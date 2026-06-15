"""Ingest service — validate, normalize, upsert NDC records from parsed Excel rows."""

import logging
from pathlib import Path

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ndc_record import NdcRecord
from app.models.ndc_approval import NdcApproval
from app.models.upload_batch import UploadBatch
from app.services.excel_parser import read_excel
from app.utils.date_utils import excel_serial_to_date
from app.utils.status_mapper import APPROVAL_STAGES, normalize_status

logger = logging.getLogger(__name__)

# Required columns for validation
REQUIRED_COLUMNS = ["Person Number", "Name of an Employee", "NDC Stage"]
VALID_STAGES = {"Recovery Pending", "GCC Pending", "NDC Completed"}


async def ingest_excel_file(
    file_path: str | Path,
    file_name: str,
    uploaded_by: str,
    db: AsyncSession,
) -> dict:
    """Parse Excel file, validate, and upsert into DB. Returns ingest result dict."""

    # Create batch record
    batch = UploadBatch(
        file_name=file_name,
        source_type="manual",
        uploaded_by=uploaded_by,
        status="processing",
    )
    db.add(batch)
    await db.flush()
    batch_id = batch.id

    errors: list[str] = []
    records_processed = 0
    records_failed = 0

    try:
        rows = read_excel(file_path)
    except Exception as e:
        batch.status = "failed"
        batch.error_message = str(e)
        await db.commit()
        return {
            "batch_id": batch_id,
            "records_processed": 0,
            "records_failed": 0,
            "status": "failed",
            "errors": [f"Failed to parse file: {e}"],
        }

    if not rows:
        batch.status = "failed"
        batch.error_message = "No data rows found"
        await db.commit()
        return {
            "batch_id": batch_id,
            "records_processed": 0,
            "records_failed": 0,
            "status": "failed",
            "errors": ["No data rows found in file"],
        }

    # Validate column presence
    first_row_keys = set(rows[0].keys())
    missing = [c for c in REQUIRED_COLUMNS if c not in first_row_keys]
    if missing:
        batch.status = "failed"
        batch.error_message = f"Missing columns: {missing}"
        await db.commit()
        return {
            "batch_id": batch_id,
            "records_processed": 0,
            "records_failed": 0,
            "status": "failed",
            "errors": [f"Missing required columns: {missing}"],
        }

    for idx, row in enumerate(rows, start=2):  # row 2 = first data row in Excel
        try:
            person_number = row.get("Person Number")
            employee_name = row.get("Name of an Employee")
            ndc_stage = row.get("NDC Stage")

            # Row-level validation
            if not person_number:
                errors.append(f"Row {idx}: Missing Person Number")
                records_failed += 1
                continue
            if not employee_name:
                errors.append(f"Row {idx}: Missing Employee Name")
                records_failed += 1
                continue
            if ndc_stage and ndc_stage not in VALID_STAGES:
                errors.append(f"Row {idx}: Invalid NDC Stage '{ndc_stage}'")
                records_failed += 1
                continue

            person_number = int(float(person_number))

            # Upsert ndc_record
            result = await db.execute(
                select(NdcRecord).where(NdcRecord.person_number == person_number)
            )
            record = result.scalar_one_or_none()

            record_data = {
                "person_number": person_number,
                "employee_name": str(employee_name).strip(),
                "business_unit": _str_or_none(row.get("Business Unit")),
                "legal_employer": _str_or_none(row.get("Legal Employer")),
                "location": _str_or_none(row.get("Location")),
                "location_city": _str_or_none(row.get("Location City")),
                "department": _str_or_none(row.get("Department")),
                "department_reporting_name": _str_or_none(row.get("Department Reporting Name")),
                "ndc_stage": ndc_stage,
                "resignation_date": excel_serial_to_date(row.get("Resignation Date")),
                "last_working_date": excel_serial_to_date(row.get("Last Working Date")),
                "ndc_assigned_date": excel_serial_to_date(row.get("NDC Assigned date")),
                "ndc_initiated_date": excel_serial_to_date(row.get("NDC Initiated Date")),
                "ndc_completed_date": excel_serial_to_date(row.get("NDC Completed Date")),
                "created_by": _str_or_none(row.get("Created by")),
                "source_file": file_name,
                "batch_id": batch_id,
            }

            if record:
                for key, value in record_data.items():
                    setattr(record, key, value)
            else:
                record = NdcRecord(**record_data)
                db.add(record)

            await db.flush()

            # Delete existing approvals, then reinsert
            await db.execute(
                delete(NdcApproval).where(NdcApproval.ndc_record_id == record.id)
            )

            for stage_key, type_col, status_col, order in APPROVAL_STAGES:
                raw_status = row.get(status_col)
                approver = row.get(type_col)
                approval = NdcApproval(
                    ndc_record_id=record.id,
                    stage_name=stage_key,
                    approver_name=_str_or_none(approver),
                    status=normalize_status(raw_status) if raw_status else None,
                    sequence_order=order,
                )
                db.add(approval)

            records_processed += 1

        except Exception as e:
            logger.exception(f"Row {idx} failed: {e}")
            errors.append(f"Row {idx}: {e}")
            records_failed += 1

    # Update batch record
    batch.records_count = records_processed
    batch.status = "success" if records_failed == 0 else "partial"
    if errors:
        batch.error_message = "\n".join(errors[:50])  # cap stored errors

    await db.commit()

    return {
        "batch_id": batch_id,
        "records_processed": records_processed,
        "records_failed": records_failed,
        "status": batch.status,
        "errors": errors,
    }


def _str_or_none(val) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None
