"""Email service – sends the NDC Delayed Cases reminder email via SMTP."""

import asyncio
from datetime import date, datetime, timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import io
import logging
import os
import smtplib
import zipfile

from sqlalchemy import select, text
from sqlalchemy.orm import defer
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ndc_approval import NdcApproval
from app.models.ndc_record import NdcRecord
from app.models.email_recipient import EmailRecipient
from app.models.rm_email_configuration import RmEmailConfiguration
from app.services.common_service import _derive_fnf_status
from app.services.sharepoint_service import SharePointService, get_httpx_client
from config.database import BASE_DIR, async_session

logger = logging.getLogger(__name__)


# ── helpers ──────────────────────────────────────────────────────────────────

def _fmt_date(d) -> str:
    """Format a date or date-string as '01-Jun-2026'."""
    if d is None:
        return "—"
    if isinstance(d, (date, datetime)):
        return d.strftime("%d-%b-%Y")
    try:
        return datetime.strptime(str(d), "%Y-%m-%d").strftime("%d-%b-%Y")
    except Exception:
        return str(d)


def _days_delayed(last_working_date) -> int:
    """Return how many calendar days have passed since last_working_date."""
    if last_working_date is None:
        return 0
    if isinstance(last_working_date, (date, datetime)):
        lwd = last_working_date if isinstance(last_working_date, date) else last_working_date.date()
    else:
        try:
            lwd = datetime.strptime(str(last_working_date), "%Y-%m-%d").date()
        except Exception:
            return 0
    diff = (date.today() - lwd).days
    return max(0, diff)


# ── HTML template builder ─────────────────────────────────────────────────────

def _build_html(records: list[dict]) -> str:
    """Build the full HTML email body for the delayed-cases reminder."""

    row_html = ""
    for rec in records:
        days = rec.get("days_delayed", 0)
        row_html += f"""
        <tr>
          <td>{rec.get('person_number', '')}</td>
          <td>{rec.get('employee_name', '')}</td>
          <td>{rec.get('department', '—')}</td>
          <td>{_fmt_date(rec.get('last_working_date'))}</td>
          <td><span class="delay">{days} Days</span></td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
body{{background:#f5f7fb;font-family:Arial,sans-serif;padding:30px;}}
.container{{max-width:1000px;margin:auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);}}
.header{{background:#0b3d91;color:white;padding:25px 35px;}}
.header h2{{margin:0;}}
.content{{padding:30px;color:#333;line-height:1.7;}}
.summary{{background:#f4f8ff;padding:14px 18px;border-left:4px solid #0b3d91;margin:20px 0;}}
table{{width:100%;border-collapse:collapse;margin-top:15px;}}
th{{background:#eef3fb;padding:14px;text-align:left;}}
td{{padding:14px;border-bottom:1px solid #ececec;}}
.delay{{background:#ffe5e5;color:#d62828;padding:6px 12px;border-radius:20px;font-weight:600;}}
.note{{background:#fff7e6;padding:16px;margin-top:25px;border-left:4px solid #ffb020;}}
.footer{{padding:25px 30px;background:#fafafa;color:#666;}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h2>NDC Delayed Cases – Top 10 Report</h2>
  </div>
  <div class="content">
    <p>Hello Team,</p>
    <p>
      Please find below the list of the <b>Top {min(len(records), 10)} delayed cases</b>
      identified as of today ({_fmt_date(date.today())}).
      These records have exceeded the expected completion timeline and require attention for closure.
    </p>
    <table>
      <tr>
        <th>Employee ID</th>
        <th>Name</th>
        <th>Department</th>
        <th>Pending Since</th>
        <th>Days Delayed</th>
      </tr>
      {row_html}
    </table>
    <div class="note">
      Please review the above delayed cases and take the required actions at the earliest
      to avoid further aging and ensure timely closure.
    </div>
    <p>If any of these records have already been processed, kindly ignore this notification.</p>
    <p>Thank you for your support.</p>
  </div>
  <div class="footer">
    Regards,<br>
    <b>Automation Team</b><br>
    NDC Monitoring System
  </div>
</div>
</body>
</html>"""
    return html


# ── main send function ────────────────────────────────────────────────────────

