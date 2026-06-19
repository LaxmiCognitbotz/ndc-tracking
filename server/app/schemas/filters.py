from datetime import date
from fastapi import Query


class NdcFilterParams:
    """Query parameter dependency for GET /ndc/records filters."""

    def __init__(
        self,
        ndc_stage: str | None = Query(None),
        business_unit: str | None = Query(None),
        legal_employer: str | None = Query(None),
        location: str | None = Query(None),
        location_city: str | None = Query(None),
        department_reporting_name: str | None = Query(None),
        approval_stage: str | None = Query(None),
        approval_status: str | None = Query(None),
        approver_name: str | None = Query(None),
        person_number: int | None = Query(None),
        employee_name: str | None = Query(None),
        has_gcc_pending: bool | None = Query(None),
        pending_days_min: int | None = Query(None),
        pending_days_max: int | None = Query(None),
        ndc_initiated_from: date | None = Query(None),
        ndc_initiated_to: date | None = Query(None),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        sort_by: str = Query("ndc_initiated_date"),
        sort_order: str = Query("desc"),
    ):
        self.ndc_stage = ndc_stage
        self.business_unit = business_unit
        self.legal_employer = legal_employer
        self.location = location
        self.location_city = location_city
        self.department_reporting_name = department_reporting_name
        self.approval_stage = approval_stage
        self.approval_status = approval_status
        self.approver_name = approver_name
        self.person_number = person_number
        self.employee_name = employee_name
        self.has_gcc_pending = has_gcc_pending
        self.pending_days_min = pending_days_min
        self.pending_days_max = pending_days_max
        self.ndc_initiated_from = ndc_initiated_from
        self.ndc_initiated_to = ndc_initiated_to
        self.page = page
        self.page_size = page_size
        self.sort_by = sort_by
        self.sort_order = sort_order
