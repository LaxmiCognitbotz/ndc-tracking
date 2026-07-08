import asyncio
from database import async_session
from app.models.ndc_record import NdcRecord
from sqlalchemy import select

async def f():
    async with async_session() as s:
        stmt = select(
            NdcRecord.person_number,
            NdcRecord.employee_name,
            NdcRecord.ndc_stage,
            NdcRecord.is_fnf_completed,
            NdcRecord.is_fnf_closed,
            NdcRecord.is_fnf_revision
        ).where(NdcRecord.ndc_stage == 'NDC Completed')
        r = await s.execute(stmt)
        print("NDC Completed records:")
        for row in r.fetchall():
            print(row)

asyncio.run(f())
