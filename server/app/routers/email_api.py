from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from pydantic import BaseModel

from database import get_db
from app.models.email_recipient import EmailRecipient

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
    # Map id to string to match frontend expectations
    return [EmailRecipientSchema(
        id=str(r.id),
        name=r.name,
        email=r.email,
        department=r.department,
        role=r.role or ""
    ) for r in records]

@router.post("/email-recipients")
async def add_email_recipient(recipient: EmailRecipientSchema, db: AsyncSession = Depends(get_db)):
    new_rec = EmailRecipient(
        name=recipient.name,
        email=recipient.email,
        department=recipient.department,
        role=recipient.role
    )
    db.add(new_rec)
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
