"""Analytics router."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from app.schemas.ndc import TatResponse, BottleneckResponse, DeptClearance, TrendPoint
from app.auth.jwt_bearer import get_current_user
from app.services.analytics_service import (
    get_tat_stats, get_bottlenecks, get_department_clearance, get_trends,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/tat", response_model=TatResponse)
async def tat_metrics(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get turnaround time (TAT) metrics and stats."""
    data = await get_tat_stats(db)
    return TatResponse(**data)


@router.get("/bottlenecks", response_model=BottleneckResponse)
async def bottlenecks(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get stage-wise pending bottlenecks."""
    data = await get_bottlenecks(db)
    return BottleneckResponse(**data)


@router.get("/department-wise", response_model=list[DeptClearance])
async def department_wise(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get department-wise clearance counts."""
    data = await get_department_clearance(db)
    return [DeptClearance(**d) for d in data]


@router.get("/trends", response_model=list[TrendPoint])
async def trends(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get monthly trends for NDC completions and average days."""
    data = await get_trends(db)
    return [TrendPoint(**d) for d in data]
