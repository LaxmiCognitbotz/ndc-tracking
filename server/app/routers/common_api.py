from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dto.common import CommonNDCRecord, FnfUpdateRequest
from app.services.common_service import fetch_common_records, update_fnf_status
from config.database import get_db

router = APIRouter(prefix="/api/v1", tags=["Exit Clearance & Settlement Operations"])


@router.get("/ndc-records", response_model=List[CommonNDCRecord])
async def get_all_ndc_records_for_common(
    db: AsyncSession = Depends(get_db),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    try:
        return await fetch_common_records(db, start_date, end_date)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}",
        )


@router.get("/fnf-records", response_model=List[CommonNDCRecord])
async def get_all_fnf_records_for_common(db: AsyncSession = Depends(get_db)):
    try:
        return await fetch_common_records(db)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}",
        )


@router.get("/analytics-records", response_model=List[CommonNDCRecord])
async def get_all_analytics_records_for_common(db: AsyncSession = Depends(get_db)):
    try:
        return await fetch_common_records(db)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}",
        )


@router.put("/ndc-records/{record_id}")
async def update_fnf_status_route(
    record_id: int,
    body: FnfUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update F&F status for a record. Triggers department date propagation on completion."""
    try:
        record = await update_fnf_status(record_id, body, db)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
        return {"status": "ok", "id": record_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}",
        )
