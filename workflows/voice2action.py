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
from activities.transcribe_audio import transcribe_audio_activity

logger = logging.getLogger("voice2action")


def wf_log(ctx: DaprWorkflowContext, msg: str, *args):
    try:
        logger.info(msg, *args)
    except Exception as e:
        logger.error(f"Logging error: {e}")

def wf_log_exception(ctx: DaprWorkflowContext, msg: str, exc: Exception):
    logger.error(f"{msg}: {exc}", exc_info=True)


# Orchestrator: single-shot poll and fan-out per file


def voice2action_poll_orchestrator(ctx: DaprWorkflowContext, input: Optional[dict] = None):
    cfg = input or {}
    folder_path = cfg.get("folder_path")
    wf_log(ctx, "voice2action_poll: polling folder=%s", folder_path)
    try:
        files_result = yield ctx.call_activity(
            activity=list_onedrive_inbox,
            input=ListInboxRequest(folder_path=folder_path).model_dump(),
        )
        wf_log(ctx, "voice2action_poll: files_result=%s", files_result)
        files = [FileRef.model_validate(f) for f in files_result.get("files", [])]
        wf_log(ctx, "voice2action_poll: %d new files detected", len(files))
        for f in files:
            wf_log(ctx, "voice2action_poll: scheduling file id=%s name=%s", f.id, f.name)
            try:
                yield ctx.call_activity(
                    activity=mark_file_pending,
                    input=MarkPendingRequest(file_id=f.id).model_dump(),
                )
            except Exception as e:
                wf_log_exception(ctx, f"Exception in mark_file_pending for file id={f.id}", e)
                raise
            try:
                yield ctx.call_child_workflow(
                    voice2action_per_file_orchestrator,
                    input=f.model_dump(),
                )
            except Exception as e:
                wf_log_exception(ctx, f"Exception in call_child_workflow for file id={f.id}", e)
                raise
        wf_log(ctx, "voice2action_poll: completed cycle, files=%d", len(files))
        return {"polled": True, "files": len(files)}
    except Exception as e:
        wf_log_exception(ctx, "Exception in voice2action_poll_orchestrator", e)
        raise


# Per-file orchestrator: download the file (idempotent)

def voice2action_per_file_orchestrator(ctx: DaprWorkflowContext, input):
    try:
        file = FileRef.model_validate(input)
        wf_log(ctx, "voice2action_per_file: downloading id=%s name=%s", file.id, file.name)
        download_result = yield ctx.call_activity(
            activity=download_onedrive_file,
            input=DownloadRequest(file=file).model_dump(),
        )
        # download_result contains the local path under 'path'
        audio_path = download_result.get('path')
        # Derive MIME type from file extension (.mp3 -> audio/mpeg, .wav -> audio/x-wav)
        mime_type = 'audio/mpeg' if file.name.lower().endswith('.mp3') else 'audio/x-wav'
        wf_log(ctx, "voice2action_per_file: transcribing id=%s path=%s", file.id, audio_path)
        transcription_result = yield ctx.call_activity(
            activity=transcribe_audio_activity,
            input={"audio_path": audio_path, "mime_type": mime_type},
        )
        wf_log(ctx, "voice2action_per_file: transcription done id=%s", file.id)
        return {"ok": True, "transcription": transcription_result}
    except Exception as e:
        wf_log_exception(ctx, "Exception in voice2action_per_file_orchestrator", e)
        raise
