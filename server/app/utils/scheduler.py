import asyncio
import datetime
import importlib
import logging
import os
from pathlib import Path
import sys

from app.services.sharepoint_sync_service import SharePointSyncService
from config.database import async_session

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
                    
                if result["files_ingested"] > 0:
                    logger.info(f"Background Scheduler: Successfully ingested {result['files_ingested']} new file(s).")
                elif result["status"] == "failed":
                    logger.error(f"Background Scheduler: SharePoint sync failed. Errors: {result['errors']}")
                else:
                    logger.info("Background Scheduler: No new files found on SharePoint.")
                
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

async def fnf_completed_sync_loop():
    """
    Background polling loop to sync F&F completed status from SharePoint every 30 minutes.
    """
    enabled = os.getenv("SHAREPOINT_SYNC_BACKGROUND_POLL", "true").lower() == "true"
    if not enabled:
        logger.info("F&F SharePoint background sync is disabled (SHAREPOINT_SYNC_BACKGROUND_POLL=false).")
        return

    logger.info("Starting F&F SharePoint completed sync scheduler. Triggers every 30 minutes.")
    sync_service = SharePointSyncService()
    
    while True:
        try:
            logger.info("Background F&F Scheduler: Initiating sync...")
            async with async_session() as db:
                fnf_result = await sync_service.sync_fnf_completed_records(db)
                try:
                    from app.services.email_service import send_auto_fnf_emails
                    await send_auto_fnf_emails(db)
                except Exception as ex:
                    logger.exception(f"Background F&F Scheduler: Error during auto email sending: {ex}")
                
            if fnf_result["records_updated"] > 0 or fnf_result.get("records_reverted", 0) > 0:
                logger.info(f"Background F&F Scheduler: Successfully synced F&F status - Completed: {fnf_result['records_updated']}, Reverted: {fnf_result.get('records_reverted', 0)}.")
            elif fnf_result["status"] == "failed":
                logger.error(f"Background F&F Scheduler: Sync failed. Errors: {fnf_result['errors']}")
            else:
                logger.info("Background F&F Scheduler: No F&F status changes detected.")
                
        except asyncio.CancelledError:
            logger.info("Background F&F Scheduler task cancelled.")
            break
        except Exception as e:
            logger.exception(f"Background F&F Scheduler: Error during sync: {e}")
            
        # Sleep for 30 minutes (30 * 60 = 1800 seconds)
        try:
            await asyncio.sleep(1800)
        except asyncio.CancelledError:
            logger.info("Background F&F Scheduler sleep cancelled.")
            break


async def fnf_closed_report_loop():
    """
    Background polling loop that generates a FNF-Closed Excel report and uploads
    it to SharePoint at the same daily times as the SharePoint file-sync loop
    (controlled by SHAREPOINT_SYNC_SCHEDULED_TIMES env var).
    """
    enabled = os.getenv("SHAREPOINT_SYNC_BACKGROUND_POLL", "true").lower() == "true"
    if not enabled:
        logger.info("FNF Closed Report scheduler is disabled (SHAREPOINT_SYNC_BACKGROUND_POLL=false).")
        return

    # Re-use the same scheduled times as the main SharePoint sync
    times_str = os.getenv("SHAREPOINT_SYNC_SCHEDULED_TIMES", "10:10,13:10,16:10,19:10")
    scheduled_times = {t.strip() for t in times_str.split(",") if t.strip()}
    logger.info(
        f"Starting FNF Closed Report scheduler. Triggers daily at: {', '.join(sorted(scheduled_times))}"
    )

    sync_service = SharePointSyncService()
    last_trigger_key = None

    while True:
        try:
            now = datetime.datetime.now()
            time_str = now.strftime("%H:%M")
            date_str = now.strftime("%Y-%m-%d")
            current_trigger_key = f"{date_str}_{time_str}"

            if time_str in scheduled_times and current_trigger_key != last_trigger_key:
                logger.info(
                    f"FNF Closed Report Scheduler: Time {time_str} reached. Generating & uploading report..."
                )
                last_trigger_key = current_trigger_key

                async with async_session() as db:
                    result = await sync_service.generate_and_upload_fnf_closed_report(db)

                if result["status"] == "success":
                    logger.info(
                        f"FNF Closed Report Scheduler: Report '{result['uploaded_file_name']}' uploaded "
                        f"with {result['records_exported']} record(s)."
                    )
                else:
                    logger.error(
                        f"FNF Closed Report Scheduler: Report generation/upload failed. "
                        f"Errors: {result['errors']}"
                    )

        except asyncio.CancelledError:
            logger.info("FNF Closed Report Scheduler task cancelled.")
            break
        except Exception as e:
            logger.exception(f"FNF Closed Report Scheduler: Unexpected error: {e}")

        # Check every 30 seconds (same cadence as the main sync loop)
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            logger.info("FNF Closed Report Scheduler sleep cancelled.")
            break


async def email_automation_loop():
    """
    Background polling loop that triggers consolidated daily emails and tomorrow alerts at 10:00 AM.
    """
    enabled = os.getenv("EMAIL_AUTOMATION_BACKGROUND_POLL", "true").lower() == "true"
    if not enabled:
        logger.info("Email automation background sync is disabled (EMAIL_AUTOMATION_BACKGROUND_POLL=false).")
        return

    logger.info("Starting Daily Email Automation scheduler. Triggers daily at 10:00 AM.")

    from app.services.email_service import run_10am_job, run_tomorrow_alert_job

    # Store the last successfully triggered date
    last_trigger_date = None

    while True:
        try:
            now = datetime.datetime.now()
            time_str = now.strftime("%H:%M")
            date_str = now.strftime("%Y-%m-%d")

            # Check if it is 10:00 AM and we haven't triggered today yet
            if time_str == "10:00" and date_str != last_trigger_date:
                logger.info("Background Email Scheduler: 10:00 AM reached. Initiating daily email jobs...")
                last_trigger_date = date_str

                await run_10am_job()
                await asyncio.sleep(5)  # Brief pause between tasks to avoid SMTP throttling
                await run_tomorrow_alert_job()
                logger.info("Background Email Scheduler: Daily email jobs completed successfully.")

        except asyncio.CancelledError:
            logger.info("Background Email Scheduler task cancelled.")
            break
        except Exception as e:
            logger.exception(f"Background Email Scheduler: Unexpected error: {e}")

        # Check every 30 seconds
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            logger.info("Background Email Scheduler sleep cancelled.")
            break
