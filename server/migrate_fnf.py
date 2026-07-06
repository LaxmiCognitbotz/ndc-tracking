"""One-off migration to add explicit department date columns to ndc_records table."""
import asyncio
from dotenv import load_dotenv
load_dotenv()

from database import engine
from sqlalchemy import text


async def migrate():
    async with engine.begin() as conn:
        migrations = [
            "ALTER TABLE ndc_records ADD COLUMN IF NOT EXISTS rm_approval_date DATE",
            "ALTER TABLE ndc_records ADD COLUMN IF NOT EXISTS it_approval_date DATE",
            "ALTER TABLE ndc_records ADD COLUMN IF NOT EXISTS abex_approval_date DATE",
            "ALTER TABLE ndc_records ADD COLUMN IF NOT EXISTS telecom_approval_date DATE",
            "ALTER TABLE ndc_records ADD COLUMN IF NOT EXISTS store_approval_date DATE",
            "ALTER TABLE ndc_records ADD COLUMN IF NOT EXISTS safety_approval_date DATE",
            "ALTER TABLE ndc_records ADD COLUMN IF NOT EXISTS administration_approval_date DATE",
            "ALTER TABLE ndc_records ADD COLUMN IF NOT EXISTS security_approval_date DATE",
            "ALTER TABLE ndc_records ADD COLUMN IF NOT EXISTS hr_approval_date DATE",
            "ALTER TABLE ndc_records ADD COLUMN IF NOT EXISTS gcc_hr_approval_date DATE",
            "ALTER TABLE ndc_records ADD COLUMN IF NOT EXISTS final_abex_approval_date DATE",
            "ALTER TABLE ndc_records ADD COLUMN IF NOT EXISTS business_specific_approval_date DATE",
            "ALTER TABLE ndc_records ADD COLUMN IF NOT EXISTS legatrix_approval_date DATE",
            "ALTER TABLE ndc_records ADD COLUMN IF NOT EXISTS is_fnf_closed BOOLEAN NOT NULL DEFAULT FALSE",
        ]
        for sql in migrations:
            print(f"Running: {sql[:80]}...")
            await conn.execute(text(sql))
        print("Migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(migrate())
