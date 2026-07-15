import os
import secrets
import logging
import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from typing import Optional

import httpx
from jose import jwt, JWTError
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.ndc_user_access import NdcUserAccess
from app.models.ndc_auth_audit_log import NdcAuthAuditLog
from config.database import get_db
from app.auth.jwt_handler import create_access_token
from app.auth.jwt_bearer import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Global keys cache for Azure AD
_azure_keys_cache = {}

# Helper: Send email via SMTP
async def send_auth_email(to_email: str, subject: str, body_html: str) -> bool:
    smtp_host = os.getenv("SMTP_HOST") or os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER") or os.getenv("SMTP_USERNAME", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_user:
        logger.error("SMTP user not configured in env")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = to_email
    msg.attach(MIMEText(body_html, "html"))

    try:
        def _send():
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.ehlo()
                if "starttls" in server.esmtp_features:
                    server.starttls()
                    server.ehlo()
                if smtp_password:
                    server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from, [to_email], msg.as_string())
        
        await asyncio.to_thread(_send)
        logger.info(f"Auth email sent successfully to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send auth email to {to_email}: {e}")
        return False

# Helper: Verify ID Token signature using Azure JWKS
async def verify_azure_token(token: str, tenant_id: str, client_id: str) -> dict:
    global _azure_keys_cache
    if not _azure_keys_cache:
        url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
        async with httpx.AsyncClient() as client:
            r = await client.get(url)
            if r.status_code == 200:
                _azure_keys_cache = r.json()
            else:
                raise HTTPException(status_code=500, detail="Failed to fetch Azure AD keys")

    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token format: {str(e)}")

    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="Token header is missing 'kid'")

    rsa_key = None
    for key in _azure_keys_cache.get("keys", []):
        if key.get("kid") == kid:
            rsa_key = key
            break

    if not rsa_key:
        # Refetch keys in case of rotation
        url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
        async with httpx.AsyncClient() as client:
            r = await client.get(url)
            if r.status_code == 200:
                _azure_keys_cache = r.json()
        for key in _azure_keys_cache.get("keys", []):
            if key.get("kid") == kid:
                rsa_key = key
                break

    if not rsa_key:
        raise HTTPException(status_code=401, detail="No matching public key found for token verification")

    try:
        # Validate audience and decrypt/verify signature. Disable strict issuer validation to handle multiple potential formats.
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=client_id,
            options={"verify_iss": False}
        )
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Token validation failed: {str(e)}")


@router.get("/config")
async def get_auth_config():
    sso_enabled = os.getenv("SSO_ENABLED", "False").lower() in ("true", "1", "yes", "on")
    return {"sso_enabled": sso_enabled}


@router.get("/login")
async def login(response: Response):
    sso_enabled = os.getenv("SSO_ENABLED", "False").lower() in ("true", "1", "yes", "on")
    if not sso_enabled:
        return {"message": "SSO disabled, direct access"}

    client_id = os.getenv("AZURE_AD_CLIENT_ID")
    tenant_id = os.getenv("AZURE_AD_TENANT_ID")
    redirect_uri = os.getenv("AZURE_AD_REDIRECT_URI")

    if not all([client_id, tenant_id, redirect_uri]):
        raise HTTPException(status_code=500, detail="Azure AD environment configurations are incomplete.")

    state = secrets.token_urlsafe(32)
    response.set_cookie(
        key="oauth_state",
        value=state,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=False  # Set to True in production with HTTPS
    )

    auth_url = (
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize?"
        f"client_id={client_id}&response_type=code&redirect_uri={redirect_uri}"
        f"&response_mode=query&scope=openid%20profile%20email%20User.Read&state={state}"
    )

    return {"url": auth_url}


