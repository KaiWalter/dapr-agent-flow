import logging
import debugpy
import os
from dapr.ext.workflow import WorkflowRuntime, DaprWorkflowClient
from workflows.voice2action import (
    voice2action_poll_orchestrator,
    voice2action_per_file_orchestrator, )
from activities.onedrive_inbox import (
    list_onedrive_inbox,
    mark_file_pending,
    download_onedrive_file,
)
from activities.transcribe_audio import transcribe_audio_activity
from activities.publish_intent_orchestrator import publish_intent_plan_activity

# Archive activities are imported conditionally per mode below


level = os.getenv("DAPR_LOG_LEVEL", "info").upper()

# Ensure a root handler exists so all module loggers emit to console
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

# This app subscribes to a pubsub topic and schedules the workflow when triggered
from flask import Flask, request, jsonify

app = Flask(__name__)

# Dapr pubsub subscription endpoint
@app.route("/dapr/subscribe", methods=["GET"])
def dapr_subscribe():
    """Programmatic Dapr subscriptions for this app.

    Replaces components/schedule-voice2action.yaml.
    """
    subs = [
        {
            "pubsubname": "pubsub",
            "topic": "voice2action-schedule",
            "route": "schedule-voice2action",
        }
    ]
    logger.info("Reporting programmatic subscriptions: %s", subs)
    return jsonify(subs)


@app.route("/schedule-voice2action", methods=["POST"])
def schedule_voice2action():
    logger.info("Flask handler triggered for /schedule-voice2action")
    event = request.get_json()
    logger.info(f"Received pubsub event: {event}")
    # Unpack CloudEvent: actual input is in event['data']
    workflow_input = event.get("data", {})
    wf_client = DaprWorkflowClient()
    instance_id = wf_client.schedule_new_workflow(
        workflow=voice2action_poll_orchestrator,
        input=workflow_input,
    )
    logger.info(f"Scheduled poller workflow instance: {instance_id}")
    return jsonify({"instance_id": instance_id}), 200

def start_runtime():
    runtime = WorkflowRuntime()
    runtime.register_workflow(voice2action_poll_orchestrator)
    runtime.register_workflow(voice2action_per_file_orchestrator)
    # Register both local and onedrive activities; orchestrator will pick based on config
    from activities.local_inbox import list_local_inbox_activity, prepare_local_file_activity
    runtime.register_activity(list_local_inbox_activity)
    runtime.register_activity(prepare_local_file_activity)
    runtime.register_activity(list_onedrive_inbox)
    runtime.register_activity(download_onedrive_file)
    from activities.archive_recording import archive_recording_local_activity, archive_recording_onedrive_activity
    runtime.register_activity(archive_recording_local_activity)
    runtime.register_activity(archive_recording_onedrive_activity)
    runtime.register_activity(mark_file_pending)
    runtime.register_activity(transcribe_audio_activity)
    runtime.register_activity(publish_intent_plan_activity)
    runtime.start()

if __name__ == "__main__":
    if os.getenv("DEBUGPY_ENABLE", "0") == "1":
        debugpy.listen(("0.0.0.0", 5678))
        print("debugpy: Waiting for debugger attach on port 5678...")
        debugpy.wait_for_client()

    start_runtime()
    port = int(os.environ.get("DAPR_APP_PORT", 5001))
    app.run(host="0.0.0.0", port=port)
