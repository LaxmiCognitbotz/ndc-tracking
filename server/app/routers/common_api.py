from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from database import get_db
from app.models.ndc_record import NdcRecord
from app.models.ndc_approval import NdcApproval
from app.schemas.common import CommonNDCRecord

router = APIRouter(prefix="/api/v1", tags=["common"])

async def fetch_common_records(db: AsyncSession) -> List[CommonNDCRecord]:
    # Fetch all records and approvals.
    records_res = await db.execute(select(NdcRecord).order_by(NdcRecord.ndc_initiated_date.desc()))
    records = records_res.scalars().all()
    
    approvals_res = await db.execute(select(NdcApproval))
    all_approvals = approvals_res.scalars().all()
    
    # Group approvals by record id for fast lookup
    approvals_by_record = {}
    for approval in all_approvals:
        if approval.ndc_record_id not in approvals_by_record:
            approvals_by_record[approval.ndc_record_id] = []
        approvals_by_record[approval.ndc_record_id].append(approval)

    result = []
    
    # Map stages to the specific properties client expects
    stage_key_map = {
        "RM": "rm", "IT": "it", "ABEX": "abex", "Telecom": "telecom", "Store": "store",
        "Safety": "safety", "Administration": "administration", "Security": "security",
        "HR": "hr", "GCC HR": "gcc_hr", "Final ABEX": "final_abex"
    }

    for record in records:
        record_approvals = approvals_by_record.get(record.id, [])
        item = {
            "id": str(record.id),
            "ndc_assigned_date": record.ndc_assigned_date.strftime("%Y-%m-%d") if record.ndc_assigned_date else "",
            "person_number": str(record.person_number),
            "employee_name": record.employee_name or "",
            "department": record.department or record.department_reporting_name or "",
            "ndc_stage": record.ndc_stage or "",
            "resignation_date": record.resignation_date.strftime("%Y-%m-%d") if record.resignation_date else "",
            "last_working_date": record.last_working_date.strftime("%Y-%m-%d") if record.last_working_date else "",
            "ndc_initiated_date": record.ndc_initiated_date.strftime("%Y-%m-%d") if record.ndc_initiated_date else "",
            "ndc_completed_date": record.ndc_completed_date.strftime("%Y-%m-%d") if record.ndc_completed_date else "",
            "created_by": record.created_by or "",
            "fnf_status": "", "fnf_document": "", "fnf_action_date": "", "fnf_completed_date": "",
            "recovery_pending_dept": "", "recovery_amount": 0.0, "recovery_status": "", "open_text_notes": ""
        }

        for prefix in stage_key_map.values():
            item[f"{prefix}_approval_status"] = "Not Applicable"
            item[f"{prefix}_approver"] = ""
            item[f"{prefix}_approval_date"] = ""

        for approval in record_approvals:
            prefix = stage_key_map.get(approval.stage_name)
            if prefix:
                status_mapped = ""
                if approval.status == "PENDING": status_mapped = "Pending"
                elif approval.status == "IN_PROGRESS": status_mapped = "In Progress"
                elif approval.status == "COMPLETED": status_mapped = "Completed"
                elif approval.status == "NOT_APPLICABLE": status_mapped = "Not Applicable"
                else: status_mapped = approval.status.capitalize() if approval.status else "Not Applicable"

                item[f"{prefix}_approval_status"] = status_mapped
                item[f"{prefix}_approver"] = approval.approver_name or ""
                item[f"{prefix}_approval_date"] = approval.stage_completed_at.strftime("%Y-%m-%d") if approval.stage_completed_at else ""

        result.append(CommonNDCRecord(**item))
    return result

@router.get("/ndc-records", response_model=List[CommonNDCRecord])
async def get_all_ndc_records_for_common(db: AsyncSession = Depends(get_db)):
    return await fetch_common_records(db)

@router.get("/fnf-records", response_model=List[CommonNDCRecord])
async def get_all_fnf_records_for_common(db: AsyncSession = Depends(get_db)):
    return await fetch_common_records(db)

@router.get("/analytics-records", response_model=List[CommonNDCRecord])
async def get_all_analytics_records_for_common(db: AsyncSession = Depends(get_db)):
    return await fetch_common_records(db)

