from __future__ import annotations

from typing import List, Optional
from dapr.ext.workflow import DaprWorkflowContext
import logging
from models.voice2action import ListInboxRequest, FileRef, DownloadRequest, MarkPendingRequest
from activities.onedrive_inbox import (
    list_onedrive_inbox,
    mark_file_pending,
    download_onedrive_file,
)

logger = logging.getLogger("voice2action")


def wf_log(ctx: DaprWorkflowContext, msg: str, *args):
    try:
        logger.info(msg, *args)
    except Exception:
        pass


# Orchestrator: single-shot poll and fan-out per file

def voice2action_poll_orchestrator(ctx: DaprWorkflowContext, input: Optional[dict] = None):
    cfg = input or {}
    folder_path = cfg.get("folder_path")

    wf_log(ctx, "voice2action_poll: polling folder=%s", folder_path)
    # list files
    files_result = yield ctx.call_activity(
        activity=list_onedrive_inbox,
        input=ListInboxRequest(folder_path=folder_path).model_dump(),
    )
    files = [FileRef.model_validate(f) for f in files_result.get("files", [])]
    wf_log(ctx, "voice2action_poll: %d new files detected", len(files))

    # for each file, mark pending and start a child workflow to download
    for f in files:
        wf_log(ctx, "voice2action_poll: scheduling file id=%s name=%s", f.id, f.name)
        yield ctx.call_activity(
            activity=mark_file_pending,
            input=MarkPendingRequest(file_id=f.id).model_dump(),
        )
        # start per-file workflow as fire-and-forget (child orchestrator)
        yield ctx.call_child_workflow(
            voice2action_per_file_orchestrator,
            input=f.model_dump(),
        )

    wf_log(ctx, "voice2action_poll: completed cycle, files=%d", len(files))
    return {"polled": True, "files": len(files)}


# Per-file orchestrator: download the file (idempotent)

def voice2action_per_file_orchestrator(ctx: DaprWorkflowContext, input):
    file = FileRef.model_validate(input)
    wf_log(ctx, "voice2action_per_file: downloading id=%s name=%s", file.id, file.name)
    yield ctx.call_activity(
        activity=download_onedrive_file,
        input=DownloadRequest(file=file).model_dump(),
    )
    wf_log(ctx, "voice2action_per_file: done id=%s", file.id)
    return {"ok": True}
