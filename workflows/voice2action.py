from __future__ import annotations

from typing import List, Optional
from dapr.ext.workflow import DaprWorkflowContext
import os
import logging
from models.voice2action import ListInboxRequest, FileRef, DownloadRequest, MarkPendingRequest
from activities.onedrive_inbox import (
    list_onedrive_inbox,
    mark_file_pending,
    download_onedrive_file,
)

from activities.transcribe_audio import transcribe_audio_activity
from activities.publish_intent_orchestrator import publish_intent_plan_activity
from activities.archive_recording import (
    archive_recording_activity,  # legacy wrapper
    archive_recording_local_activity,
    archive_recording_onedrive_activity,
)

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
    # Tier 1 provides these
    offline_mode = bool(cfg.get("offline_mode", False))
    inbox_folder = cfg.get("inbox_folder")
    wf_log(ctx, "voice2action_poll: polling folder=%s", inbox_folder)
    try:
        if offline_mode:
            from activities.local_inbox import list_local_inbox_activity
            activity_fn = list_local_inbox_activity
        else:
            activity_fn = list_onedrive_inbox
        files_result = yield ctx.call_activity(
            activity=activity_fn,
            input=ListInboxRequest(inbox_folder=inbox_folder).model_dump(),
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
                    input={
                        "file": f.model_dump(),
                        "config": {
                            "offline_mode": offline_mode,
                            "inbox_folder": inbox_folder,
                            "archive_folder": cfg.get("archive_folder"),
                            "download_folder": cfg.get("download_folder"),
                        },
                    },
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
        data = input or {}
        file = FileRef.model_validate(data.get("file"))
        cfg = data.get("config") or {}
        offline_mode = bool(cfg.get("offline_mode", False))
        inbox_folder = cfg.get("inbox_folder")
        archive_folder = cfg.get("archive_folder")
        download_folder = cfg.get("download_folder")
        wf_log(ctx, "voice2action_per_file: downloading id=%s name=%s", file.id, file.name)
        if offline_mode:
            from activities.local_inbox import prepare_local_file_activity
            download_activity = prepare_local_file_activity
        else:
            download_activity = download_onedrive_file
        download_result = yield ctx.call_activity(
            activity=download_activity,
            input={
                **DownloadRequest(file=file, download_folder=download_folder).model_dump(),
                "src_folder": inbox_folder,
            },
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
        # Build archive input; inbox folder depends on mode
        archive_input = {
            "file_id": file.id,
            "file_name": file.name,
            "inbox_folder": inbox_folder,
            "archive_folder": archive_folder,
        }
        # Publish intent plan first (fire-and-forget via pub/sub), then archive sequentially
        _ = yield ctx.call_activity(
            activity=publish_intent_plan_activity,
            input={
                "correlation_id": file.id,
                "transcription_text": transcription_result.get("text"),
                "transcription_path": transcription_result.get("transcription_path"),
                "audio_path": audio_path,
                "file_name": file.name,
            },
        )
        archive_activity = archive_recording_local_activity if offline_mode else archive_recording_onedrive_activity
        archive_result = yield ctx.call_activity(
            activity=archive_activity,
            input=archive_input,
        )
        return {"ok": True, "transcription": transcription_result, "archive": archive_result}
    except Exception as e:
        wf_log_exception(ctx, "Exception in voice2action_per_file_orchestrator", e)
        raise
