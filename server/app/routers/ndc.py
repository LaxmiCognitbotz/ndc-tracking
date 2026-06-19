"""NDC records router — filtered listing, detail, summary, bottlenecks."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from app.models.ndc_record import NdcRecord
from app.models.ndc_approval import NdcApproval
from app.schemas.filters import NdcFilterParams
from app.schemas.ndc import (
    NdcRecordResponse, NdcDetailResponse, NdcApprovalResponse,
    PaginatedResponse, NdcSummaryResponse, StageSummary, BottleneckItem,
)
from app.auth.jwt_bearer import get_current_user
from app.utils.date_utils import pending_days, tat_days, days_to_lwd

router = APIRouter(prefix="/ndc", tags=["ndc"])

# Sortable columns whitelist
SORT_COLUMNS = {
    "ndc_initiated_date": NdcRecord.ndc_initiated_date,
    "person_number": NdcRecord.person_number,
    "employee_name": NdcRecord.employee_name,
    "ndc_stage": NdcRecord.ndc_stage,
    "last_working_date": NdcRecord.last_working_date,
    "ndc_completed_date": NdcRecord.ndc_completed_date,
    "business_unit": NdcRecord.business_unit,
    "location_city": NdcRecord.location_city,
}


def _build_filtered_query(filters: NdcFilterParams):
    """Build a select query with all applicable filters."""
    query = select(NdcRecord)
    needs_approval_join = False

    # Direct column filters
    if filters.ndc_stage:
        query = query.where(NdcRecord.ndc_stage == filters.ndc_stage)
    if filters.business_unit:
        query = query.where(NdcRecord.business_unit == filters.business_unit)
    if filters.legal_employer:
        query = query.where(NdcRecord.legal_employer == filters.legal_employer)
    if filters.location:
        query = query.where(NdcRecord.location == filters.location)
    if filters.location_city:
        query = query.where(NdcRecord.location_city == filters.location_city)
    if filters.department_reporting_name:
        query = query.where(NdcRecord.department_reporting_name == filters.department_reporting_name)
    if filters.person_number:
        query = query.where(NdcRecord.person_number == filters.person_number)
    if filters.employee_name:
        query = query.where(NdcRecord.employee_name.ilike(f"%{filters.employee_name}%"))

    # Date range filters
    if filters.ndc_initiated_from:
        query = query.where(NdcRecord.ndc_initiated_date >= filters.ndc_initiated_from)
    if filters.ndc_initiated_to:
        query = query.where(NdcRecord.ndc_initiated_date <= filters.ndc_initiated_to)

    # Pending days filter (computed via DB current_date)
    if filters.pending_days_min is not None:
        query = query.where(
            (func.current_date() - NdcRecord.ndc_initiated_date) >= filters.pending_days_min
        )
    if filters.pending_days_max is not None:
        query = query.where(
            (func.current_date() - NdcRecord.ndc_initiated_date) <= filters.pending_days_max
        )

    # Approval-based filters — require join
    if filters.approval_stage or filters.approval_status or filters.approver_name:
        needs_approval_join = True
        query = query.join(NdcApproval, NdcApproval.ndc_record_id == NdcRecord.id)
        if filters.approval_stage:
            query = query.where(NdcApproval.stage_name == filters.approval_stage)
        if filters.approval_status:
            from app.utils.status_mapper import normalize_status
            normalized = normalize_status(filters.approval_status)
            query = query.where(NdcApproval.status == normalized)
        if filters.approver_name:
            query = query.where(NdcApproval.approver_name.ilike(f"%{filters.approver_name}%"))

    # GCC pending filter
    if filters.has_gcc_pending:
        if not needs_approval_join:
            query = query.join(NdcApproval, NdcApproval.ndc_record_id == NdcRecord.id)
        query = query.where(
            NdcApproval.stage_name == "GCC HR",
            NdcApproval.status.in_(["PENDING", "IN_PROGRESS"]),
        )

    return query.distinct()


@router.get("/records", response_model=PaginatedResponse)
async def list_records(
    filters: NdcFilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Paginated, filterable list of NDC records."""
    base_query = _build_filtered_query(filters)

    # Count
    count_q = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    # Sort
    sort_col = SORT_COLUMNS.get(filters.sort_by, NdcRecord.ndc_initiated_date)
    if filters.sort_order == "asc":
        base_query = base_query.order_by(sort_col.asc())
    else:
        base_query = base_query.order_by(sort_col.desc())

    # Paginate
    offset = (filters.page - 1) * filters.page_size
    base_query = base_query.offset(offset).limit(filters.page_size)

    result = await db.execute(base_query)
    records = result.scalars().all()

    today = date.today()
    items = []
    for r in records:
        resp = NdcRecordResponse.model_validate(r)
        resp.pending_days = pending_days(r.ndc_initiated_date) if r.ndc_stage != "NDC Completed" else None
        resp.tat_days = tat_days(r.ndc_initiated_date, r.ndc_completed_date)
        resp.days_to_lwd = days_to_lwd(r.last_working_date)
        items.append(resp)

    pages = (total + filters.page_size - 1) // filters.page_size if total > 0 else 0

    return PaginatedResponse(
        items=items,
        total=total,
        page=filters.page,
        page_size=filters.page_size,
        pages=pages,
    )