async def send_delayed_reminder(records: list[dict]) -> dict:
    """
    Send the NDC delayed-cases reminder email with the top 10 delayed records.

    Args:
        records: Top-N delayed records (dicts with keys: person_number,
                 employee_name, department, last_working_date, days_delayed).

    Returns:
        {"success": bool, "message": str}
    """
    smtp_host = os.getenv("SMTP_HOST") or os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER") or os.getenv("SMTP_USERNAME", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)
    recipient = os.getenv("EMAIL_RECIPIENT", "")

    if not smtp_user:
        msg = "SMTP user not configured"
        logger.error(msg)
        return {"success": False, "message": msg}

    if not recipient:
        msg = "EMAIL_RECIPIENT not configured"
        logger.error(msg)
        return {"success": False, "message": msg}

    html_body = _build_html(records)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"NDC Delayed Cases Reminder – Top {min(len(records), 10)} Records ({_fmt_date(date.today())})"
    msg["From"] = smtp_from
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=60) as server:
            server.ehlo()
            if "starttls" in server.esmtp_features:
                server.starttls()
                server.ehlo()
            if smtp_password:
                server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [recipient], msg.as_string())

        logger.info("Delayed-cases reminder sent to %s (%d records)", recipient, len(records))
        return {
            "success": True,
            "message": f"Reminder email sent to {recipient} with {len(records)} delayed records.",
        }
    except Exception as e:
        logger.exception("Failed to send reminder email: %s", e)
        return {"success": False, "message": f"Email failed: {e}"}


async def send_fnf_details_email(email_to: str, record: dict) -> dict:
    """
    Send the F&F details of an employee to a specific email address,
    attaching the F&F document file if available.
    """

    smtp_host = os.getenv("SMTP_HOST") or os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER") or os.getenv("SMTP_USERNAME", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_user:
        msg = "SMTP user not configured"
        logger.error(msg)
        return {"success": False, "message": msg}

    # Build simple, professional HTML template
    html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    color: #334155;
    background-color: #f8fafc;
    padding: 30px 15px;
    margin: 0;
  }}
  .container {{
    max-width: 560px;
    margin: 0 auto;
    background: #ffffff;
    border-radius: 8px;
    border-top: 4px solid #0f766e;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
    overflow: hidden;
    border-left: 1px solid #e2e8f0;
    border-right: 1px solid #e2e8f0;
    border-bottom: 1px solid #e2e8f0;
  }}
  .content {{
    padding: 32px 24px;
  }}
  h2 {{
    color: #0f766e;
    font-size: 18px;
    font-weight: 600;
    margin-top: 0;
    margin-bottom: 20px;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 10px;
  }}
  p {{
    margin: 0 0 16px;
    font-size: 14px;
    line-height: 1.6;
    color: #475569;
  }}
  .details-table {{
    width: 100%;
    border-collapse: collapse;
    margin: 20px 0;
    font-size: 13.5px;
  }}
  .details-table td {{
    padding: 10px 12px;
    border-bottom: 1px solid #f1f5f9;
  }}
  .details-table tr:last-child td {{
    border-bottom: none;
  }}
  .label {{
    font-weight: 600;
    color: #64748b;
    width: 38%;
  }}
  .value {{
    color: #0f172a;
    font-weight: 500;
  }}
  .footer {{
    background-color: #f8fafc;
    padding: 20px 24px;
    border-top: 1px solid #e2e8f0;
    font-size: 12.5px;
    color: #64748b;
    line-height: 1.5;
  }}
  .footer strong {{
    color: #475569;
  }}
