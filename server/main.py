import asyncio
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Disable uvicorn access logs to reduce noise in production
# logging.getLogger("uvicorn.access").disabled = True

from app.helpers.startup.lifespan import lifespan
from app.modules.auth import router as auth_router
from app.modules.common import router as common_router
from app.modules.email import router as email_router
from app.modules.employee_email import router as employee_email_router
from app.modules.ff import router as ff_router
from app.modules.rm_email import router as rm_email_router
from app.modules.users import router as users_router
from app.utils.response import (
    UnifiedJSONResponse,
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from spa_server.router import router as spa_router

# Load env variables
load_dotenv(verbose=True)


app = FastAPI(
    title="NDC & GCC Workflow Management API",
    version="1.0.0",
    # description="Enterprise backend API for managing No Dues Certificates (NDC) and GCC workflows. Features automated email triggers, SharePoint integration for settlement records, and real-time status syncing.",
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


@app.get("/health", tags=["Health Check"])
async def health():
    return {"status": "ok"}


app.include_router(ff_router.router)
app.include_router(email_router.router)
app.include_router(rm_email_router.router)
app.include_router(employee_email_router.router)
app.include_router(auth_router.router)
app.include_router(users_router.admin_router)
app.include_router(common_router.router)


# Catch-all frontend router MUST be last to avoid swallowing API routes!
app.include_router(spa_router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8010, reload=True)
