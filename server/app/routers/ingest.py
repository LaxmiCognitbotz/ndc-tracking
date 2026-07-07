"""Ingest router — Excel upload and batch listing."""

import os
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

from database import get_db
from app.models.upload_batch import UploadBatch
from app.schemas.ndc import IngestResponse, BatchResponse
from app.auth.jwt_bearer import get_current_user
from app.services.ingest_service import ingest_excel_file

# Load environment variables from .env
load_dotenv(verbose=True)

# Load env variables
UPLOAD_DIR = os.getenv("UPLOAD_DIR")

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/upload-excel", response_model=IngestResponse)
async def upload_excel(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Upload an Excel file (.xlsb or .xlsx) for ingest."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in (".xlsb", ".xlsx", ".xls"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # Save file to disk
    upload_dir = Path(UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / file.filename

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    try:
        result = await ingest_excel_file(
            file_path=str(file_path),
            file_name=file.filename,
            uploaded_by=user.get("sub", "unknown"),
            db=db,
        )
    finally:
        if file_path.exists():
            try:
                os.remove(file_path)
            except Exception as e:
                # Fallback to ignore error if file can't be deleted immediately (e.g. permission or locking issue)
                pass

    return IngestResponse(**result)


@router.get("/batches", response_model=list[BatchResponse])
async def list_batches(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List all upload batches."""
    q = await db.execute(
        select(UploadBatch).order_by(UploadBatch.uploaded_at.desc())
    )
    return q.scalars().all()