</style>
</head>
<body>
<div class="container">
  <div class="content">
    <h2>Full &amp; Final Settlement Details</h2>
    <p>Dear Recipient,</p>
    <p>Please find below the Full &amp; Final (F&amp;F) settlement details for the employee clearance request:</p>
    
    <table class="details-table">
      <tr>
        <td class="label">Employee Name:</td>
        <td class="value">{record.get('employee_name')}</td>
      </tr>
      <tr>
        <td class="label">Person Number:</td>
        <td class="value">{record.get('person_number')}</td>
      </tr>
      <tr>
        <td class="label">Department:</td>
        <td class="value">{record.get('department')}</td>
      </tr>
      <tr>
        <td class="label">Resignation Date:</td>
        <td class="value">{_fmt_date(record.get('resignation_date'))}</td>
      </tr>
      <tr>
        <td class="label">Last Working Date:</td>
        <td class="value">{_fmt_date(record.get('last_working_date'))}</td>
      </tr>
      <tr>
        <td class="label">F&amp;F Status:</td>
        <td class="value">{record.get('fnf_status')}</td>
      </tr>
      <tr>
        <td class="label">Completed Date:</td>
        <td class="value">{_fmt_date(record.get('fnf_completed_date'))}</td>
      </tr>
      <tr>
        <td class="label">Document Count:</td>
        <td class="value">{record.get('fnf_document_count', 0)}</td>
      </tr>
    </table>
  </div>
  <div class="footer">
    Regards,<br>
    <strong>NDC Monitoring System</strong>
  </div>
