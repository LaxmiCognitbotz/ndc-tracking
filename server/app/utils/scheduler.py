import os
import asyncio
import logging
import datetime
from database import async_session
from app.services.sharepoint_sync_service import SharePointSyncService

logger = logging.getLogger(__name__)

async def sharepoint_sync_loop():
    """
    Background polling loop to check SharePoint and ingest new files at specific daily times.
    """
    enabled = os.getenv("SHAREPOINT_SYNC_BACKGROUND_POLL", "true").lower() == "true"
    if not enabled:
        logger.info("SharePoint background sync is disabled (SHAREPOINT_SYNC_BACKGROUND_POLL=false).")
        return

    # Parse configured scheduled times from env
    times_str = os.getenv("SHAREPOINT_SYNC_SCHEDULED_TIMES", "10:10,13:10,16:10,19:10")
    scheduled_times = {t.strip() for t in times_str.split(",") if t.strip()}
    logger.info(f"Starting SharePoint background sync scheduler. Triggers daily at: {', '.join(sorted(scheduled_times))}")
    
    sync_service = SharePointSyncService()
    
    # Store the last successfully triggered date & time key (e.g. "2026-07-07_10:10")
    last_trigger_key = None
    
    while True:
        try:
            now = datetime.datetime.now()
            time_str = now.strftime("%H:%M")
            date_str = now.strftime("%Y-%m-%d")
            current_trigger_key = f"{date_str}_{time_str}"
            
            if time_str in scheduled_times and current_trigger_key != last_trigger_key:
                logger.info(f"Background Scheduler: Time {time_str} reached. Initiating SharePoint sync...")
                last_trigger_key = current_trigger_key
                
                async with async_session() as db:
                    result = await sync_service.check_and_ingest_new_files(db)
                    fnf_result = await sync_service.sync_fnf_completed_records(db)
                    
                if result["files_ingested"] > 0:
                    logger.info(f"Background Scheduler: Successfully ingested {result['files_ingested']} new file(s).")
                elif result["status"] == "failed":
                    logger.error(f"Background Scheduler: SharePoint sync failed. Errors: {result['errors']}")
                else:
                    logger.info("Background Scheduler: No new files found on SharePoint.")

                if fnf_result["records_updated"] > 0:
                    logger.info(f"Background Scheduler: Successfully updated F&F completed status for {fnf_result['records_updated']} records.")
                elif fnf_result["status"] == "failed":
                    logger.error(f"Background Scheduler: SharePoint F&F sync failed. Errors: {fnf_result['errors']}")
                else:
                    logger.info("Background Scheduler: No new F&F folders found on SharePoint to update.")
                
        except asyncio.CancelledError:
            logger.info("Background Scheduler task cancelled.")
            break
        except Exception as e:
            logger.exception(f"Background Scheduler: Error during SharePoint sync check: {e}")
            
        # Check current time every 30 seconds
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            logger.info("Background Scheduler sleep cancelled.")
            break
