from __future__ import annotations
from time import sleep

import logging
import os
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

logging.basicConfig(level=logging.INFO)
# logging.getLogger("dapr").setLevel(logging.DEBUG)
# logging.getLogger("dapr.ext.workflow").setLevel(logging.DEBUG)
logger = logging.getLogger("voice2action")
logger.setLevel(logging.DEBUG)


def main():
    runtime = WorkflowRuntime()
    # Register workflows (orchestrators)
    runtime.register_workflow(voice2action_poll_orchestrator)
    runtime.register_workflow(voice2action_per_file_orchestrator)
    # Register activities
    runtime.register_activity(list_onedrive_inbox)
    runtime.register_activity(mark_file_pending)
    runtime.register_activity(download_onedrive_file)

    runtime.start()
    sleep(10)  # wait for workflow runtime to start

    wf_client = DaprWorkflowClient()

    poll_interval = int(os.getenv("ONEDRIVE_VOICE_POLL_INTERVAL", "30"))
    folder_path = os.getenv("ONEDRIVE_VOICE_INBOX")

    try:
        while True:
            instance_id = wf_client.schedule_new_workflow(
                workflow=voice2action_poll_orchestrator,
                input={
                    "folder_path": folder_path,
                },
            )
            logger.info(f"Scheduled poller workflow instance: {instance_id}")
            state = wf_client.wait_for_workflow_completion(instance_id, timeout_in_seconds=120)
            logger.info(f"Poller completed: status={state.runtime_status}")
            sleep(max(5, poll_interval))
    except KeyboardInterrupt:
        logger.info("Stopping...")
    finally:
        runtime.shutdown()


if __name__ == "__main__":
    main()
