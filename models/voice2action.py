from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel


class FileRef(BaseModel):
    id: str
    name: str
    size: Optional[int] = None
    etag: Optional[str] = None


class ListInboxRequest(BaseModel):
    folder_path: Optional[str] = None
    corr_id: Optional[str] = None


class ListInboxResult(BaseModel):
    files: List[FileRef]


class DownloadRequest(BaseModel):
    file: FileRef
    corr_id: Optional[str] = None
    target_dir: Optional[str] = None


class MarkPendingRequest(BaseModel):
    file_id: str
    corr_id: Optional[str] = None