@router.get("/callback")
async def callback(request: Request, response: Response, code: Optional[str] = None, state: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    if not code or not state:
        raise HTTPException(status_code=400, detail="Authorization code or state parameter is missing.")

    cookie_state = request.cookies.get("oauth_state")
    if not cookie_state or cookie_state != state:
        # Clear cookie
        response.delete_cookie("oauth_state")
        raise HTTPException(status_code=400, detail="State parameter mismatch. Possible CSRF attack.")

    # Clear cookie
    response.delete_cookie("oauth_state")

    client_id = os.getenv("AZURE_AD_CLIENT_ID")
    client_secret = os.getenv("AZURE_AD_CLIENT_SECRET")
    tenant_id = os.getenv("AZURE_AD_TENANT_ID")
    redirect_uri = os.getenv("AZURE_AD_REDIRECT_URI")

    # Exchange authorization code for token
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }

    async with httpx.AsyncClient() as client:
        token_res = await client.post(token_url, data=data)
        if token_res.status_code != 200:
            logger.error(f"Failed token exchange: {token_res.text}")
            raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_res.text}")
        tokens = token_res.json()

    id_token = tokens.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="ID Token not returned by Azure AD.")

    # Verify ID Token
    payload = await verify_azure_token(id_token, tenant_id, client_id)

    email = (payload.get("email") or payload.get("preferred_username") or payload.get("upn", "")).strip().lower()
    name = payload.get("name", email.split('@')[0])

    if not email:
        raise HTTPException(status_code=400, detail="No email address found in Azure AD token claims.")

    # Check Super Admin
    super_admin_env = os.getenv("SUPER_ADMIN_EMAIL", "")
    super_admins = [e.strip().lower() for e in super_admin_env.split(",") if e.strip()]

    ip_address = request.client.host if request.client else None

    # CASE A: Email is Super Admin
    if email in super_admins:
        # Seed/update in DB to ensure it exists
        stmt = select(NdcUserAccess).where(NdcUserAccess.email == email)
        res = await db.execute(stmt)
        user_access = res.scalar_one_or_none()

        if not user_access:
            user_access = NdcUserAccess(
                email=email,
                name=name,
                role="super_admin",
                status="approved",
                approved_at=datetime.now(timezone.utc).replace(tzinfo=None),
                approved_by="system"
            )
            db.add(user_access)
        else:
            user_access.role = "super_admin"
            user_access.status = "approved"
        
        await db.commit()

        # Log audit
        audit_log = NdcAuthAuditLog(
            event_type="LOGIN_SUCCESS",
            email=email,
            role="super_admin",
            performed_by=email,
            ip_address=ip_address,
            notes="Super admin logged in"
        )
        db.add(audit_log)
        await db.commit()

        # Create session token
        session_token = create_access_token({"sub": email, "role": "super_admin", "name": name})
        return RedirectResponse(
            url=f"/ndc/ndc-reporting/overview?token={session_token}&email={email}&role=super_admin&name={name}"
        )

    # Database lookup for other users
    stmt = select(NdcUserAccess).where(NdcUserAccess.email == email)
    res = await db.execute(stmt)
    user_access = res.scalar_one_or_none()

    # CASE E: First-time login
    if not user_access:
        approval_token = secrets.token_urlsafe(32)
        user_access = NdcUserAccess(
            email=email,
            name=name,
            role="admin",
            status="pending",
            approval_token=approval_token
        )
        db.add(user_access)
        await db.commit()

        # Send approval request email to super admins
        base_url = str(request.base_url).rstrip('/')
        approve_link = f"{base_url}/api/auth/approve-access?token={approval_token}"
        reject_link = f"{base_url}/api/auth/reject-access?token={approval_token}"

        email_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; border: 1px solid #ddd; padding: 20px; border-radius: 8px;">
                <h2 style="color: #0b3d91; border-bottom: 2px solid #0b3d91; padding-bottom: 10px;">NDC System — New Access Request</h2>
                <p>Hello Super Admin,</p>
                <p>A new user has logged in via SSO for the first time and is requesting administrative access to the <b>NDC & F&F Tracking System</b>.</p>
                
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr>
                        <td style="padding: 8px; font-weight: bold; width: 30%;">User Name:</td>
                        <td style="padding: 8px;">{name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold;">User Email:</td>
                        <td style="padding: 8px;">{email}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold;">Requested Role:</td>
                        <td style="padding: 8px;">admin</td>
                    </tr>
                </table>

                <p>Please review and act on this request immediately by clicking one of the buttons below:</p>
                <div style="margin: 30px 0; text-align: center;">
                    <a href="{approve_link}" style="background-color: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold; margin-right: 15px;">APPROVE ACCESS</a>
                    <a href="{reject_link}" style="background-color: #dc3545; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold;">REJECT ACCESS</a>
                </div>
                <p style="font-size: 0.9em; color: #777;">This email link is single-use and will be invalidated once clicked.</p>
                <hr style="border: 0; border-top: 1px solid #eee;" />
                <p style="font-size: 0.85em; color: #999;">Regards,<br><b>NDC Authentication Guard</b></p>
            </div>
        </body>
        </html>
        """

        for sa_email in super_admins:
            await send_auth_email(
                to_email=sa_email,
                subject="NDC System — New Access Request",
                body_html=email_body
            )

        # Log audit
        audit_log = NdcAuthAuditLog(
            event_type="FIRST_LOGIN_REQUEST_SENT",
            email=email,
            role="admin",
            performed_by="system",
            ip_address=ip_address,
            notes="First-time login, access request sent"
        )
        db.add(audit_log)
        await db.commit()

        return RedirectResponse(url=f"/ndc/pending?email={email}")

    # CASE B: Approved User
    if user_access.status == "approved":
        audit_log = NdcAuthAuditLog(
            event_type="LOGIN_SUCCESS",
            email=email,
            role=user_access.role,
            performed_by=email,
            ip_address=ip_address,
            notes="Admin logged in successfully"
        )
        db.add(audit_log)
        await db.commit()

        session_token = create_access_token({"sub": email, "role": user_access.role, "name": name})
        return RedirectResponse(
            url=f"/ndc/ndc-reporting/overview?token={session_token}&email={email}&role={user_access.role}&name={name}"
        )

    # CASE C: Pending User
    if user_access.status == "pending":
        audit_log = NdcAuthAuditLog(
            event_type="LOGIN_BLOCKED_PENDING",
            email=email,
            role=user_access.role,
            performed_by=email,
            ip_address=ip_address,
            notes="Login blocked: approval pending"
        )
        db.add(audit_log)
        await db.commit()

        return RedirectResponse(url=f"/ndc/pending?email={email}")

    # CASE D: Rejected User
    if user_access.status == "rejected":
        audit_log = NdcAuthAuditLog(
            event_type="LOGIN_BLOCKED_REJECTED",
            email=email,
            role=user_access.role,
            performed_by=email,
            ip_address=ip_address,
            notes="Login blocked: user access rejected"
        )
        db.add(audit_log)
        await db.commit()

        return RedirectResponse(url=f"/ndc/access-denied?email={email}")


@router.get("/approve-access", response_class=HTMLResponse)
async def approve_access(token: str, db: AsyncSession = Depends(get_db)):
    stmt = select(NdcUserAccess).where(NdcUserAccess.approval_token == token)
    res = await db.execute(stmt)
    user_access = res.scalar_one_or_none()

    if not user_access:
        return """
        <html>
        <body style="font-family: Arial, sans-serif; text-align: center; padding-top: 100px; background-color: #f8f9fa;">
            <div style="max-width: 500px; margin: auto; padding: 40px; background: white; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                <div style="font-size: 48px; color: #dc3545; margin-bottom: 20px;">⚠️</div>
                <h2 style="color: #343a40;">Link Invalid or Expired</h2>
                <p style="color: #6c757d; font-size: 1.1em;">This access approval link has already been used or is invalid.</p>
            </div>
        </body>
        </html>
        """

    email = user_access.email
    name = user_access.name or email.split('@')[0]

    # Update status to approved and clear approval_token
    user_access.status = "approved"
    user_access.approved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    user_access.approved_by = "super_admin"
    user_access.approval_token = None

    db.add(user_access)

    # Log audit
    audit_log = NdcAuthAuditLog(
        event_type="ACCESS_APPROVED",
        email=email,
        role=user_access.role,
        performed_by="super_admin",
        notes="Access approved via email link"
    )
    db.add(audit_log)
    await db.commit()

    # Send confirmation email to user
    user_email_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; border: 1px solid #ddd; padding: 20px; border-radius: 8px;">
            <h2 style="color: #28a745; border-bottom: 2px solid #28a745; padding-bottom: 10px;">NDC System — Access Granted</h2>
            <p>Hello {name},</p>
            <p>Your access request to the <b>NDC & F&F Tracking and Reporting System</b> has been approved by the administrator.</p>
            <p>You can now log in to the portal using your Adani corporate account.</p>
            <div style="margin: 30px 0; text-align: center;">
                <a href="/ndc" style="background-color: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold;">GO TO NDC TRACKING SYSTEM</a>
            </div>
            <hr style="border: 0; border-top: 1px solid #eee;" />
            <p style="font-size: 0.85em; color: #999;">Regards,<br><b>NDC System Administrator</b></p>
        </div>
    </body>
    </html>
    """
    await send_auth_email(
        to_email=email,
        subject="NDC System — Access Granted",
        body_html=user_email_body
    )

    return """
    <html>
    <body style="font-family: Arial, sans-serif; text-align: center; padding-top: 100px; background-color: #f8f9fa;">
        <div style="max-width: 500px; margin: auto; padding: 40px; background: white; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
            <div style="font-size: 48px; color: #28a745; margin-bottom: 20px;">✓</div>
            <h2 style="color: #343a40; margin-bottom: 10px;">Access Approved</h2>
            <p style="color: #6c757d; font-size: 1.1em;">You have successfully approved access for <strong>{}</strong>.</p>
            <p style="color: #6c757d; font-size: 1.1em;">An email confirmation has been dispatched to the user.</p>
        </div>
    </body>
    </html>
    """.format(email)


@router.get("/reject-access", response_class=HTMLResponse)
async def reject_access(token: str, db: AsyncSession = Depends(get_db)):
    stmt = select(NdcUserAccess).where(NdcUserAccess.approval_token == token)
    res = await db.execute(stmt)
    user_access = res.scalar_one_or_none()

    if not user_access:
        return """
        <html>
        <body style="font-family: Arial, sans-serif; text-align: center; padding-top: 100px; background-color: #f8f9fa;">
            <div style="max-width: 500px; margin: auto; padding: 40px; background: white; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                <div style="font-size: 48px; color: #dc3545; margin-bottom: 20px;">⚠️</div>
                <h2 style="color: #343a40;">Link Invalid or Expired</h2>
                <p style="color: #6c757d; font-size: 1.1em;">This access rejection link has already been used or is invalid.</p>
            </div>
        </body>
        </html>
        """

    email = user_access.email
    name = user_access.name or email.split('@')[0]

    # Update status to rejected and clear approval_token
    user_access.status = "rejected"
    user_access.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    user_access.reviewed_by = "super_admin"
    user_access.approval_token = None

    db.add(user_access)

    # Log audit
    audit_log = NdcAuthAuditLog(
        event_type="ACCESS_REJECTED",
        email=email,
        role=user_access.role,
        performed_by="super_admin",
        notes="Access rejected via email link"
    )
    db.add(audit_log)
    await db.commit()

    # Send rejection email to user
    user_email_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; border: 1px solid #ddd; padding: 20px; border-radius: 8px;">
            <h2 style="color: #dc3545; border-bottom: 2px solid #dc3545; padding-bottom: 10px;">NDC System — Access Denied</h2>
            <p>Hello {name},</p>
            <p>Your access request to the <b>NDC & F&F Tracking and Reporting System</b> has been declined.</p>
            <p>If you believe this is a mistake, please contact the system administrator for assistance.</p>
            <hr style="border: 0; border-top: 1px solid #eee;" />
            <p style="font-size: 0.85em; color: #999;">Regards,<br><b>NDC System Administrator</b></p>
        </div>
    </body>
    </html>
    """
    await send_auth_email(
        to_email=email,
        subject="NDC System — Access Denied",
        body_html=user_email_body
    )

    return """
    <html>
    <body style="font-family: Arial, sans-serif; text-align: center; padding-top: 100px; background-color: #f8f9fa;">
        <div style="max-width: 500px; margin: auto; padding: 40px; background: white; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
            <div style="font-size: 48px; color: #dc3545; margin-bottom: 20px;">✕</div>
            <h2 style="color: #343a40; margin-bottom: 10px;">Access Denied</h2>
            <p style="color: #6c757d; font-size: 1.1em;">You have rejected access for <strong>{}</strong>.</p>
            <p style="color: #6c757d; font-size: 1.1em;">The user has been notified of the decision.</p>
        </div>
    </body>
    </html>
    """.format(email)


@router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    email = "unknown"
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            from app.auth.jwt_handler import decode_jwt_token
            email = decode_jwt_token(token) or "unknown"
        except Exception:
            pass

    # Log audit
    audit_log = NdcAuthAuditLog(
        event_type="SESSION_REVOKED",
        email=email,
        performed_by=email,
        ip_address=request.client.host if request.client else None,
        notes="User logged out successfully"
    )
    db.add(audit_log)
    await db.commit()

    # In a full Azure flow we can also return a logout redirect URL
    tenant_id = os.getenv("AZURE_AD_TENANT_ID")
    logout_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/logout?post_logout_redirect_uri={request.base_url}"
    return {"message": "Logged out successfully", "logout_url": logout_url}


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    email = current_user.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token session payload.")

    sso_enabled = os.getenv("SSO_ENABLED", "False").lower() in ("true", "1", "yes", "on")
    if not sso_enabled:
        return {
            "email": "dev@local.com",
            "name": "Dev User",
            "role": "super_admin",
            "status": "approved"
        }

    stmt = select(NdcUserAccess).where(NdcUserAccess.email == email)
    res = await db.execute(stmt)
    user_access = res.scalar_one_or_none()

    if not user_access:
        # Check if they are configured as Super Admin
        super_admin_env = os.getenv("SUPER_ADMIN_EMAIL", "")
        super_admins = [e.strip().lower() for e in super_admin_env.split(",") if e.strip()]
        if email in super_admins:
            return {
                "email": email,
                "name": current_user.get("name", email.split('@')[0]),
                "role": "super_admin",
                "status": "approved"
            }
        raise HTTPException(status_code=403, detail="User access record not found in system.")

    return {
        "email": user_access.email,
        "name": user_access.name,
        "role": user_access.role,
        "status": user_access.status
    }


# ==============================================================================
# SUPER ADMIN ADMIN ACTIONS (under /api/admin)
# ==============================================================================

# Custom dependency to enforce super_admin access
async def require_super_admin(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    email = current_user.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Unauthorized")

    sso_enabled = os.getenv("SSO_ENABLED", "False").lower() in ("true", "1", "yes", "on")
    if not sso_enabled:
        return "super_admin"

    # Check hardcoded list first
    super_admin_env = os.getenv("SUPER_ADMIN_EMAIL", "")
    super_admins = [e.strip().lower() for e in super_admin_env.split(",") if e.strip()]
    if email in super_admins:
        return "super_admin"

    stmt = select(NdcUserAccess.role).where(NdcUserAccess.email == email, NdcUserAccess.status == "approved")
    res = await db.execute(stmt)
    role = res.scalar_one_or_none()

    if role != "super_admin":
        raise HTTPException(status_code=403, detail="Access denied. Super Admin role required.")
    
    return role


admin_router = APIRouter(prefix="/api/admin", tags=["Admin Management"], dependencies=[Depends(require_super_admin)])


@admin_router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db)):
    stmt = select(NdcUserAccess).order_by(NdcUserAccess.requested_at.desc())
    res = await db.execute(stmt)
    users = res.scalars().all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "role": u.role,
            "status": u.status,
            "requested_at": u.requested_at.isoformat() if u.requested_at else None,
            "approved_at": u.approved_at.isoformat() if u.approved_at else None,
            "approved_by": u.approved_by,
            "reviewed_at": u.reviewed_at.isoformat() if u.reviewed_at else None,
            "reviewed_by": u.reviewed_by,
            "notes": u.notes
        }
        for u in users
    ]


@admin_router.put("/users/{email}/revoke")
async def revoke_access(email: str, db: AsyncSession = Depends(get_db)):
    email_clean = email.strip().lower()
    
    # Check if they are trying to revoke a super_admin from env list
    super_admin_env = os.getenv("SUPER_ADMIN_EMAIL", "")
    super_admins = [e.strip().lower() for e in super_admin_env.split(",") if e.strip()]
    if email_clean in super_admins:
        raise HTTPException(status_code=400, detail="Cannot revoke root super admins configured via environment variables.")

    stmt = select(NdcUserAccess).where(NdcUserAccess.email == email_clean)
    res = await db.execute(stmt)
    user_access = res.scalar_one_or_none()

    if not user_access:
        raise HTTPException(status_code=404, detail="User access record not found.")

    user_access.status = "rejected"
    user_access.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    user_access.reviewed_by = "super_admin"
    user_access.approval_token = None
    db.add(user_access)

    # Log audit
    audit_log = NdcAuthAuditLog(
        event_type="SESSION_REVOKED",
        email=email_clean,
        role=user_access.role,
        performed_by="super_admin",
        notes="User access revoked by super admin"
    )
    db.add(audit_log)
    await db.commit()

    return {"message": f"Access successfully revoked for {email_clean}."}


@admin_router.get("/audit-logs")
async def list_audit_logs(page: int = 1, limit: int = 50, db: AsyncSession = Depends(get_db)):
    offset = (page - 1) * limit
    stmt = select(NdcAuthAuditLog).order_by(NdcAuthAuditLog.created_at.desc()).offset(offset).limit(limit)
    res = await db.execute(stmt)
    logs = res.scalars().all()
    
    # Fetch total count
    from sqlalchemy import func
    count_stmt = select(func.count(NdcAuthAuditLog.id))
    count_res = await db.execute(count_stmt)
    total = count_res.scalar() or 0

    return {
        "logs": [
            {
                "id": l.id,
                "event_type": l.event_type,
                "email": l.email,
                "role": l.role,
                "performed_by": l.performed_by,
                "ip_address": l.ip_address,
                "created_at": l.created_at.isoformat() if l.created_at else None,
                "notes": l.notes
            }
            for l in logs
        ],
        "total": total,
        "page": page,
        "limit": limit
    }
