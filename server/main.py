import os
import uvicorn
from fastapi import FastAPI
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

app = FastAPI(
    title="NDC/GCC Workflow Tracking API",
    version="1.0.0",
    description="Backend API for NDC/GCC workflow tracking and reporting",
    default_response_class=UnifiedJSONResponse,
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

from app.routers import common_api, email_api
app.include_router(common_api.router)
app.include_router(email_api.router)



@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/auth/dev-token")
async def dev_token(username: str = "admin"):
    """Development-only endpoint to generate a JWT for testing."""
    token = create_access_token({"sub": username, "role": "admin"})
    return {"access_token": token, "token_type": "bearer"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
