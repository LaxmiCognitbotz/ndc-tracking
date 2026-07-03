import io
import re
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import pandas as pd

from database import get_db
from app.models.rm_email_configuration import RmEmailConfiguration

router = APIRouter(prefix="/api/v1", tags=["rm-email-configuration"])

class RmEmailCreate(BaseModel):
    rm_name: str
    email: str

@router.post("/rm-email-configuration")
async def create_rm_email_configuration(
    config: RmEmailCreate,
    db: AsyncSession = Depends(get_db)
):
    email_str = config.email.strip().lower()
    
    email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    if not re.match(email_regex, email_str):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    # Duplicate check
    res = await db.execute(select(RmEmailConfiguration).where(RmEmailConfiguration.email == email_str))
    existing = res.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail="RM with this email already exists")
        
    new_config = RmEmailConfiguration(
        rm_name=config.rm_name.strip(),
        email=email_str
    )
    db.add(new_config)
    await db.commit()
    
    return JSONResponse(content={
        "success": True,
        "message": "RM added successfully"
    })

@router.get("/rm-email-configuration")
async def get_rm_email_configurations(
    page: int = 1,
    limit: int = 10,
    search: str = "",
    db: AsyncSession = Depends(get_db)
):
    if page < 1:
        page = 1
    if limit < 1:
        limit = 10

    # Build select query
    query = select(RmEmailConfiguration)
    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.where(
            (RmEmailConfiguration.rm_name.ilike(search_pattern)) |
            (RmEmailConfiguration.email.ilike(search_pattern))
        )

    # Order by RM Name ascending
    query = query.order_by(RmEmailConfiguration.rm_name.asc())

    # Count total matching records
    count_q = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    # Offset & Limit pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    # Execute query
    res = await db.execute(query)
    records = res.scalars().all()

    # Map records to list of dicts
    data = [
        {
            "id": r.id,
            "rm_name": r.rm_name,
            "email": r.email,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None,
            "updated_at": r.updated_at.strftime("%Y-%m-%d %H:%M:%S") if r.updated_at else None
        }
        for r in records
    ]

    total_pages = (total + limit - 1) // limit if total > 0 else 0

    # Return standard JSONResponse to bypass default UnifiedJSONResponse wrapping
    return JSONResponse(content={
        "data": data,
        "page": page,
        "limit": limit,
        "total": total,
        "totalPages": total_pages
    })

@router.post("/rm-email-configuration/import")
async def import_rm_email_configurations(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = file.filename.split(".")[-1].lower()
    if ext not in ("xlsx", "xls"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: .{ext}. Only .xlsx and .xls are allowed.")

    try:
        content = await file.read()
        df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse Excel file: {str(e)}")

    # Clean and check columns
    df.columns = [str(col).strip() for col in df.columns]

    col_mapping = {}
    for col in df.columns:
        col_lower = col.lower()
        if col_lower == "rm name":
            col_mapping["rm_name"] = col
        elif col_lower == "email":
            col_mapping["email"] = col

    if "rm_name" not in col_mapping or "email" not in col_mapping:
        raise HTTPException(status_code=400, detail="Excel file must contain 'RM Name' and 'Email' columns.")

    inserted = 0
    skipped = 0
    failed = 0
    errors = []

    # Get all existing emails for duplicate checking
    res = await db.execute(select(RmEmailConfiguration.email))
    existing_emails = {e.lower() for e in res.scalars().all()}
    
    seen_emails = set()

    for idx, row in df.iterrows():
        row_num = idx + 2  # Row index starts at 2 (Row 1 is header)
        
        raw_rm_name = row[col_mapping["rm_name"]]
        raw_email = row[col_mapping["email"]]

        # Skip completely empty rows
        if pd.isna(raw_rm_name) and pd.isna(raw_email):
            continue

        rm_name_str = str(raw_rm_name).strip() if not pd.isna(raw_rm_name) else ""
        email_str = str(raw_email).strip().lower() if not pd.isna(raw_email) else ""

        if not rm_name_str and not email_str:
            continue

        # Validations
        if not rm_name_str:
            errors.append({"row": row_num, "message": "RM Name is required"})
            failed += 1
            continue

        if not email_str:
            errors.append({"row": row_num, "message": "Email is required"})
            failed += 1
            continue

        email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(email_regex, email_str):
            errors.append({"row": row_num, "message": "Invalid email format"})
            failed += 1
            continue

        # Duplicate check
        if email_str in existing_emails or email_str in seen_emails:
            skipped += 1
            continue

        seen_emails.add(email_str)
        new_config = RmEmailConfiguration(
            rm_name=rm_name_str,
            email=email_str
        )
        db.add(new_config)
        inserted += 1

    if inserted > 0:
        await db.commit()

    return JSONResponse(content={
        "success": True,
        "inserted": inserted,
        "skipped": skipped,
        "failed": failed,
        "errors": errors
    })

@router.get("/rm-email-configuration/sample")
async def download_sample(db: AsyncSession = Depends(get_db)):
    data = [
        {"RM Name": "RM North", "Email": "rmnorth@company.com"},
        {"RM Name": "RM West", "Email": "rmwest@company.com"}
    ]
    df = pd.DataFrame(data)

    output = io.BytesIO()
    # Write to Excel in memory
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sample")
    output.seek(0)

    headers = {
        'Content-Disposition': 'attachment; filename="sample_rm_email_configuration.xlsx"'
    }
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )

@router.delete("/rm-email-configuration/{id}")
async def delete_rm_email_configuration(id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(RmEmailConfiguration).where(RmEmailConfiguration.id == id))
    config = res.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="RM email configuration not found")
        
    await db.delete(config)
    await db.commit()
    
    return JSONResponse(content={
        "success": True,
        "message": "Record deleted successfully"
    })
