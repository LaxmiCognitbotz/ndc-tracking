from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from pydantic import BaseModel
from datetime import date

from database import get_db
from app.models.email_recipient import EmailRecipient
from app.models.ndc_record import NdcRecord
from app.services.email_service import send_delayed_reminder, _days_delayed

router = APIRouter(prefix="/api/v1", tags=["email"])

class EmailRecipientSchema(BaseModel):
    id: str | None = None
    name: str
    email: str
    department: str
    role: str | None = None

    model_config = {"from_attributes": True}

@router.get("/email-recipients", response_model=List[EmailRecipientSchema])
async def get_email_recipients(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(EmailRecipient))
    records = res.scalars().all()
    # Map id to string to match client expectations
    return [EmailRecipientSchema(
        id=str(r.id),
        name=r.name,
        email=r.email,
        department=r.department,
        role=r.role or ""
    ) for r in records]

@router.post("/email-recipients")
async def add_email_recipient(recipient: EmailRecipientSchema, db: AsyncSession = Depends(get_db)):
    # Duplicate email check
    existing = await db.execute(
        select(EmailRecipient).where(EmailRecipient.email == recipient.email.strip().lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A recipient with this email already exists.")

    new_rec = EmailRecipient(
        name=recipient.name,
        email=recipient.email.strip().lower(),
        department=recipient.department,
        role=recipient.role
    )
    db.add(new_rec)
    await db.commit()
    return {"status": "success"}

@router.put("/email-recipients/{id}")
async def update_email_recipient(id: int, recipient: EmailRecipientSchema, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(EmailRecipient).where(EmailRecipient.id == id))
    rec = res.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")

    # Duplicate email check – exclude the current record from the check
    dup = await db.execute(
        select(EmailRecipient).where(
            EmailRecipient.email == recipient.email.strip().lower(),
            EmailRecipient.id != id
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Another recipient with this email already exists.")

    rec.name = recipient.name
    rec.email = recipient.email.strip().lower()
    rec.department = recipient.department
    rec.role = recipient.role
    await db.commit()
    return {"status": "success"}

@router.delete("/email-recipients/{id}")
async def delete_email_recipient(id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(EmailRecipient).where(EmailRecipient.id == id))
    rec = res.scalar_one_or_none()
    if rec:
        await db.delete(rec)
        await db.commit()
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/send-delayed-reminder")
async def send_delayed_reminder_email(
    db: AsyncSession = Depends(get_db),
):
    """Send a reminder email for the top 10 delayed NDC cases.

    Delayed = not NDC Completed AND last_working_date < today.
    Records are sorted by days delayed (most delayed first).
    """
    today = date.today()

    # Fetch all overdue non-completed records
    result = await db.execute(
        select(NdcRecord)
        .where(
            NdcRecord.ndc_stage != "NDC Completed",
            NdcRecord.last_working_date < today,
            NdcRecord.last_working_date.isnot(None),
        )
    )
    all_delayed = result.scalars().all()

    # Sort by days delayed desc, take top 10
    sorted_delayed = sorted(
        all_delayed,
        key=lambda r: _days_delayed(r.last_working_date),
        reverse=True,
    )
    top10 = sorted_delayed[:10]

    records_payload = [
        {
            "person_number": str(r.person_number),
            "employee_name": r.employee_name,
            "department": r.department or r.department_reporting_name or "—",
            "last_working_date": r.last_working_date,
            "days_delayed": _days_delayed(r.last_working_date),
        }
        for r in top10
    ]

    outcome = await send_delayed_reminder(
        records=records_payload,
    )

    if not outcome["success"]:
        raise HTTPException(status_code=500, detail=outcome["message"])

    return {"status": "success", "message": outcome["message"], "records_sent": len(top10)}


from app.models.ndc_approval import NdcApproval
from app.routers.common_api import _derive_fnf_status
from app.services.email_service import send_fnf_details_email

class FnfEmailRequest(BaseModel):
    email: str
    record_id: int

@router.post("/send-fnf-email")
async def send_fnf_email(
    payload: FnfEmailRequest,
    db: AsyncSession = Depends(get_db)
):
    # Fetch the record
    result = await db.execute(
        select(NdcRecord).where(NdcRecord.id == payload.record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    # Fetch record approvals
    approvals_res = await db.execute(
        select(NdcApproval).where(NdcApproval.ndc_record_id == record.id)
    )
    record_approvals = approvals_res.scalars().all()

    stage_key_map = {
        "RM Approval": "rm",
        "IT Approval": "it",
        "ABEX Approval": "abex",
        "Telecom Approval": "telecom",
        "Store Approval": "store",
        "Safety Approval": "safety",
        "Administration Approval": "administration",
        "Security Approval": "security",
        "HR Approval": "hr",
        "GCC HR Approval": "gcc_hr",
        "Final ABEX Approval": "final_abex",
        "Business Specific Approval": "business_specific",
        "Legatrix Approval": "legatrix",
    }

    # Check if an F&F document file exists on the server in the uploads folder
    from database import BASE_DIR
    fnf_doc_name = ""
    for ext in [".pdf", ".png", ".jpg", ".jpeg", ".docx", ".xlsx", ".xls"]:
        possible_file = f"{record.person_number}{ext}"
        possible_path = BASE_DIR / "uploads" / possible_file
        if possible_path.exists():
            fnf_doc_name = possible_file
            break

    # Base record fields
    record_dict = {
        "person_number": str(record.person_number),
        "employee_name": record.employee_name or "",
        "department": record.department or record.department_reporting_name or "—",
        "resignation_date": record.resignation_date,
        "last_working_date": record.last_working_date,
        "fnf_status": _derive_fnf_status(record),
        "fnf_completed_date": record.fnf_completed_date,
        "fnf_document_count": record.fnf_document_count,
        "fnf_document": fnf_doc_name,
    }

    # Initialize approvals with default
    for prefix in stage_key_map.values():
        record_dict[f"{prefix}_approval_status"] = "Not Applicable"
        record_dict[f"{prefix}_approval_date"] = ""

    # Populate approvals
    for approval in record_approvals:
        prefix = stage_key_map.get(approval.stage_name)
        if prefix:
            status_mapped = ""
            if approval.status == "PENDING": status_mapped = "Pending"
            elif approval.status == "IN_PROGRESS": status_mapped = "In Progress"
            elif approval.status == "COMPLETED": status_mapped = "Completed"
            elif approval.status == "NOT_APPLICABLE": status_mapped = "Not Applicable"
            else: status_mapped = approval.status.capitalize() if approval.status else "Not Applicable"

            record_dict[f"{prefix}_approval_status"] = status_mapped
            record_dict[f"{prefix}_approval_date"] = approval.stage_completed_at.strftime("%Y-%m-%d") if approval.stage_completed_at else ""

    outcome = await send_fnf_details_email(
        email_to=payload.email.strip(),
        record=record_dict
    )

    if not outcome["success"]:
        raise HTTPException(status_code=500, detail=outcome["message"])

    return {"status": "success", "message": outcome["message"]}
