"""Fast backfill of explicit date columns on ndc_records from ndc_approvals."""
import asyncio
from dotenv import load_dotenv
load_dotenv()

from database import engine
from sqlalchemy import text

col_name_map = {
    "RM": "rm_approval_date",
    "IT": "it_approval_date",
    "Abex": "abex_approval_date",
    "Telecom": "telecom_approval_date",
    "Store": "store_approval_date",
    "Safety": "safety_approval_date",
    "Administration": "administration_approval_date",
    "Security": "security_approval_date",
    "HR": "hr_approval_date",
    "GCC HR": "gcc_hr_approval_date",
    "Final Abex": "final_abex_approval_date",
    "Business Specific": "business_specific_approval_date",
    "Legatrix": "legatrix_approval_date"
}

async def backfill():
    async with engine.begin() as conn:
        for stage_name, col_name in col_name_map.items():
            sql = f"""
                UPDATE ndc_records
                SET {col_name} = a.stage_completed_at
                FROM ndc_approvals a
                WHERE a.ndc_record_id = ndc_records.id
                AND a.stage_name = :stage_name
                AND a.stage_completed_at IS NOT NULL
            """
            result = await conn.execute(text(sql), {"stage_name": stage_name})
            print(f"Updated {result.rowcount} records for {stage_name} ({col_name})")
        
        print("Backfill completed successfully!")

if __name__ == "__main__":
    asyncio.run(backfill())
