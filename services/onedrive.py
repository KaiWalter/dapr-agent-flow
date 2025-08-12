from __future__ import annotations


import os
import json
import time
from typing import List, Optional, Dict, Any
from .http_client import HttpClient
from .state_store import StateStore
from models.voice2action import FileRef
import logging



class OneDriveService:
    """
    OneDrive adapter using Microsoft Graph. Handles token refresh and state store for TR001.
    """

    TOKEN_STATE_KEY = "ms_graph_token_state"

    def __init__(self, http: Optional[HttpClient] = None):
        self.http = http or HttpClient()
        self.base_url = "https://graph.microsoft.com/v1.0/me"
        self.state = StateStore()
        self.logger = logging.getLogger("onedrive")
        self.token_data = self._load_token()
        if not self.token_data:
            # First run: get from env
            env_token = os.getenv("MS_GRAPH_TOKEN")
            if not env_token:
                raise RuntimeError("MS_GRAPH_TOKEN env var is required for OneDrive access")
            # Assume env_token is a JSON string with at least access_token, expires_at, refresh_token
            try:
                self.token_data = json.loads(env_token)
            except Exception:
                # fallback: treat as raw access token, expires in 1h
                self.token_data = {
                    "access_token": env_token,
                    "expires_at": int(time.time()) + 3600,
                    "refresh_token": None
                }
            self._save_token(self.token_data)



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
        if self.token_data.get("expires_at", 0) - now < 300:
            # Less than 5 min left, refresh
            self.logger.info("Refreshing MS Graph token...")
            self._refresh_token()
        return self.token_data["access_token"]

    def _refresh_token(self):
        refresh_token = self.token_data.get("refresh_token")
        if not refresh_token:
            raise RuntimeError("No refresh_token available for MS Graph token refresh.")
        # Standard MS OAuth2 token endpoint
        token_url = os.getenv("MS_GRAPH_TOKEN_URL", "https://login.microsoftonline.com/common/oauth2/v2.0/token")
        client_id = os.getenv("MS_GRAPH_CLIENT_ID")
        client_secret = os.getenv("MS_GRAPH_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise RuntimeError("MS_GRAPH_CLIENT_ID and MS_GRAPH_CLIENT_SECRET env vars are required for token refresh.")
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": "https://graph.microsoft.com/.default offline_access"
        }
        resp = self.http.post(token_url, data=data)
        resp.raise_for_status()
        token_json = resp.json()
        access_token = token_json["access_token"]
        expires_in = int(token_json.get("expires_in", 3600))
        new_refresh_token = token_json.get("refresh_token", refresh_token)
        self.token_data = {
            "access_token": access_token,
            "expires_at": int(time.time()) + expires_in,
            "refresh_token": new_refresh_token
        }
        self._save_token(self.token_data)

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
