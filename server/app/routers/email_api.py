from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_recipient import EmailRecipient
from app.models.ndc_record import NdcRecord
from app.dto.email import EmailRecipientSchema, FnfEmailRequest, DelayedReminderRequest
from app.services.email_service import _days_delayed, send_delayed_reminder, send_fnf_email_service
from config.database import get_db

router = APIRouter(prefix="/api/v1", tags=["Email Notification Management"])


@router.get("/email-recipients", response_model=List[EmailRecipientSchema])
async def get_email_recipients(db: AsyncSession = Depends(get_db)):
    try:
        res = await db.execute(select(EmailRecipient))
        records = res.scalars().all()
        return [
            EmailRecipientSchema(
                id=str(r.id),
                name=r.name,
                email=r.email,
                department=r.department,
                role=r.role or "",
            )
            for r in records
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}",
        )


@router.post("/email-recipients")
async def add_email_recipient(
    recipient: EmailRecipientSchema, db: AsyncSession = Depends(get_db)
):
    try:
        # Duplicate email check
        existing = await db.execute(
            select(EmailRecipient).where(
                EmailRecipient.email == recipient.email.strip().lower()
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A recipient with this email already exists.",
            )

        new_rec = EmailRecipient(
            name=recipient.name,
            email=recipient.email.strip().lower(),
            department=recipient.department,
            role=recipient.role,
        )
        db.add(new_rec)
        await db.commit()
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}",
        )


@router.put("/email-recipients/{id}")
async def update_email_recipient(
    id: int, recipient: EmailRecipientSchema, db: AsyncSession = Depends(get_db)
):
    try:
        res = await db.execute(select(EmailRecipient).where(EmailRecipient.id == id))
        rec = res.scalar_one_or_none()
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
            )

        # Duplicate email check – exclude the current record from the check
        dup = await db.execute(
            select(EmailRecipient).where(
                EmailRecipient.email == recipient.email.strip().lower(),
                EmailRecipient.id != id,
            )
        )
        if dup.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another recipient with this email already exists.",
            )

        rec.name = recipient.name
        rec.email = recipient.email.strip().lower()
        rec.department = recipient.department
        rec.role = recipient.role
        await db.commit()
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}",
        )


@router.delete("/email-recipients/{id}")
async def delete_email_recipient(id: int, db: AsyncSession = Depends(get_db)):
    try:
        res = await db.execute(select(EmailRecipient).where(EmailRecipient.id == id))
        rec = res.scalar_one_or_none()
        if rec:
            await db.delete(rec)
            await db.commit()
            return {"status": "success"}
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}",
        )


@router.post("/send-delayed-reminder")
async def send_delayed_reminder_email(
    payload: DelayedReminderRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a reminder email for the top 10 delayed/overdue cases (NDC or F&F)."""
    try:
        today = date.today()

        # Fetch records based on type
        if payload.type == "fnf_open":
            # NDC Completed, but F&F is not completed and not revision
            result = await db.execute(
                select(NdcRecord).where(
                    NdcRecord.ndc_stage == "NDC Completed",
                    NdcRecord.is_fnf_completed == False,
                    NdcRecord.is_fnf_revision == False,
                )
            )
            records = result.scalars().all()
            sorted_records = sorted(
                records,
                key=lambda r: r.last_working_date or date.min,
                reverse=True,
            )
        elif payload.type == "fnf_revision":
            # NDC Completed, but F&F needs revision
            result = await db.execute(
                select(NdcRecord).where(
                    NdcRecord.ndc_stage == "NDC Completed",
                    NdcRecord.is_fnf_revision == True,
                )
            )
            records = result.scalars().all()
            sorted_records = sorted(
                records,
                key=lambda r: r.last_working_date or date.min,
                reverse=True,
            )
        else:
            # Default: ndc_delayed
            # Fetch all overdue non-completed records
            result = await db.execute(
                select(NdcRecord).where(
                    NdcRecord.ndc_stage != "NDC Completed",
                    NdcRecord.last_working_date < today,
                    NdcRecord.last_working_date.isnot(None),
                )
            )
            records = result.scalars().all()
            sorted_records = sorted(
                records,
                key=lambda r: _days_delayed(r.last_working_date),
                reverse=True,
            )

        top10 = sorted_records[:10]

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
            recipient=payload.email,
            reminder_type=payload.type or "ndc_delayed",
        )

        if not outcome["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=outcome["message"],
            )

        return {
            "status": "success",
            "message": outcome["message"],
            "records_sent": len(top10),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}",
        )


@router.post("/send-fnf-email")
async def send_fnf_email(
    payload: FnfEmailRequest, db: AsyncSession = Depends(get_db)
):
    try:
        outcome = await send_fnf_email_service(payload.record_id, payload.email, db)
        if not outcome["success"]:
            status_code = outcome.get("status_code", status.HTTP_500_INTERNAL_SERVER_ERROR)
            raise HTTPException(status_code=status_code, detail=outcome["message"])

        return {"status": "success", "message": outcome["message"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}",
        )
