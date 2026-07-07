import logging
from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
from app.services.sharepoint_service import SharePointService
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ff", tags=["fnf-sharepoint"])

# Create SharePoint Service instance
sharepoint_service = SharePointService()

@router.get("/download/{person_number}")
async def download_ff_document(person_number: str):
    """
    Downloads the F&F document for a given employee from SharePoint.
    If no file exists, returns 404.
    If multiple files exist, streams the first file found.
    """
    logger.info(f"Received SharePoint document download request for person: {person_number}")
    
    async with httpx.AsyncClient() as client:
        try:
            # 1. Resolve site ID
            site_id = await sharepoint_service.get_site_id(client)
            
            # 2. Resolve drive ID and target folder path
            drive_id, folder_path = await sharepoint_service.get_drive_details(client, site_id)
            
            # 3. Locate folder by person number and list files
            files, resolved_folder = await sharepoint_service.get_person_folder_files(
                client, site_id, drive_id, folder_path, person_number
            )
            
            if not files:
                logger.warning(f"No files found for person: {person_number} in SharePoint.")
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={
                        "success": False,
                        "message": "Document not found."
                    }
                )
                
            # 4. Stream either the single file or compile all into a zip archive
            if len(files) == 1:
                selected_file = files[0]
                stream, filename, mime_type = await sharepoint_service.get_download_stream(selected_file)
            else:
                stream, filename, mime_type = await sharepoint_service.get_zipped_download_stream(files, person_number)
            
            logger.info(f"Successfully located file '{filename}' for person {person_number} at path '{resolved_folder}'. Initiating stream.")
            
            headers = {
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition"  # Allows Axios to access the filename header
            }
            
            return StreamingResponse(
                stream,
                media_type=mime_type,
                headers=headers
            )
            
        except Exception as e:
            logger.exception(f"SharePoint download failed for person {person_number} due to exception: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False,
                    "message": f"SharePoint server error: {str(e)}"
                }
            )

@router.post("/sync")
async def sync_ff_completed_records(db: AsyncSession = Depends(get_db)):
    """
    Manually triggers F&F SharePoint folder sync to identify which employees
    have folders under F&F_Documents, and marks their status in the DB as completed.
    """
    from app.services.sharepoint_sync_service import SharePointSyncService
    sync_service = SharePointSyncService()
    result = await sync_service.sync_fnf_completed_records(db)
    return result
