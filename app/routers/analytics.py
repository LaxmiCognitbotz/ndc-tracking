"""Analytics router."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from app.schemas.ndc import (
    TatResponse, BottleneckResponse, DeptClearance, TrendPoint, PieChartResponse,
    NdcAnalysisResponse, ApprovalStageAnalysis, MonthlyTrendPoint,
    ClosedTatAnalysisResponse, DelayedCase,
)
from app.schemas.filters import NdcFilterParams
from app.auth.jwt_bearer import get_current_user
from app.services.analytics_service import (
    get_tat_stats, get_bottlenecks, get_department_clearance, get_trends,
    get_status_pie_data, get_ndc_analysis_data, get_approval_analysis_data,
    get_monthly_trend_data, get_closed_tat_analysis_data, get_top_delayed_cases,
    get_approval_departments,
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


@router.get("/status-pie", response_model=PieChartResponse)
async def status_pie(
    filters: NdcFilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get status counts (completed, pending, in progress) for the dashboard status pie/donut chart."""
    data = await get_status_pie_data(db, filters)
    return PieChartResponse(**data)


@router.get("/ndc-analysis", response_model=NdcAnalysisResponse)
async def ndc_analysis(
    filters: NdcFilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get counts of completed NDC records grouped by completion delay buckets (relative to LWD) for the dashboard bar chart."""
    data = await get_ndc_analysis_data(db, filters)
    return NdcAnalysisResponse(**data)


@router.get("/approval-analysis", response_model=list[ApprovalStageAnalysis])
async def approval_analysis(
    filters: NdcFilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get counts of completed and pending approvals grouped by approval stage/department."""
    data = await get_approval_analysis_data(db, filters)
    return [ApprovalStageAnalysis(**d) for d in data]


@router.get("/monthly-trend", response_model=list[MonthlyTrendPoint])
async def monthly_trend(
    filters: NdcFilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get monthly trends for NDC initiated vs completed clearances (counts and percentages)."""
    data = await get_monthly_trend_data(db, filters)
    return [MonthlyTrendPoint(**d) for d in data]


@router.get("/closed-tat-analysis", response_model=ClosedTatAnalysisResponse)
async def closed_tat_analysis(
    filters: NdcFilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get counts of completed NDC records grouped by TAT duration buckets (completed - initiated)."""
    data = await get_closed_tat_analysis_data(db, filters)
    return ClosedTatAnalysisResponse(**data)


@router.get("/top-delayed-cases", response_model=list[DelayedCase])
async def top_delayed_cases(
    category: str = "All",
    limit: int = 10,
    filters: NdcFilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get top delayed pending cases grouped by NDC and F&F categories."""
    data = await get_top_delayed_cases(db, filters, category=category, limit=limit)
    return [DelayedCase(**d) for d in data]


@router.get("/approval-departments", response_model=list[str])
async def approval_departments(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get distinct approval stage names for dropdown menus."""
    return await get_approval_departments(db)





