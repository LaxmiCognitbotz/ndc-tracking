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
