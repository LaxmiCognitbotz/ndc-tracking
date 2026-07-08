import os
import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load env variables
load_dotenv(verbose=True)

from app.routers import ingest, ndc, analytics, export
from app.auth.jwt_handler import create_access_token
from app.utils.response import (
    UnifiedJSONResponse,
    validation_exception_handler,
    http_exception_handler,
    general_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException
from app.utils.scheduler import sharepoint_sync_loop, fnf_completed_sync_loop, fnf_closed_report_loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the background tasks
    bg_task = asyncio.create_task(sharepoint_sync_loop())
    fnf_bg_task = asyncio.create_task(fnf_completed_sync_loop())
    fnf_closed_task = asyncio.create_task(fnf_closed_report_loop())
    yield
    # Cancel the background tasks on shutdown
    bg_task.cancel()
    fnf_bg_task.cancel()
    fnf_closed_task.cancel()
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

app = FastAPI(
    title="NDC/GCC Workflow Tracking API",
    version="1.0.0",
    description="Backend API for NDC/GCC workflow tracking and reporting",
    default_response_class=UnifiedJSONResponse,
    lifespan=lifespan,
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

app.include_router(ingest.router)
app.include_router(ndc.router)
app.include_router(analytics.router)
app.include_router(export.router)

from app.routers import common_api, email_api, ff, rm_email_configuration_api
app.include_router(common_api.router)
app.include_router(email_api.router)
app.include_router(ff.router)
app.include_router(rm_email_configuration_api.router)



@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/auth/dev-token")
async def dev_token(username: str = "admin"):
    """Development-only endpoint to generate a JWT for testing."""
    token = create_access_token({"sub": username, "role": "admin"})
    return {"access_token": token, "token_type": "bearer"}


# --- FRONTEND SPA ROUTING ---
DIST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "client", "dist"))
os.makedirs(DIST_DIR, exist_ok=True)
print(f"[SPA] DIST_DIR = {DIST_DIR}")
print(f"[SPA] DIST_DIR exists = {os.path.exists(DIST_DIR)}")
if os.path.exists(os.path.join(DIST_DIR, "assets")):
    print(f"[SPA] Assets: {os.listdir(os.path.join(DIST_DIR, 'assets'))}")

# Known static file extensions — never serve index.html for these
STATIC_EXTENSIONS = {
    ".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".map", ".json", ".webp",
}


def _serve_file_or_404(full_path: str):
    """Serve a static file from dist, or raise 404 if it's a static asset that doesn't exist."""
    file_path = os.path.join(DIST_DIR, full_path)
    _, ext = os.path.splitext(full_path)

    # If the file physically exists, serve it
    if full_path and os.path.isfile(file_path):
        print(f"[SPA] ✅ Serving: {file_path}")
        return FileResponse(file_path)

    # If this looks like a static asset but doesn't exist, return 404 (NOT index.html)
    if ext.lower() in STATIC_EXTENSIONS:
        print(f"[SPA] ❌ Static file NOT FOUND: {file_path}")
        raise HTTPException(status_code=404, detail=f"Static file not found: {full_path}")

    # For all other paths (page navigation), serve index.html for React Router
    index_path = os.path.join(DIST_DIR, "index.html")
    if os.path.exists(index_path):
        print(f"[SPA] 📄 SPA fallback for: /{full_path}")
        return FileResponse(index_path, media_type="text/html")

    raise HTTPException(status_code=404, detail="Frontend build not found. Run npm run build.")


@app.get("/")
async def serve_frontend_root():
    return _serve_file_or_404("")


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    return _serve_file_or_404(full_path)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8010, reload=True)

