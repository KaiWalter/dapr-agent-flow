from __future__ import annotations
from time import sleep

import logging
import debugpy
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

logger = logging.getLogger("workflow")

def main():
    from dapr.clients import DaprClient
    poll_interval = int(os.getenv("ONEDRIVE_VOICE_POLL_INTERVAL", "30"))
    folder_path = os.getenv("ONEDRIVE_VOICE_INBOX")

    try:
        with DaprClient() as d:
            while True:
                import json
                event = {"folder_path": folder_path}
                d.publish_event(
                    pubsub_name="pubsub",
                    topic_name="voice2action-schedule",
                    data=json.dumps(event),
                    data_content_type="application/json",
                )
                logger.info(f"Published schedule event to pubsub: {event}")
                sleep(poll_interval)
    except KeyboardInterrupt:
        logger.info("Stopping...")


if __name__ == "__main__":
    if os.getenv("DEBUGPY_ENABLE", "0") == "1":
        debugpy.listen(("0.0.0.0", 5678))
        print("debugpy: Waiting for debugger attach on port 5678...")
        debugpy.wait_for_client()
    
    main()