</div>
</body>
</html>"""

    # Build MIMEMultipart message
    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"F&F Settlement Details – {record.get('employee_name')} ({record.get('person_number')})"
    msg["From"] = smtp_from
    msg["To"] = email_to
    
    # Attach body
    body_part = MIMEText(html_body, "html")
    msg.attach(body_part)

    # Attach F&F document(s) from SharePoint or local folder as fallback
    attached_from_sharepoint = False
    person_number = record.get("person_number")
    
    if person_number:
        logger.info("Attempting to attach F&F document(s) from SharePoint for person: %s", person_number)
        sharepoint_service = SharePointService()
        async with get_httpx_client() as client:
            try:
                # 1. Resolve site ID
                site_id = await sharepoint_service.get_site_id(client)
                
                # 2. Resolve drive ID and folder path
                drive_id, folder_path = await sharepoint_service.get_drive_details(client, site_id)
                
                # 3. Locate folder and list files
                files, resolved_folder = await sharepoint_service.get_person_folder_files(
                    client, site_id, drive_id, folder_path, person_number
                )
                
                if files:
                    if len(files) == 1:
                        # Single file attachment
                        file_item = files[0]
                        name = file_item.get("name", "document.pdf")
                        download_url = file_item.get("@microsoft.graph.downloadUrl")
                        if download_url:
                            logger.info("Downloading file '%s' from SharePoint for email attachment.", name)
                            res = await client.get(download_url)
                            if res.status_code == 200:
                                attachment = MIMEApplication(res.content)
                                attachment.add_header('Content-Disposition', 'attachment', filename=name)
                                msg.attach(attachment)
                                logger.info("Successfully attached SharePoint file '%s' to email.", name)
                                attached_from_sharepoint = True
                    else:
                        # Multiple files: ZIP them in-memory and attach
                        logger.info("Multiple files (%d) found in SharePoint. Zipping for email attachment...", len(files))
                        
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                            for file_item in files:
                                name = file_item.get("name", "document.pdf")
                                download_url = file_item.get("@microsoft.graph.downloadUrl")
                                if download_url:
                                    logger.info("Downloading '%s' from SharePoint for email ZIP attachment...", name)
                                    res = await client.get(download_url)
                                    if res.status_code == 200:
                                        zip_file.writestr(name, res.content)
                                        
                        zip_buffer.seek(0)
                        zip_data = zip_buffer.read()
                        if zip_data:
                            zip_filename = f"{person_number}_documents.zip"
                            attachment = MIMEApplication(zip_data)
                            attachment.add_header('Content-Disposition', 'attachment', filename=zip_filename)
                            msg.attach(attachment)
                            logger.info("Successfully attached SharePoint ZIP archive '%s' to email.", zip_filename)
                            attached_from_sharepoint = True
                else:
                    logger.info("No SharePoint documents found for person: %s", person_number)
            except Exception as e:
                logger.error("Failed to retrieve SharePoint attachments for email: %s", str(e))

    # Fallback to local uploads folder if nothing was attached from SharePoint
    if not attached_from_sharepoint:
        fnf_doc_name = record.get("fnf_document")
        if fnf_doc_name:
            file_path = BASE_DIR / "uploads" / fnf_doc_name
            if file_path.exists():
                with open(file_path, "rb") as f:
                    attachment = MIMEApplication(f.read())
                attachment.add_header('Content-Disposition', 'attachment', filename=fnf_doc_name)
                msg.attach(attachment)
                logger.info("Attached F&F document from local server fallback: %s", fnf_doc_name)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=60) as server:
            server.ehlo()
            if "starttls" in server.esmtp_features:
                server.starttls()
                server.ehlo()
            if smtp_password:
                server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [email_to], msg.as_string())

        logger.info("F&F details email sent to %s for %s", email_to, record.get('employee_name'))
        return {
            "success": True,
            "message": f"Email sent successfully to {email_to}.",
        }
    except Exception as e:
        logger.exception("Failed to send F&F details email: %s", e)
        return {"success": False, "message": f"Failed to send email: {e}"}


async def send_fnf_email_service(record_id: int, email_to: str, db: AsyncSession) -> dict:
    """Prepare and send the F&F details email for a specific record."""
    result = await db.execute(
        select(NdcRecord).where(NdcRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        return {"success": False, "message": "Record not found", "status_code": 404}

    # Fetch record approvals
    approvals_res = await db.execute(
        select(NdcApproval).where(NdcApproval.ndc_record_id == record.id)
    )
    record_approvals = approvals_res.scalars().all()

    stage_key_map = {
        "RM Approval": "rm",
        "IT Approval": "it",
        "ABEX Approval": "abex",
        "Telecom Approval": "telecom",
        "Store Approval": "store",
        "Safety Approval": "safety",
        "Administration Approval": "administration",
        "Security Approval": "security",
        "HR Approval": "hr",
        "GCC HR Approval": "gcc_hr",
        "Final ABEX Approval": "final_abex",
        "Business Specific Approval": "business_specific",
        "Legatrix Approval": "legatrix",
    }

    # Check if an F&F document file exists on the server in the uploads folder
    fnf_doc_name = ""
    for ext in [".pdf", ".png", ".jpg", ".jpeg", ".docx", ".xlsx", ".xls"]:
        possible_file = f"{record.person_number}{ext}"
        possible_path = BASE_DIR / "uploads" / possible_file
        if possible_path.exists():
            fnf_doc_name = possible_file
            break

    # Base record fields
    record_dict = {
        "person_number": str(record.person_number),
        "employee_name": record.employee_name or "",
        "department": record.department or record.department_reporting_name or "—",
        "resignation_date": record.resignation_date,
        "last_working_date": record.last_working_date,
        "fnf_status": _derive_fnf_status(record),
        "fnf_completed_date": record.fnf_completed_date,
        "fnf_document_count": record.fnf_document_count,
        "fnf_document": fnf_doc_name,
    }

    # Initialize approvals with default
    for prefix in stage_key_map.values():
        record_dict[f"{prefix}_approval_status"] = "Not Applicable"
        record_dict[f"{prefix}_approval_date"] = ""

    # Populate approvals
    for approval in record_approvals:
        prefix = stage_key_map.get(approval.stage_name)
        if prefix:
            status_mapped = ""
            if approval.status == "PENDING":
                status_mapped = "Pending"
            elif approval.status == "IN_PROGRESS":
                status_mapped = "In Progress"
            elif approval.status == "COMPLETED":
                status_mapped = "Completed"
            elif approval.status == "NOT_APPLICABLE":
                status_mapped = "Not Applicable"
            else:
                status_mapped = approval.status.capitalize() if approval.status else "Not Applicable"

            record_dict[f"{prefix}_approval_status"] = status_mapped
            record_dict[f"{prefix}_approval_date"] = (
                approval.stage_completed_at.strftime("%Y-%m-%d")
                if approval.stage_completed_at
                else ""
            )

    outcome = await send_fnf_details_email(
        email_to=email_to.strip(),
        record=record_dict
    )
    return outcome


def send_notification_email(records, recipient, stage_name, manager_name=None, is_tomorrow=False):
    """Format the records as HTML and send via SMTP."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_user:
        logger.error("SMTP_USER not configured in env")
        return False

    if not records:
        return False

    row_html = ""
    for rec in records:
        lwd = _fmt_date(rec.last_working_date)
        row_html += f"""
        <tr>
          <td>{rec.person_number}</td>
          <td>{rec.employee_name}</td>
          <td>{rec.department or '—'}</td>
          <td>{lwd}</td>
        </tr>"""

    greeting = f"Dear {manager_name}," if manager_name else "Hello,"
    warning_html = ""
    if manager_name and "Conflict Redirected" in manager_name:
        greeting = "Dear HR Team,"
        clean_name = manager_name.replace(" (Conflict Redirected)", "")
        warning_html = f"""
        <p style="color: #d9534f; font-weight: bold; background-color: #fdf7f7; border: 1px solid #d9534f; padding: 12px; border-radius: 5px; margin-bottom: 15px;">
          Warning: This report has been redirected to HR because there are multiple conflicting email configurations for manager '{clean_name}' in the system.
        </p>
        """

    if is_tomorrow:
        tomorrow_str = _fmt_date(date.today() + timedelta(days=1))
        intro_paragraph = f"""
        <p>The following users are currently pending in the <b>{stage_name}</b> Approval stage.</p>
        <p>These records have their last working date set for tomorrow ({tomorrow_str}):</p>
        """
        subject = f"Pending {stage_name} Approvals Report - Action Required Tomorrow"
    else:
        intro_paragraph = f"<p>The following users are currently pending in the <b>{stage_name}</b> Approval stage.</p>"
        subject = f"Pending {stage_name} Approvals Report - Action Required"

    html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
