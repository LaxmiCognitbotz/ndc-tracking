import asyncio
import os
import sys
from datetime import datetime

# Inject root folder into sys.path so we can import app modules
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from config.database import async_session
from app.helpers.ff.sharepoint_sync_service import SharePointSyncService

async def manual_sync():
    print("=" * 70)
    print(f"[START] Manual SharePoint Sync at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print("\nConnecting to SharePoint to check for new Excel files...")

    # Initialize the service
    try:
        sync_service = SharePointSyncService()
    except Exception as e:
        print(f"\n[ERROR] Failed to initialize SharePoint service: {e}")
        sys.exit(1)

    # Run the ingestion using the existing database session
    async with async_session() as db:
        try:
            print("Scanning target folder for updates...")
            results = await sync_service.check_and_ingest_new_files(db)
            
            print("\n" + "=" * 70)
            if results["status"] == "success":
                print("[SUCCESS] Sync Completed Successfully!")
                print(f"Files Found:      {results['files_found']}")
                print(f"Files Downloaded: {results['files_downloaded']}")
                print(f"Files Ingested:   {results['files_ingested']}")
            else:
                print("[FAILED] Sync encountered errors!")
            
            if results.get("details"):
                print("\nDetails:")
                for d in results["details"]:
                    print(f" - {d['file_name']}: {d['status'].upper()} ({d.get('message', '')})")
            
            if results.get("errors"):
                print("\nErrors encountered:")
                for err in results["errors"]:
                    print(f" - {err}")
                    
            print("=" * 70)
            
        except Exception as e:
            print(f"\n[CRITICAL ERROR] The sync process crashed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(manual_sync())
