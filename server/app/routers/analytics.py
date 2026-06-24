"""Analytics router."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from app.schemas.ndc import (
    TatResponse, BottleneckResponse, DeptClearance, TrendPoint,
    DashboardSummary, OpenNdcBreakdown, ClosedNdcBreakdown,
    DelayedCasesBreakdown, DashboardDetailedMetrics,
)
from app.auth.jwt_bearer import get_current_user
from app.services.analytics_service import (
    get_tat_stats, get_bottlenecks, get_department_clearance, get_trends,
    get_dashboard_summary, get_open_ndc_breakdown, get_closed_ndc_breakdown,
    get_delayed_cases_breakdown, get_dashboard_detailed_metrics,
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


# Dashboard Metrics Endpoints

@router.get("/dashboard/summary", response_model=DashboardSummary)
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get dashboard summary metrics.
    
    Returns:
    - total_employee_exit_count: Total NDC records in system
    - open_ndc: Records in Recovery Pending or GCC Pending stages
    - closed_ndc: Records in NDC Completed stage
    - top_delayed_cases: Records overdue past last working date
    - in_progress_cases: Records in Recovery Pending stage
    - pending_approval: Records in GCC Pending stage
    - overdue: Records past last working date
    - avg_completion_time_days: Average TAT for completed NDCs
    """
    data = await get_dashboard_summary(db)
    return DashboardSummary(**data)


@router.get("/dashboard/open-ndc", response_model=OpenNdcBreakdown)
async def open_ndc_breakdown(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get breakdown of open NDC categories.
    
    Returns:
    - recovery_pending: NDCs in Recovery Pending stage
    - ndc_pending_with_gcc: NDCs in GCC Pending stage
    """
    data = await get_open_ndc_breakdown(db)
    return OpenNdcBreakdown(**data)


@router.get("/dashboard/closed-ndc", response_model=ClosedNdcBreakdown)
async def closed_ndc_breakdown(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get breakdown of closed NDC categories.
    
    Returns:
    - ff_done: F&F completed cases
    - ff_open: F&F open cases
    - ff_revision_required: F&F cases requiring revision
    
    Note: Requires additional F&F tracking fields in database schema.
    """
    data = await get_closed_ndc_breakdown(db)
    return ClosedNdcBreakdown(**data)


@router.get("/dashboard/delayed-cases", response_model=DelayedCasesBreakdown)
async def delayed_cases_breakdown(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get breakdown of delayed cases.
    
    Returns:
    - ndc_delay_cases: Delayed NDC processing cases
    - ff_delay_cases: Delayed F&F processing cases
    """
    data = await get_delayed_cases_breakdown(db)
    return DelayedCasesBreakdown(**data)


@router.get("/dashboard/detailed", response_model=DashboardDetailedMetrics)
async def dashboard_detailed(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get complete dashboard with all metrics in one call.
    
    Returns all dashboard metrics:
    - summary: Overall metrics
    - open_ndc_breakdown: Open NDC categories
    - closed_ndc_breakdown: Closed NDC categories
    - delayed_cases: Delayed case categories
    """
    data = await get_dashboard_detailed_metrics(db)
    return DashboardDetailedMetrics(**data)
