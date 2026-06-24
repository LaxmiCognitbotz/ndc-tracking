"""One-off script to directly ingest a local Excel file into the database."""
import asyncio
from dotenv import load_dotenv
load_dotenv()

from database import async_session
from app.services.ingest_service import ingest_excel_file

FILE_PATH = r"C:\NDC\NDC_Process_Request_Status_10_June_2026_03.24PM.xls"
FILE_NAME = "NDC_Process_Request_Status_10_June_2026_03.24PM.xls"

async def main():
    print(f"Ingesting: {FILE_NAME}")
    async with async_session() as db:
        result = await ingest_excel_file(
            file_path=FILE_PATH,
            file_name=FILE_NAME,
            uploaded_by="admin",
            db=db,
        )
    print("\n=== Ingest Result ===")
    print(f"  Batch ID        : {result['batch_id']}")
    print(f"  Records OK      : {result['records_processed']}")
    print(f"  Records Failed  : {result['records_failed']}")
    print(f"  Status          : {result['status']}")
    if result['errors']:
        print(f"\n  Errors ({len(result['errors'])}):")
        for e in result['errors'][:20]:
            print(f"    - {e}")

if __name__ == "__main__":
    asyncio.run(main())
