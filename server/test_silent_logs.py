import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(verbose=True)

from config.database import async_session
from app.models.ndc_record import NdcRecord
from app.modules.email.service import EmailService
from sqlalchemy import update
import logging

logging.basicConfig(level=logging.INFO)

async def run_test():
    pns = [30045476, 30115934, 30125168, 30126226, 30128233, 30141080, 30165032]
    
    async with async_session() as db:
        # Reset the 7 users
        stmt_reset = update(NdcRecord).where(NdcRecord.person_number.in_(pns)).values(is_fnf_email_sent=False)
        await db.execute(stmt_reset)
        await db.commit()
        print(f"Reset email_sent = False for {len(pns)} testing employees.")
        
        print("Now executing send_auto_fnf_emails to verify the logs are clean...")
        await EmailService.send_auto_fnf_emails(db)
        print("Execution complete!")

if __name__ == "__main__":
    asyncio.run(run_test())
