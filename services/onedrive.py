from __future__ import annotations

import os
from typing import List, Optional
from .http_client import HttpClient
from models.voice2action import FileRef


class OneDriveService:
    """
    Minimal OneDrive adapter using Microsoft Graph. For real use, obtain an access token via client credentials or device code.
    This adapter expects the access token to be provided in env MS_GRAPH_TOKEN. Do NOT store secrets in code.
    """

    def __init__(self, http: Optional[HttpClient] = None):
        self.http = http or HttpClient()
        self.base_url = "https://graph.microsoft.com/v1.0/me"
        self.token = os.getenv("MS_GRAPH_TOKEN")
        if not self.token:
            raise RuntimeError("MS_GRAPH_TOKEN env var is required for OneDrive access")

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

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
