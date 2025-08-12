import logging
import os
import json
from dapr.ext.workflow import WorkflowRuntime, DaprWorkflowClient
from dapr.clients import DaprClient
from workflows.voice2action import (
    voice2action_poll_orchestrator,
    voice2action_per_file_orchestrator,
)
from activities.onedrive_inbox import (
    list_onedrive_inbox,
    mark_file_pending,
    download_onedrive_file,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker_voice2action")
logger.setLevel(logging.DEBUG)

# This app subscribes to a pubsub topic and schedules the workflow when triggered
from flask import Flask, request, jsonify

app = Flask(__name__)

# Dapr pubsub subscription endpoint
@app.route("/schedule-voice2action", methods=["POST"])
def schedule_voice2action():
    data = request.get_json()
    logger.info(f"Received pubsub event: {data}")
    folder_path = data.get("folder_path")
    wf_client = DaprWorkflowClient()
    instance_id = wf_client.schedule_new_workflow(
        workflow=voice2action_poll_orchestrator,
        input={"folder_path": folder_path},
    )
    logger.info(f"Scheduled poller workflow instance: {instance_id}")
    return jsonify({"instance_id": instance_id}), 200

def start_runtime():
    runtime = WorkflowRuntime()
    runtime.register_workflow(voice2action_poll_orchestrator)
    runtime.register_workflow(voice2action_per_file_orchestrator)
    runtime.register_activity(list_onedrive_inbox)
    runtime.register_activity(mark_file_pending)
    runtime.register_activity(download_onedrive_file)
    runtime.start()

if __name__ == "__main__":
    start_runtime()
    app.run(host="0.0.0.0", port=5001)
