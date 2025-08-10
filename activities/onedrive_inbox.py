from __future__ import annotations

import os
import json
import logging
from typing import List
from models.voice2action import FileRef, ListInboxRequest, ListInboxResult, DownloadRequest, MarkPendingRequest
from services.onedrive import OneDriveService
from services.state_store import StateStore
from services.http_client import HttpClient


logger = logging.getLogger("voice2action")
PENDING_PREFIX = "voice_inbox_pending:"  # to avoid duplicates during polling
DOWNLOADED_PREFIX = "voice_inbox_downloaded:"  # idempotency tracking
DOWNLOAD_DIR = os.getenv("VOICE_DOWNLOAD_DIR", "./downloads/voice")


def list_onedrive_inbox(ctx, req: dict) -> dict:
    data = ListInboxRequest.model_validate(req)
    folder = data.folder_path or os.getenv("ONEDRIVE_VOICE_INBOX", "/Voice/Inbox")
    logger.info("Listing OneDrive inbox folder=%s", folder)
    http = HttpClient()
    svc = OneDriveService(http)
    files = svc.list_folder(folder)
    logger.info("Found %d items in OneDrive folder before filtering", len(files))
    # Filter out files that were already downloaded or are pending
    state = StateStore()
    filtered: List[FileRef] = []
    skipped_downloaded = 0
    skipped_pending = 0
    for f in files:
        if state.get(DOWNLOADED_PREFIX + f.id):
            skipped_downloaded += 1
            continue
        if state.get(PENDING_PREFIX + f.id):
            skipped_pending += 1
            continue
        filtered.append(f)
    logger.info(
        "After filtering: %d new files (skipped %d downloaded, %d pending)",
        len(filtered),
        skipped_downloaded,
        skipped_pending,
    )
    return ListInboxResult(files=filtered).model_dump()


def mark_file_pending(ctx, req: dict) -> dict:
    data = MarkPendingRequest.model_validate(req)
    logger.info("Marking file pending id=%s", data.file_id)
    state = StateStore()
    state.set(PENDING_PREFIX + data.file_id, "1")
    return {"ok": True}


def download_onedrive_file(ctx, req: dict) -> dict:
    data = DownloadRequest.model_validate(req)
    http = HttpClient()
    svc = OneDriveService(http)
    dl_url = svc.get_download_url(data.file.id)
    dest_dir = data.target_dir or DOWNLOAD_DIR
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, data.file.name)
    logger.info("Downloading OneDrive file id=%s name=%s -> %s", data.file.id, data.file.name, dest_path)
    http.download(dl_url, dest_path)
    # Mark downloaded and clear pending
    state = StateStore()
    state.set(DOWNLOADED_PREFIX + data.file.id, "1")
    state.delete(PENDING_PREFIX + data.file.id)
    logger.info("Downloaded and marked complete id=%s", data.file.id)
    return {"path": dest_path}
