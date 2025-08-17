from __future__ import annotations

from .http_client import HttpClient
from .token_state_store import TokenStateStore
from models.voice2action import FileRef

from typing import Optional

def move_file_to_archive(file_id: str, file_name: Optional[str] = None, inbox_folder: Optional[str] = None, archive_folder: Optional[str] = None):
    """
    Move a file to the archive folder on OneDrive using PATCH /me/drive/items/{item-id}
    with parentReference.id as per Graph documentation.
    """
    service = OneDriveService()
    if not archive_folder:
        raise ValueError("archive_folder is required to move file in OneDrive.")
    # Resolve destination folder ID from path
    dest_meta = service.get_item_by_path(archive_folder)
    dest_id = dest_meta.get("id")
    if not dest_id:
        raise RuntimeError(f"Could not resolve archive folder id for path '{archive_folder}'")

    patch_url = f"{service.base_url}/drive/items/{file_id}"
    json_body: Dict[str, Any] = {
        "parentReference": {"id": dest_id}
    }
    if file_name:
        json_body["name"] = file_name
    resp = service.http.patch(patch_url, headers=service._headers(), json=json_body)
    resp.raise_for_status()
    return resp.json()

from typing import List, Optional, Dict, Any
import json
import logging
import msal
import os
import time
import requests



class OneDriveService:
    """
    OneDrive adapter using Microsoft Graph. Handles token refresh and state store for TR001.
    """

    TOKEN_STATE_KEY = "global_ms_graph_token_cache"  # store the MSAL cache, not a custom dict

    def __init__(self, http: Optional[HttpClient] = None):
        self.http = http or HttpClient()
        self.base_url = "https://graph.microsoft.com/v1.0/me"
        self.state = TokenStateStore()
        self.logger = logging.getLogger("onedrive")
        self.client_id = os.getenv("MS_GRAPH_CLIENT_ID")
        self.client_secret = os.getenv("MS_GRAPH_CLIENT_SECRET")
        self.authority = os.getenv("MS_GRAPH_AUTHORITY", "https://login.microsoftonline.com/consumers")
        # Delegated scopes
        self.scopes = [
            "User.Read",
            "Files.ReadWrite"
        ]

        # Load MSAL token cache from state
        self.cache = msal.SerializableTokenCache()
        raw = self.state.get(self.TOKEN_STATE_KEY)
        if raw:
            try:
                self.cache.deserialize(raw)
            except Exception:
                self.logger.warning("Failed to deserialize token cache; starting fresh.")

        self.app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret,
            token_cache=self.cache,
        )

        # Ensure we have a token (will use refresh token if available)
        self._ensure_token()

    # ---- First-time bootstrap (run once after user consents) ----
    def get_authorization_url(self, redirect_uri: str) -> str:
        return self.app.get_authorization_request_url(self.scopes, redirect_uri=redirect_uri)

    def redeem_auth_code(self, code: str, redirect_uri: str):
        result = self.app.acquire_token_by_authorization_code(
            code, scopes=self.scopes, redirect_uri=redirect_uri
        )
        self._ensure_ok(result)
        self._persist_cache()

    # ---- Normal operation / refresh-on-demand ----
    def _ensure_token(self):
        accounts = self.app.get_accounts()
        result = self.app.acquire_token_silent(self.scopes, account=accounts[0] if accounts else None)
        if not result:
            raise RuntimeError(
                "No cached delegated token. Run interactive consent (auth code) once to bootstrap."
            )
        self._ensure_ok(result)
        self._persist_cache()

    def _headers(self):
        accounts = self.app.get_accounts()
        result = self.app.acquire_token_silent(self.scopes, account=accounts[0] if accounts else None)
        self._ensure_ok(result)
        self._persist_cache()
        return {"Authorization": f"Bearer {result['access_token']}"}

    def _persist_cache(self):
        if self.cache.has_state_changed:
            self.state.set(self.TOKEN_STATE_KEY, self.cache.serialize())

    def _ensure_ok(self, result):
        if not result or "access_token" not in result:
            raise RuntimeError(f"MSAL token failure: {result.get('error_description', result)}")

    # reqular operations
    def download_file_by_path(self, onedrive_path: str, local_path: str):
        """
        Download a file from OneDrive by its path (e.g. /folder/file.txt) to a local file.
        Uses requests directly for streaming.
        """
        url = f"{self.base_url}/drive/root:{onedrive_path}:/content"
        resp = requests.get(url, headers=self._headers(), stream=True)
        resp.raise_for_status()
        with open(local_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

    def list_folder(self, folder_path: str) -> List[FileRef]:
        # GET /me/drive/root:/path:/children
        url = f"{self.base_url}/drive/root:/{folder_path}:/children"
        resp = self.http.get(url, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        items = []
        for it in data.get("value", []):
            if "file" in it:  # skip folders
                items.append(
                    FileRef(
                        id=it.get("id"),
                        name=it.get("name"),
                        size=it.get("size"),
                        etag=it.get("eTag"),
                    )
                )
        return items

    def get_download_url(self, item_id: str) -> str:
        # GET /me/drive/items/{item-id}
        url = f"{self.base_url}/drive/items/{item_id}"
        resp = self.http.get(url, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        # Prefer @microsoft.graph.downloadUrl if available
        dl = data.get("@microsoft.graph.downloadUrl")
        if dl:
            return dl
        # Fallback: content endpoint
        return f"{url}/content"

    def get_item_by_path(self, item_path: str) -> Dict[str, Any]:
        """
        Resolve an item (file or folder) by absolute or relative OneDrive path and return its metadata.
        Example: "/Recordings/Archive" -> { id: "...", name: "Archive", ... }
        """
        # Normalize: strip leading slash to match /drive/root:/{path} syntax
        norm = item_path.lstrip('/')
        url = f"{self.base_url}/drive/root:/{norm}"
        resp = self.http.get(url, headers=self._headers())
        resp.raise_for_status()
        return resp.json()
