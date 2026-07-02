import os
import logging
import asyncio
import msal
import httpx
import urllib.parse
from typing import AsyncGenerator, Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)

class SharePointService:
    def __init__(self):
        # Cached properties to avoid repeating site/drive lookups
        self._site_id: Optional[str] = None
        self._drive_id: Optional[str] = None

    @property
    def tenant_id(self) -> str:
        val = os.getenv("SHAREPOINT_TENANT_ID")
        if not val:
            raise Exception("SHAREPOINT_TENANT_ID environment variable is missing.")
        return val

    @property
    def client_id(self) -> str:
        val = os.getenv("SHAREPOINT_CLIENT_ID")
        if not val:
            raise Exception("SHAREPOINT_CLIENT_ID environment variable is missing.")
        return val

    @property
    def client_secret(self) -> str:
        val = os.getenv("SHAREPOINT_CLIENT_SECRET")
        if not val:
            raise Exception("SHAREPOINT_CLIENT_SECRET environment variable is missing.")
        return val

    @property
    def site_url(self) -> str:
        val = os.getenv("SHAREPOINT_SITE_URL")
        if not val:
            raise Exception("SHAREPOINT_SITE_URL environment variable is missing.")
        return val

    @property
    def target_folder(self) -> str:
        val = os.getenv("SHAREPOINT_TARGET_FOLDER")
        if not val:
            raise Exception("SHAREPOINT_TARGET_FOLDER environment variable is missing.")
        return val

    @property
    def authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}"

    @property
    def scopes(self) -> list[str]:
        return ["https://graph.microsoft.com/.default"]

    async def get_access_token(self) -> str:
        """Obtain a Microsoft Graph API access token using client credentials flow."""
        if not self.tenant_id or not self.client_id or not self.client_secret:
            raise Exception("SharePoint credentials are not configured in environment variables.")

        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret
        )
        
        # First check MSAL internal cache
        result = app.acquire_token_silent(self.scopes, account=None)
        if not result:
            logger.info("No cached token found. Requesting a new token from Azure AD.")
            # Run the synchronous token fetch in a thread pool to keep FastAPI non-blocking
            result = await asyncio.to_thread(
                app.acquire_token_for_client,
                scopes=self.scopes
            )
            
        if "access_token" in result:
            return result["access_token"]
        else:
            error_msg = result.get("error_description") or result.get("error") or "Unknown error"
            logger.error(f"SharePoint authentication failed: {error_msg}")
            raise Exception(f"SharePoint authentication failed: {error_msg}")

    async def get_site_id(self, client: httpx.AsyncClient) -> str:
        """Resolve the SharePoint Site ID from the SHAREPOINT_SITE_URL."""
        if self._site_id:
            return self._site_id

        if not self.site_url:
            raise Exception("SHAREPOINT_SITE_URL is not configured.")

        parsed_url = urllib.parse.urlparse(self.site_url)
        hostname = parsed_url.netloc
        relative_path = parsed_url.path.rstrip("/")
        
        token = await self.get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # Graph API format for sites: sites/{hostname}:/{relative-path}
        url = f"https://graph.microsoft.com/v1.0/sites/{hostname}:{relative_path}"
        logger.info(f"Resolving Site ID from URL: {url}")
        
        response = await client.get(url, headers=headers)
        if response.status_code != 200:
            logger.error(f"Failed to resolve site ID. Status: {response.status_code}, Body: {response.text}")
            raise Exception(f"Failed to resolve site ID: {response.status_code} - {response.text}")
            
        site_data = response.json()
        self._site_id = site_data.get("id")
        if not self._site_id:
            raise Exception("Site details resolved but 'id' field is missing.")
            
        logger.info(f"Resolved Site ID: {self._site_id}")
        return self._site_id

    async def get_drive_details(self, client: httpx.AsyncClient, site_id: str) -> Tuple[str, str]:
        """
        Resolves the Drive ID (Document Library ID) and the base folder path inside that drive
        from the SHAREPOINT_TARGET_FOLDER environment variable.
        """
        if self._drive_id:
            # Recompute folder path since it depends on target_folder
            pass

        if not self.target_folder:
            raise Exception("SHAREPOINT_TARGET_FOLDER is not configured.")

        # Determine relative folder after the site prefix
        parsed_site = urllib.parse.urlparse(self.site_url)
        site_path = parsed_site.path.rstrip("/")
        
        folder = self.target_folder
        if folder.startswith(site_path):
            folder = folder[len(site_path):]
        folder = folder.strip("/")
        
        # Split target folder path. e.g. "Shared Documents/AI_AGEL/001_AI_Project/AI05_NDC_Tracker"
        parts = [p for p in folder.split("/") if p]
        if not parts:
            drive_name = "Shared Documents"
            folder_path_in_drive = ""
        else:
            drive_name = parts[0]
            folder_path_in_drive = "/".join(parts[1:])
            
        logger.info(f"Target drive name: '{drive_name}', path inside drive: '{folder_path_in_drive}'")
        
        token = await self.get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # Fetch drives list to map drive_name to drive_id
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
        response = await client.get(url, headers=headers)
        if response.status_code != 200:
            logger.error(f"Failed to list drives. Status: {response.status_code}, Body: {response.text}")
            raise Exception(f"Failed to list drives: {response.status_code}")
            
        drives = response.json().get("value", [])
        drive_id = None
        for d in drives:
            if d.get("name") == drive_name:
                drive_id = d.get("id")
                break
                
        if not drive_id:
            logger.warning(f"Drive '{drive_name}' not found in drives list. Falling back to site default drive.")
            default_drive_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive"
            res = await client.get(default_drive_url, headers=headers)
            if res.status_code == 200:
                drive_id = res.json().get("id")
            else:
                raise Exception(f"Failed to resolve document library '{drive_name}' or site default drive: {res.text}")
                
        self._drive_id = drive_id
        logger.info(f"Resolved Drive ID: {self._drive_id}")
        return drive_id, folder_path_in_drive

    def _encode_path_segments(self, path: str) -> str:
        """Safely URL-encodes each path segment individually, preserving slashes."""
        segments = [urllib.parse.quote(s) for s in path.split("/") if s]
        return "/".join(segments)

    async def get_person_folder_files(
        self, client: httpx.AsyncClient, site_id: str, drive_id: str, folder_path_in_drive: str, person_number: str
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Locates the employee folder by person number and lists all files within it.
        Checks multiple candidate paths to support cases with or without a nested 'F&F_Documents' directory.
        Returns a tuple: (list of file items, successfully resolved folder path).
        """
        token = await self.get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # We check two main path structures:
        # 1. {folder_path_in_drive}/F&F_Documents/{person_number} (most likely structure)
        # 2. {folder_path_in_drive}/{person_number} (fallback structure)
        candidates = []
        if folder_path_in_drive:
            if "F&F_Documents" not in folder_path_in_drive:
                candidates.append(f"{folder_path_in_drive}/F&F_Documents/{person_number}")
            candidates.append(f"{folder_path_in_drive}/{person_number}")
        else:
            candidates.append(f"F&F_Documents/{person_number}")
            candidates.append(person_number)

        for candidate_path in candidates:
            # Clean path from redundant slashes
            clean_path = "/".join([p for p in candidate_path.split("/") if p])
            encoded_path = self._encode_path_segments(clean_path)
            
            # GET /sites/{site-id}/drives/{drive-id}/root:/{folder_path}:/children
            url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root:/{encoded_path}:/children"
            logger.info(f"Querying SharePoint path: {clean_path} (Encoded: {encoded_path})")
            
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                children = response.json().get("value", [])
                # Only keep files, exclude folders/directories
                files = [item for item in children if "file" in item]
                logger.info(f"Folder '{clean_path}' found with {len(files)} files.")
                return files, clean_path
            elif response.status_code == 404:
                logger.debug(f"Path '{clean_path}' not found (404). Trying next candidate if available.")
                continue
            else:
                logger.error(f"Error querying path '{clean_path}': {response.status_code} - {response.text}")
                if response.status_code in (401, 403):
                    raise Exception(f"SharePoint permissions or auth error: {response.text}")
                    
        # If all candidates returned 404
        logger.warning(f"No SharePoint folder found for person number {person_number} in any checked paths.")
        return [], ""

    async def get_download_stream(
        self, file_item: Dict[str, Any]
    ) -> Tuple[AsyncGenerator[bytes, None], str, str]:
        """
        Extracts details from file item and returns an async byte generator, filename, and mimetype.
        """
        download_url = file_item.get("@microsoft.graph.downloadUrl")
        file_name = file_item.get("name", "document.pdf")
        mime_type = file_item.get("file", {}).get("mimeType", "application/octet-stream")
        
        if not download_url:
            raise Exception("SharePoint file item is missing download URL.")
            
        logger.info(f"Preparing download stream for file: '{file_name}' (MIME: {mime_type})")
        
        # Generator function that streams file chunk-by-chunk using a self-managed httpx client
        async def stream_generator():
            async with httpx.AsyncClient() as dl_client:
                async with dl_client.stream("GET", download_url) as r:
                    r.raise_for_status()
                    async for chunk in r.aiter_bytes(chunk_size=8192):
                        yield chunk
                    
        return stream_generator(), file_name, mime_type

    async def get_zipped_download_stream(
        self, files: List[Dict[str, Any]], person_number: str
    ) -> Tuple[AsyncGenerator[bytes, None], str, str]:
        """
        Downloads multiple files from SharePoint, compiles them into a ZIP archive,
        and returns an async byte generator for the ZIP content.
        """
        zip_filename = f"{person_number}_documents.zip"
        mime_type = "application/zip"
        
        logger.info(f"Creating ZIP download stream for {len(files)} files.")
        
        async def zip_stream_generator():
            import io
            import zipfile
            
            zip_buffer = io.BytesIO()
            # Compile the zip archive in-memory
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                async with httpx.AsyncClient() as fetch_client:
                    for file_item in files:
                        name = file_item.get("name", "document.pdf")
                        download_url = file_item.get("@microsoft.graph.downloadUrl")
                        if download_url:
                            try:
                                logger.info(f"Fetching '{name}' for zipping...")
                                res = await fetch_client.get(download_url)
                                if res.status_code == 200:
                                    zip_file.writestr(name, res.content)
                                    logger.info(f"Successfully added '{name}' to ZIP archive.")
                                else:
                                    logger.error(f"Failed to fetch '{name}' for zipping (status: {res.status_code})")
                            except Exception as e:
                                logger.error(f"Error fetching '{name}' for zipping: {str(e)}")
                                
            zip_buffer.seek(0)
            # Yield chunk-by-chunk
            while True:
                chunk = zip_buffer.read(8192)
                if not chunk:
                    break
                yield chunk
                
        return zip_stream_generator(), zip_filename, mime_type

