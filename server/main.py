import asyncio
from contextlib import asynccontextmanager
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from app.routers import common_api, email_api, ff_api, rm_email_configuration_api, auth
from app.utils.response import (
    UnifiedJSONResponse,
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.utils.scheduler import (
    email_automation_loop,
    fnf_closed_report_loop,
    fnf_completed_sync_loop,
    sharepoint_sync_loop,
)

# Load env variables
load_dotenv(verbose=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Seed Super Admins
    from config.database import async_session
    from sqlalchemy import select
    from app.models.ndc_user_access import NdcUserAccess
    from datetime import datetime, timezone

    super_admin_env = os.getenv("SUPER_ADMIN_EMAIL", "")
    super_admins = [e.strip().lower() for e in super_admin_env.split(",") if e.strip()]

    async with async_session() as session:
        for sa_email in super_admins:
            stmt = select(NdcUserAccess).where(NdcUserAccess.email == sa_email)
            res = await session.execute(stmt)
            user_access = res.scalar_one_or_none()
            if not user_access:
                print(f"Seeding super admin: {sa_email}")
                user_access = NdcUserAccess(
                    email=sa_email,
                    name=sa_email.split('@')[0],
                    role="super_admin",
                    status="approved",
                    approved_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    approved_by="system"
                )
                session.add(user_access)
            else:
                print(f"Ensuring super admin privileges: {sa_email}")
                user_access.role = "super_admin"
                user_access.status = "approved"
                # Update attributes in-place to ensure SQLAlchemy flushes correctly
                session.add(user_access)
        await session.commit()

    # Start the background tasks
    bg_task = asyncio.create_task(sharepoint_sync_loop())
    fnf_bg_task = asyncio.create_task(fnf_completed_sync_loop())
    fnf_closed_task = asyncio.create_task(fnf_closed_report_loop())
    email_task = asyncio.create_task(email_automation_loop())
    yield
    # Cancel the background tasks on shutdown
    bg_task.cancel()
    fnf_bg_task.cancel()
    fnf_closed_task.cancel()
    email_task.cancel()
    try:
        await bg_task
    except asyncio.CancelledError:
        pass
    try:
        await fnf_bg_task
    except asyncio.CancelledError:
        pass
    try:
        await fnf_closed_task
    except asyncio.CancelledError:
        pass
    try:
        await email_task
    except asyncio.CancelledError:
        pass


tags_metadata = [
    {
        "name": "Health Check",
        "description": "Service health check endpoint.",
    },
    {
        "name": "Exit Clearance & Settlement Operations",
        "description": "API operations for managing exit clearances (NDC) and Full & Final (F&F) statuses.",
    },
    {
        "name": "Email Notification Management",
        "description": "Endpoints to view/modify alert recipients and manually trigger reminder/settlement emails.",
    },
    {
        "name": "Settlement Documents (SharePoint)",
        "description": "Integration to download and stream exit clearance documents from SharePoint folders.",
    },
    {
        "name": "Reporting Manager Email Configurations",
        "description": "Management of Reporting Manager names and their designated email addresses for automated reminders.",
    }
]


app = FastAPI(
    title="NDC/GCC Workflow Tracking API",
    version="1.0.0",
    description="Backend API for NDC/GCC workflow tracking and reporting",
    default_response_class=UnifiedJSONResponse,
    lifespan=lifespan,
    openapi_tags=tags_metadata,
)

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(common_api.router)
app.include_router(email_api.router)
app.include_router(ff_api.router)
app.include_router(rm_email_configuration_api.router)
app.include_router(auth.router)
app.include_router(auth.admin_router)


@app.get("/health", tags=["Health Check"])
async def health():
    return {"status": "ok"}


# --- FRONTEND SPA ROUTING ---
DIST_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "client", "dist")
)
os.makedirs(DIST_DIR, exist_ok=True)

# Known static file extensions — never serve index.html for these
STATIC_EXTENSIONS = {
    ".js",
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".map",
    ".json",
    ".webp",
}


def _serve_file_or_404(full_path: str):
    """Serve a static file from dist, or raise 404 if it's a static asset that doesn't exist."""
    file_path = os.path.join(DIST_DIR, full_path)
    _, ext = os.path.splitext(full_path)

    # If the file physically exists, serve it
    if full_path and os.path.isfile(file_path):
        return FileResponse(file_path)

    # If this looks like a static asset but doesn't exist, return 404 (NOT index.html)
    if ext.lower() in STATIC_EXTENSIONS:
        raise HTTPException(
            status_code=404, detail=f"Static file not found: {full_path}"
        )

    # For all other paths (page navigation), serve index.html for React Router
    index_path = os.path.join(DIST_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")

    raise HTTPException(
        status_code=404, detail="Frontend build not found. Run npm run build."
    )


@app.get("/")
async def serve_frontend_root():
    return _serve_file_or_404("")


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    return _serve_file_or_404(full_path)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8010, reload=True)
