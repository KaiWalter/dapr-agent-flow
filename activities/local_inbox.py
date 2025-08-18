import os
import shutil
from typing import List
from models.voice2action import FileRef, ListInboxRequest, ListInboxResult, DownloadRequest
from services.state_store import StateStore

# Reuse the same prefixes as OneDrive activities for idempotency
PENDING_PREFIX = "voice_inbox_pending:"
DOWNLOADED_PREFIX = "voice_inbox_downloaded:"

def list_local_inbox_activity(ctx, req: dict) -> dict:
    data = ListInboxRequest.model_validate(req)
    # Use the folder passed from Tier 2 (workflow)
    folder = data.inbox_folder
    if not folder:
        raise ValueError("list_local_inbox_activity requires 'inbox_folder' in request input.")
    os.makedirs(folder, exist_ok=True)
    # Build file refs from local folder
    refs: List[FileRef] = []
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        if os.path.isfile(path) and (name.lower().endswith('.wav') or name.lower().endswith('.mp3')):
            refs.append(FileRef(id=name, name=name))
    # Filter out already downloaded or pending
    state = StateStore()
    filtered: List[FileRef] = []
    for f in refs:
        if state.get(DOWNLOADED_PREFIX + f.id):
            continue
        if state.get(PENDING_PREFIX + f.id):
            continue
        filtered.append(f)
    return ListInboxResult(files=filtered).model_dump()


def prepare_local_file_activity(ctx, req: dict) -> dict:
    """
    Offline-mode equivalent of download: copies the local inbox file to the download work dir
    and marks it downloaded; also clears pending.
    Input matches DownloadRequest to keep workflow parity: { file: FileRef, target_dir?: str }
    Output: { path: str }
    """
    data = DownloadRequest.model_validate(req)
    # Workflow must provide the source directory of the local inbox via 'src_folder'
    src_dir = req.get("src_folder")
    if not src_dir:
        raise ValueError("prepare_local_file_activity requires 'src_folder' in request input.")
    # Validate only the fields expected by DownloadRequest to avoid extra-field errors
    payload = {k: v for k, v in req.items() if k in {"file", "corr_id", "download_folder"}}
    data = DownloadRequest.model_validate(payload)
    src_path = os.path.join(src_dir, data.file.name)
    dest_dir = data.download_folder or os.getenv("LOCAL_VOICE_DOWNLOAD_FOLDER", "./.work/voice")
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, data.file.name)
    # Copy file to workspace to keep parity with OneDrive download
    shutil.copy2(src_path, dest_path)
    # Mark downloaded and clear pending
    state = StateStore()
    state.set(DOWNLOADED_PREFIX + data.file.id, "1")
    state.delete(PENDING_PREFIX + data.file.id)
    return {"path": dest_path}
