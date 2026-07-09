import asyncio
import logging
import sys
import os

from dotenv import load_dotenv

load_dotenv(verbose=True)

# Add the server directory to sys.path so 'app' and 'database' can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import async_session
from app.services.sharepoint_sync_service import SharePointSyncService

logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Suppress noisy logs from HTTP requests and token fetching
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("app.services.sharepoint_service").setLevel(logging.ERROR)
logging.getLogger("app.services.sharepoint_sync_service").setLevel(logging.WARNING)

async def run_report():
    sync_service = SharePointSyncService()
    async with async_session() as db:
        result = await sync_service.generate_and_upload_fnf_closed_report(db)
        
    if result.get("status") == "success":
        print(f"SUCCESS: Deleted old reports and uploaded '{result['uploaded_file_name']}' ({result['records_exported']} records).")
    else:
        print(f"FAILED: Could not upload report. Errors: {result.get('errors')}")

if __name__ == "__main__":
    asyncio.run(run_report())
