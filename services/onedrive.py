from __future__ import annotations
from .http_client import HttpClient
from .state_store import StateStore
from models.voice2action import FileRef
from typing import List, Optional, Dict, Any
import json
import logging
import msal
import os
import time



class OneDriveService:
    """
    OneDrive adapter using Microsoft Graph. Handles token refresh and state store for TR001.
    """

    TOKEN_STATE_KEY = "global_ms_graph_token_state"

    def __init__(self, http: Optional[HttpClient] = None):
        self.http = http or HttpClient()
        self.base_url = "https://graph.microsoft.com/v1.0/me"
        self.state = StateStore()
        self.logger = logging.getLogger("onedrive")
        self.client_id = os.getenv("MS_GRAPH_CLIENT_ID")
        self.client_secret = os.getenv("MS_GRAPH_CLIENT_SECRET")
        self.authority = os.getenv("MS_GRAPH_AUTHORITY", "https://login.microsoftonline.com/common")
        self.scope = ["https://graph.microsoft.com/.default", "offline_access"]
        self.token_data = None
        self.app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret,
        )
        self.token_data = self._load_token()
        if not self.token_data:
            self.logger.info("No stored token found, acquiring token via MSAL.")
            self.token_data = self._acquire_token_by_client_credentials()
            self._save_token(self.token_data)

    def _acquire_token_by_client_credentials(self):
        result = self.app.acquire_token_for_client(scopes=self.scope)
        if "access_token" not in result:
            raise RuntimeError(f"MSAL failed to acquire token: {result.get('error_description', result)}")
        return {
            "access_token": result["access_token"],
            "expires_at": int(time.time()) + int(result.get("expires_in", 3600)),
            "refresh_token": result.get("refresh_token")
        }
    def _headers(self):
        token = self._get_valid_access_token()
        return {"Authorization": f"Bearer {token}"}

    def _load_token(self) -> Optional[Dict[str, Any]]:
        raw = self.state.get(self.TOKEN_STATE_KEY)
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                return None
        return None

    def _save_token(self, data: Dict[str, Any]):
        self.state.set(self.TOKEN_STATE_KEY, json.dumps(data))

    def _get_valid_access_token(self) -> str:
        now = int(time.time())
        expires_at = self.token_data.get("expires_at", 0)
        # Defensive: force refresh if expires_at is missing or in the past
        if not expires_at or expires_at < now:
            self.logger.warning(f"Token expires_at value {expires_at} is missing or expired, forcing refresh.")
            self.token_data = self._acquire_token_by_client_credentials()
            self._save_token(self.token_data)
            expires_at = self.token_data.get("expires_at", 0)
        if expires_at - now < 300:
            # Less than 5 min left, refresh
            self.logger.info("Refreshing MS Graph token...")
            self.token_data = self._acquire_token_by_client_credentials()
            self._save_token(self.token_data)
        return self.token_data["access_token"]

    # _refresh_token is no longer needed with msal client credentials flow

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
