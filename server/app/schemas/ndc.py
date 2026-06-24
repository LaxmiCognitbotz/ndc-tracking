from datetime import date, datetime
from pydantic import BaseModel


class NdcApprovalResponse(BaseModel):
    stage_name: str
    approver_name: str | None = None
    status: str | None = None
    sequence_order: int | None = None

    model_config = {"from_attributes": True}


class NdcRecordResponse(BaseModel):
    id: int
    person_number: int
    employee_name: str
    business_unit: str | None = None
    legal_employer: str | None = None
    location: str | None = None
    location_city: str | None = None
    department: str | None = None
    department_reporting_name: str | None = None
    ndc_stage: str | None = None
    resignation_date: date | None = None
    last_working_date: date | None = None
    ndc_assigned_date: date | None = None
    ndc_initiated_date: date | None = None
    ndc_completed_date: date | None = None
    created_by: str | None = None
    source_file: str | None = None
    batch_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    # Derived fields
    pending_days: int | None = None
    tat_days: int | None = None
    days_to_lwd: int | None = None

    model_config = {"from_attributes": True}


class NdcDetailResponse(NdcRecordResponse):
    approvals: list[NdcApprovalResponse] = []


class PaginatedResponse(BaseModel):
    items: list[NdcRecordResponse]
    total: int
    page: int
    page_size: int
    pages: int


class StageSummary(BaseModel):
    stage: str
    count: int


class NdcSummaryResponse(BaseModel):
    total_records: int
    stage_counts: list[StageSummary]
    total_pending: int
    gcc_pending_count: int


class BottleneckItem(BaseModel):
    stage_name: str
    pending_count: int


class ApproverBottleneck(BaseModel):
    approver_name: str | None
    stage_name: str
    pending_count: int


class BottleneckResponse(BaseModel):
    stage_wise: list[BottleneckItem]
    approver_wise: list[ApproverBottleneck]


class TatResponse(BaseModel):
    avg_tat_days: float | None
    min_tat_days: int | None
    max_tat_days: int | None
    completed_count: int
    total_count: int
    completion_rate: float


class DeptClearance(BaseModel):
    department: str
    total: int
    completed: int
    clearance_pct: float


class TrendPoint(BaseModel):
    date: date
    initiated: int
    completed: int


class BatchResponse(BaseModel):
    id: int
    file_name: str | None = None
    source_type: str | None = None
    records_count: int | None = None
    uploaded_by: str | None = None
    uploaded_at: datetime | None = None
    status: str | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}


class IngestResponse(BaseModel):
    batch_id: int
    records_processed: int
    records_failed: int
    status: str
    errors: list[str] = []


# Dashboard Metrics Schemas
class OpenNdcCategory(BaseModel):
    name: str
    count: int


class ClosedNdcCategory(BaseModel):
    name: str
    count: int


class DelayedCaseCategory(BaseModel):
    name: str
    count: int
    link: str | None = None


class DashboardSummary(BaseModel):
    total_employee_exit_count: int
    open_ndc: int
    closed_ndc: int
    top_delayed_cases: int
    in_progress_cases: int
    pending_approval: int
    overdue: int
    avg_completion_time_days: float | None


class OpenNdcBreakdown(BaseModel):
    recovery_pending: int
    ndc_pending_with_gcc: int


class ClosedNdcBreakdown(BaseModel):
    ff_done: int
    ff_open: int
    ff_revision_required: int


class DelayedCasesBreakdown(BaseModel):
    ndc_delay_cases: int
    ff_delay_cases: int


class DashboardDetailedMetrics(BaseModel):
    summary: DashboardSummary
    open_ndc_breakdown: OpenNdcBreakdown
    closed_ndc_breakdown: ClosedNdcBreakdown
    delayed_cases: DelayedCasesBreakdown