@router.get("/records/{person_number}", response_model=NdcDetailResponse)
async def get_record_detail(
    person_number: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Full detail for a single employee including all 13 approval stages."""
    result = await db.execute(
        select(NdcRecord).where(NdcRecord.person_number == person_number)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    approvals_q = await db.execute(
        select(NdcApproval)
        .where(NdcApproval.ndc_record_id == record.id)
        .order_by(NdcApproval.sequence_order)
    )
    approvals = approvals_q.scalars().all()

    resp = NdcDetailResponse.model_validate(record)
    resp.pending_days = pending_days(record.ndc_initiated_date) if record.ndc_stage != "NDC Completed" else None
    resp.tat_days = tat_days(record.ndc_initiated_date, record.ndc_completed_date)
    resp.days_to_lwd = days_to_lwd(record.last_working_date)
    resp.approvals = [NdcApprovalResponse.model_validate(a) for a in approvals]

    return resp


@router.get("/summary", response_model=NdcSummaryResponse)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Stage counts, pending counts, GCC pending count."""
    total_q = await db.execute(select(func.count()).select_from(NdcRecord))
    total = total_q.scalar() or 0

    stage_q = await db.execute(
        select(NdcRecord.ndc_stage, func.count().label("cnt"))
        .group_by(NdcRecord.ndc_stage)
    )
    stage_counts = [StageSummary(stage=r.ndc_stage, count=r.cnt) for r in stage_q.all()]

    pending_q = await db.execute(
        select(func.count()).select_from(NdcRecord)
        .where(NdcRecord.ndc_stage != "NDC Completed")
    )
    total_pending = pending_q.scalar() or 0

    gcc_q = await db.execute(
        select(func.count(distinct(NdcApproval.ndc_record_id)))
        .where(
            NdcApproval.stage_name == "GCC HR",
            NdcApproval.status.in_(["PENDING", "IN_PROGRESS"]),
        )
    )
    gcc_pending = gcc_q.scalar() or 0

    return NdcSummaryResponse(
        total_records=total,
        stage_counts=stage_counts,
        total_pending=total_pending,
        gcc_pending_count=gcc_pending,
    )


@router.get("/pending-bottlenecks", response_model=list[BottleneckItem])
async def pending_bottlenecks(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Stage-wise pending count ranked."""
    q = await db.execute(
        select(NdcApproval.stage_name, func.count().label("pending_count"))
        .where(NdcApproval.status == "PENDING")
        .group_by(NdcApproval.stage_name)
        .order_by(func.count().desc())
    )
    return [BottleneckItem(stage_name=r.stage_name, pending_count=r.pending_count) for r in q.all()]
