import asyncio
import datetime
import logging
import os

from app.helpers.ff.sharepoint_sync_service import SharePointSyncService
from config.database import async_session

logger = logging.getLogger(__name__)

async def email_automation_loop():
    """
    Background polling loop that triggers consolidated daily emails and tomorrow alerts at 10:00 AM.
    """
    enabled = os.getenv("EMAIL_AUTOMATION_BACKGROUND_POLL", "true").lower() == "true"
    if not enabled:
        logger.info("Email automation background sync is disabled (EMAIL_AUTOMATION_BACKGROUND_POLL=false).")
        return

    logger.info("Starting Daily Email Automation scheduler. Triggers daily at 10:00 AM.")

    from app.modules.email.service import EmailService

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

                await EmailService.run_10am_job()
                await asyncio.sleep(5)  # Brief pause between tasks to avoid SMTP throttling
                await EmailService.run_tomorrow_alert_job()
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
