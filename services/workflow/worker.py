from __future__ import annotations
from time import sleep

import logging
import debugpy
import os

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
    offline_mode = os.getenv("OFFLINE_MODE", "false").lower() == "true"
    # Resolve all config at Tier 1 and pass it down (Tier 2/3 shouldn't read env for this)
    inbox_folder = (
        os.getenv("LOCAL_VOICE_INBOX", "./local_voice_inbox")
        if offline_mode
        else os.getenv("ONEDRIVE_VOICE_INBOX")
    )
    archive_folder = (
        os.getenv("LOCAL_VOICE_ARCHIVE", "./local_voice_archive")
        if offline_mode
        else os.getenv("ONEDRIVE_VOICE_ARCHIVE")
    )
    download_folder = os.getenv("LOCAL_VOICE_DOWNLOAD_FOLDER", "./.work/voice")
    # Optional: path to common terms file to bias transcription (FR002)
    terms_file = os.getenv("TRANSCRIPTION_TERMS_FILE")

    # Ensure local dirs exist in offline mode for smoother testing
    if offline_mode:
        if inbox_folder:
            os.makedirs(inbox_folder, exist_ok=True)
        if archive_folder:
            os.makedirs(archive_folder, exist_ok=True)

    sleep(poll_interval)
    
    try:
        with DaprClient() as d:
            while True:
                import json
                event = {
                    "offline_mode": offline_mode,
                    "inbox_folder": inbox_folder,
                    "archive_folder": archive_folder,
                    "download_folder": download_folder,
                    "terms_file": terms_file,
                }
                d.publish_event(
                    pubsub_name="pubsub",
                    topic_name="voice2action-schedule",
                    data=json.dumps(event),
                    data_content_type="application/json",
                )
                logger.info(
                    f"Published schedule event to pubsub (mode={'offline' if offline_mode else 'onedrive'}): {event}"
                )
                sleep(poll_interval)
    except KeyboardInterrupt:
        logger.info("Stopping...")


if __name__ == "__main__":
    if os.getenv("DEBUGPY_ENABLE", "0") == "1":
        debugpy.listen(("0.0.0.0", 5678))
        print("debugpy: Waiting for debugger attach on port 5678...")
        debugpy.wait_for_client()
    
    main()