body {{background:#f5f7fb;font-family:Arial,sans-serif;padding:30px;}}
.container {{max-width:800px;margin:auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);}}
.header {{background:#0b3d91;color:white;padding:25px 35px;}}
.header h2 {{margin:0;}}
.content {{padding:30px;color:#333;line-height:1.7;}}
table {{width:100%;border-collapse:collapse;margin-top:15px;}}
th {{background:#eef3fb;padding:14px;text-align:left;}}
td {{padding:14px;border-bottom:1px solid #ececec;}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h2>Pending {stage_name} Approval Records</h2>
  </div>
  <div class="content">
    <p>{greeting}</p>
    {warning_html}
    {intro_paragraph}
    <table>
      <tr>
        <th>Employee ID</th>
        <th>Name</th>
        <th>Department</th>
        <th>Last Working Date</th>
      </tr>
      {row_html}
    </table>
    <p>Please review these records and take the necessary actions.</p>
  </div>
</div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            if "starttls" in server.esmtp_features:
                server.starttls()
                server.ehlo()
            if smtp_password:
                server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [recipient], msg.as_string())
        logger.info(f"Successfully sent {stage_name} email with {len(records)} records to {recipient}.")
        return True
    except Exception as e:
        logger.error(f"Failed to send {stage_name} email to {recipient}: {e}")
        return False


def send_duplicate_managers_report(records, recipient):
    """Format the conflicting/duplicate RM records as HTML and send to HR."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_user:
        logger.error("SMTP_USER not configured in env")
        return False

    if not records:
        return False

    row_html = ""
    for rm_name, rec in records:
        lwd = _fmt_date(rec.last_working_date)
        row_html += f"""
        <tr>
          <td style="font-weight: bold; color: #d9534f;">{rm_name}</td>
          <td>{rec.person_number}</td>
          <td>{rec.employee_name}</td>
          <td>{rec.department or '—'}</td>
          <td>{lwd}</td>
        </tr>"""

    html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
body {{background:#f5f7fb;font-family:Arial,sans-serif;padding:30px;}}
.container {{max-width:850px;margin:auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);}}
.header {{background:#d9534f;color:white;padding:25px 35px;}}
.header h2 {{margin:0;}}
.content {{padding:30px;color:#333;line-height:1.7;}}
table {{width:100%;border-collapse:collapse;margin-top:15px;}}
th {{background:#fdf7f7;padding:14px;text-align:left;border-bottom:2px solid #d9534f;}}
td {{padding:14px;border-bottom:1px solid #ececec;}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h2>Conflicting RM Configurations - Redirected Approvals Report</h2>
  </div>
  <div class="content">
    <p>Dear HR Team,</p>
    <p style="color: #d9534f; font-weight: bold; background-color: #fdf7f7; border: 1px solid #d9534f; padding: 12px; border-radius: 5px; margin-bottom: 15px;">
      Warning: The following pending RM approvals have been redirected to HR because their Reporting Managers have multiple conflicting email configurations in the system. Please resolve these duplicates in the <b>rm_email_configuration</b> database table.
    </p>
    <table>
      <tr>
        <th>Reporting Manager</th>
        <th>Employee ID</th>
        <th>Name</th>
        <th>Department</th>
        <th>Last Working Date</th>
      </tr>
      {row_html}
    </table>
    <p>Please review these records and take the necessary actions.</p>
  </div>
</div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Redirected RM Approvals Report (Conflicting Manager Configurations) - Action Required"
    msg["From"] = smtp_from
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            if "starttls" in server.esmtp_features:
                server.starttls()
                server.ehlo()
            if smtp_password:
                server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [recipient], msg.as_string())
        logger.info(f"Successfully sent consolidated duplicate RM report with {len(records)} records to HR ({recipient}).")
        return True
    except Exception as e:
        logger.error(f"Failed to send consolidated duplicate RM report to HR ({recipient}): {e}")
        return False


async def fetch_all_data():
    """Fetch all active NDC records and their approval stages from the database, handling schema differences if needed."""
    async with async_session() as session:
        # Check if 'approver_name' column exists in database to avoid ProgrammingError on old schemas
        has_approver_name_col = False
        try:
            col_check = await session.execute(text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ndc_records' AND column_name='approver_name')"
            ))
            has_approver_name_col = col_check.scalar()
        except Exception as e:
            logger.warning(f"Could not check for approver_name column presence: {e}")

        query = select(NdcRecord, NdcApproval).join(NdcApproval, NdcRecord.id == NdcApproval.ndc_record_id)
        if not has_approver_name_col and hasattr(NdcRecord, "approver_name"):
            query = query.options(defer(NdcRecord.approver_name))
            
        result = await session.execute(query)
        rows = result.all()
        
        # Group by record
        records_map = {}
        for rec, app in rows:
            if rec.id not in records_map:
                records_map[rec.id] = {
                    "record": rec,
                    "approvals": {},
                    "db_approvals": []
                }
            records_map[rec.id]["db_approvals"].append(app)
            
            # Use lower case for consistent matching
            stage = app.stage_name.strip().lower()
            status = app.status.strip().lower() if app.status else ""
            
            # Handle GCC HR vs HR carefully
            if "gcc hr" in stage:
                key = "gcc hr"
            elif "hr" in stage:
                key = "hr"
            elif "rm" in stage:
                key = "rm"
            elif "telecom" in stage:
                key = "telecom"
            elif "administration" in stage or "admin" in stage:
                key = "administration"
            elif "it" in stage:
                key = "it"
            elif "safety" in stage:
                key = "safety"
            elif "security" in stage:
                key = "security"
            elif "final abex" in stage:
                key = "final abex"
            elif "abex" in stage:
                key = "abex"
            elif "store" in stage:
                key = "store"
            elif "business specific" in stage:
                key = "business specific"
            elif "legatrix" in stage:
                key = "legatrix"
            else:
                key = stage
                
            records_map[rec.id]["approvals"][key] = status
            
        return records_map


async def run_10am_job():
    """Daily 10:00 AM Email Job to send all pending approval updates."""
    logger.info("Starting consolidated 10:00 AM email job...")
    records_map = await fetch_all_data()
    
    # Fetch department email recipients and RM configs
    dept_email_map = {}
    rm_configs_by_name = {}  # key: rm_name (lower) -> list of emails
    
    async with async_session() as session:
        try:
            dept_res = await session.execute(select(EmailRecipient))
            for rec in dept_res.scalars().all():
                if rec.department and rec.email:
                    dept_email_map[rec.department.strip().lower()] = rec.email.strip()
        except Exception as e:
            logger.warning(f"Could not fetch department email recipients: {e}")
            
        try:
            rm_configs_res = await session.execute(select(RmEmailConfiguration))
            for cfg in rm_configs_res.scalars().all():
                if cfg.rm_name and cfg.email:
                    name_key = cfg.rm_name.strip().lower()
                    email_val = cfg.email.strip()
                    if name_key not in rm_configs_by_name:
                        rm_configs_by_name[name_key] = []
                    rm_configs_by_name[name_key].append(email_val)
        except Exception as e:
            logger.warning(f"Could not fetch RM email configurations: {e}")
            
    rm_groups = {}  # key: (rm_name, rm_email) -> value: list of NdcRecord
    duplicate_rm_records = []  # list of (rm_name, rec)
    
    departments = [
        ("HR", dept_email_map.get("hr")),
        ("Telecom", dept_email_map.get("telecom")),
        ("Administration", dept_email_map.get("administration")),
        ("GCC HR", dept_email_map.get("gcc hr")),
        ("Abex", dept_email_map.get("abex")),
        ("Store", dept_email_map.get("store")),
        ("Safety", dept_email_map.get("safety")),
        ("Final Abex", dept_email_map.get("final abex")),
        ("Business Specific", dept_email_map.get("business specific")),
        ("Legatrix", dept_email_map.get("legatrix")),
    ]
    
    emails_to_send = {dep: [] for dep, _ in departments}
    
    for rec_id, data in records_map.items():
        rec = data["record"]
        approvals = data["approvals"]
        db_approvals = data.get("db_approvals", [])
        
        # 1. Group for RM department separately (only if Pending)
        if approvals.get("rm", "") == "pending":
            rm_name = getattr(rec, "approver_name", None)
            if not rm_name:
                for app in db_approvals:
                    if app.stage_name.strip().lower() == "rm":
                        rm_name = app.approver_name
                        break
            
            if rm_name:
                rm_name = rm_name.strip()
            else:
                rm_name = "Unknown Manager"
                
            has_conflict = False
            rm_email = None
            
            if rm_name and rm_name != "Unknown Manager":
                normalized_rm = rm_name.lower()
                if normalized_rm in rm_configs_by_name:
                    emails = rm_configs_by_name[normalized_rm]
                    if len(emails) > 1:
                        has_conflict = True
                    elif len(emails) == 1:
                        rm_email = emails[0]
            
            default_rm_email = dept_email_map.get("rm")
            
            if has_conflict:
                duplicate_rm_records.append((rm_name, rec))
            else:
                target_email = rm_email or default_rm_email
                if not target_email:
                    logger.info(f"Skipping notification for RM '{rm_name}': no email configuration or default RM email found.")
                    continue
                key = (rm_name, target_email)
                if key not in rm_groups:
                    rm_groups[key] = []
                rm_groups[key].append(rec)
            
        # 2. Build for other departments
        for dept_name, recipient in departments:
            dept_key = dept_name.lower()
            current_status = approvals.get(dept_key, "")
            
            # Specific rule for GCC HR
            if dept_name == "GCC HR":
                req_depts = ["rm", "it", "telecom", "safety", "administration", "security", "hr"]
                all_completed = True
                for req_d in req_depts:
                    if approvals.get(req_d, "") != "completed":
                        all_completed = False
                        break
                
                if current_status == "pending" and all_completed:
                    emails_to_send[dept_name].append(rec)
            else:
                if current_status == "pending":
                    emails_to_send[dept_name].append(rec)
                        
    # Send RM emails in batches
    rm_group_items = list(rm_groups.items())
    total_rm_emails = len(rm_group_items)
    
    success_count = 0
    failure_count = 0
    
    if total_rm_emails > 0:
        BATCH_SIZE = int(os.getenv("EMAIL_BATCH_SIZE", "10"))
        BATCH_DELAY = int(os.getenv("EMAIL_BATCH_DELAY_SECONDS", "30"))
        
        logger.info(f"Starting RM email send. Total unique RMs: {total_rm_emails}. Batch size: {BATCH_SIZE}. Batch delay: {BATCH_DELAY}s.")
        
        for i in range(0, total_rm_emails, BATCH_SIZE):
            batch = rm_group_items[i:i + BATCH_SIZE]
            logger.info(f"Sending RM email batch {i // BATCH_SIZE + 1} (emails {i+1} to {min(i + BATCH_SIZE, total_rm_emails)} of {total_rm_emails})...")
            
            for (rm_name, rm_email), recs in batch:
                try:
                    success = send_notification_email(recs, rm_email, "RM", manager_name=rm_name)
                    if success:
                        success_count += 1
                    else:
                        failure_count += 1
                except Exception as e:
                    logger.error(f"Failed to send email to RM '{rm_name}' ({rm_email}): {e}")
                    failure_count += 1
                await asyncio.sleep(2)
            
            if i + BATCH_SIZE < total_rm_emails:
                logger.info(f"Waiting for {BATCH_DELAY} seconds before next batch...")
                await asyncio.sleep(BATCH_DELAY)
                
        logger.info(f"RM Email Job Completed. Success: {success_count}, Failure: {failure_count}")
    else:
        logger.info("No pending RM records. Skipping RM emails.")
        
    # Send duplicate/conflicting RM records report to HR
    if duplicate_rm_records:
        hr_email = dept_email_map.get("hr")
        if hr_email:
            send_duplicate_managers_report(duplicate_rm_records, hr_email)
        else:
            logger.warning("Conflicting RM records found, but HR email is not configured in database.")
        await asyncio.sleep(2)
        
    # Send other department emails
    for dept_name, recipient in departments:
        if not recipient:
            logger.info(f"Skipping {dept_name} daily notification: recipient email is not configured.")
            continue
            
        records_for_dept = emails_to_send[dept_name]
        if records_for_dept:
            send_notification_email(records_for_dept, recipient, dept_name)
        else:
            logger.info(f"No pending records for {dept_name}. Skipping email.")


async def get_pending_records_for_tomorrow(stage_keyword: str):
    """Fetch NdcRecord instances where the specified stage is pending and last_working_date is tomorrow."""
    target_date = date.today() + timedelta(days=1)
    
    async with async_session() as session:
        query = (
            select(NdcRecord)
            .join(NdcApproval, NdcRecord.id == NdcApproval.ndc_record_id)
            .where(
                NdcApproval.stage_name.ilike(f"%{stage_keyword}%"),
                NdcApproval.status.ilike("PENDING"),
                NdcRecord.last_working_date == target_date
            )
            .distinct()
        )
        result = await session.execute(query)
        records = result.scalars().unique().all()
        
        # Ensure strict uniqueness by person_number
        unique_records = []
        seen_person_numbers = set()
        for r in records:
            if r.person_number not in seen_person_numbers:
                seen_person_numbers.add(r.person_number)
                unique_records.append(r)
                
        return unique_records


async def process_stage_for_tomorrow(keyword: str, recipient: str, stage_name: str):
    if not recipient:
        logger.info(f"Skipping {stage_name} tomorrow notification: recipient email is not configured.")
        return
        
    logger.info(f"Fetching pending {stage_name} records for tomorrow...")
    records = await get_pending_records_for_tomorrow(keyword)
    
    if not records:
        logger.info(f"No pending {stage_name} records found for tomorrow. Email not sent.")
        return
        
    logger.info(f"Found {len(records)} pending {stage_name} records for tomorrow. Sending email to {recipient}...")
    send_notification_email(records, recipient, stage_name, is_tomorrow=True)


async def run_tomorrow_alert_job():
    """Tomorrow Alert Job specifically for IT & Security pending actions."""
    logger.info("Starting Tomorrow Alerts (IT & Security) email job...")
    dept_email_map = {}
    async with async_session() as session:
        try:
            res = await session.execute(select(EmailRecipient))
            for rec in res.scalars().all():
                if rec.department and rec.email:
                    dept_email_map[rec.department.strip().lower()] = rec.email.strip()
        except Exception as e:
            logger.warning(f"Could not fetch department email recipients: {e}")

    # 1. Process IT Approvals for tomorrow
    await process_stage_for_tomorrow(
        keyword="IT", 
        recipient=dept_email_map.get("it"), 
        stage_name="IT"
    )
    
    # 2. Process Security Approvals for tomorrow
    await process_stage_for_tomorrow(
        keyword="Security", 
        recipient=dept_email_map.get("security"), 
        stage_name="Security"
    )

