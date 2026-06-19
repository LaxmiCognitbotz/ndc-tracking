"""Export router — MIS Excel download."""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from app.auth.jwt_bearer import get_current_user
from app.services.export_service import generate_mis_excel

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/mis-excel")
async def download_mis_excel(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Download formatted MIS Excel report."""
    buf = await generate_mis_excel(db)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=NDC_MIS_Report.xlsx"},
    )
