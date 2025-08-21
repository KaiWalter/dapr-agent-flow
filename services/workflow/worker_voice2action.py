import os
import json
import logging
from time import sleep
import debugpy

from cloudevents.sdk.event import v1
from dapr.ext.grpc import App
from dapr.clients.grpc._response import TopicEventResponse
from dapr.ext.workflow import WorkflowRuntime, DaprWorkflowClient

from workflows.voice2action import (
    voice2action_poll_orchestrator,
    voice2action_per_file_orchestrator,
)
from activities.onedrive_inbox import (
    list_onedrive_inbox,
    mark_file_pending,
    download_onedrive_file,
)
from activities.transcribe_audio import transcribe_audio_activity
from activities.publish_intent_orchestrator import publish_intent_plan_activity
from services.state_store import StateStore

# Root logging per repo convention
level = os.getenv("DAPR_LOG_LEVEL", "info").upper()
root = logging.getLogger()
if not root.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
root.setLevel(getattr(logging, level, logging.INFO))
logger = logging.getLogger("worker_voice2action")


def start_runtime() -> None:
    runtime = WorkflowRuntime()
    runtime.register_workflow(voice2action_poll_orchestrator)
    runtime.register_workflow(voice2action_per_file_orchestrator)
    # Register both local and onedrive activities; orchestrator will pick based on config
    from activities.local_inbox import (
        list_local_inbox_activity,
        prepare_local_file_activity,
    )
    runtime.register_activity(list_local_inbox_activity)
    runtime.register_activity(prepare_local_file_activity)
    runtime.register_activity(list_onedrive_inbox)
    runtime.register_activity(download_onedrive_file)
    from activities.archive_recording import (
        archive_recording_local_activity,
        archive_recording_onedrive_activity,
    )
    runtime.register_activity(archive_recording_local_activity)
    runtime.register_activity(archive_recording_onedrive_activity)
    runtime.register_activity(mark_file_pending)
    runtime.register_activity(transcribe_audio_activity)
    runtime.register_activity(publish_intent_plan_activity)
    runtime.start()


app = App()


@app.subscribe(pubsub_name="pubsub", topic="voice2action-schedule")
def on_schedule_event(event: v1.Event) -> TopicEventResponse:
    try:
        raw = event.Data()
        if isinstance(raw, (bytes, bytearray)):
            try:
                raw = raw.decode("utf-8")
            except Exception:
                pass
        data = json.loads(raw) if isinstance(raw, str) else raw
        logger.info("Received pubsub event: %s", data)

        # Idempotency using CloudEvent ID (at-least-once delivery)
        ce_id = None
        try:
            ce_id = event.EventID()
        except Exception:
            pass
        store = StateStore()
        if ce_id:
            key = f"schedule_event:{ce_id}"
            if store.get(key):
                logger.info(
                    "Duplicate delivery for event id=%s; already processed. Acking.", ce_id
                )
                sleep(0.02)
                return TopicEventResponse("success")

        # Schedule workflow
        wf_client = DaprWorkflowClient()
        instance_id = wf_client.schedule_new_workflow(
            workflow=voice2action_poll_orchestrator,
            input=data or {},
        )
        logger.info("Scheduled poller workflow instance: %s", instance_id)
        if ce_id:
            store.set(f"schedule_event:{ce_id}", instance_id)
        return TopicEventResponse("success")
    except Exception as e:
        logger.exception("Failed to process schedule event: %s", e)
        return TopicEventResponse("retry")


# Health check
app.register_health_check(lambda: logger.info("Healthy") or None)


if __name__ == "__main__":
    if os.getenv("DEBUGPY_ENABLE", "0") == "1":
        debugpy.listen(("0.0.0.0", 5678))
        print("debugpy: Waiting for debugger attach on port 5678...")
        debugpy.wait_for_client()

    # Start workflow runtime then gRPC app
    start_runtime()
    port = int(os.environ.get("DAPR_APP_PORT", 5002))
    app.run(port)
