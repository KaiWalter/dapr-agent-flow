from __future__ import annotations

import os
from typing import Any, Dict, Optional
import httpx


class HttpClient:
    def __init__(self, timeout: float = 30.0):
        self._client = httpx.Client(timeout=timeout)

    def get(self, url: str, headers: Optional[Dict[str, str]] = None, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        return self._client.get(url, headers=headers, params=params)

    def post(self, url: str, json: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        if json is not None:
            return self._client.post(url, json=json, headers=headers)
        elif data is not None:
            return self._client.post(url, data=data, headers=headers)
        else:
            return self._client.post(url, headers=headers)

    def download(self, url: str, dest_path: str, headers: Optional[Dict[str, str]] = None) -> None:
        with self._client.stream("GET", url, headers=headers) as r:
            r.raise_for_status()
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)

    def patch(self, url: str, json: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        return self._client.patch(url, json=json, headers=headers)

    def delete(self, url: str, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        return self._client.delete(url, headers=headers)

    def close(self):
        self._client.close()
