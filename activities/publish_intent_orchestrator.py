from __future__ import annotations
import json
import logging
import os
from typing import Any, Dict
from dapr.clients import DaprClient

logger = logging.getLogger("voice2action")


def publish_intent_plan_activity(ctx, input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Publish a planning/execution request to the LLM Orchestrator via Dapr pub/sub.
    Input:
      - correlation_id: str
      - transcription_text: str
      - transcription_path: str
      - classification_path: str
      - audio_path: str
      - file_name: str
      - metadata: dict (optional)
    """
    pubsub_name = os.getenv("DAPR_PUBSUB_NAME", "pubsub")
    # Topic the LLM Orchestrator service listens on; default matches orchestrator name
    topic = os.getenv("DAPR_INTENT_ORCHESTRATOR_TOPIC", "IntentOrchestrator")

    # LLM Orchestrator expects a TriggerAction message format
    event_data = {
        "task": f"Process voice transcription from [{input.get('transcription_path')}]. "
                f"Text inside [...] is a file path — preserve it exactly."
                f"From the first two sentences, extract the user’s intent and propose next steps. "
                f"Treat the rest of the transcription as a note with no further intent. "
                f"Possible explicit intent: create a task. "
                f"If no intent is found, send an email containing the full transcript.",
        "workflow_instance_id": input.get("correlation_id"),
    }

    with DaprClient() as d:
        d.publish_event(
            pubsub_name=pubsub_name,
            topic_name=topic,
            data=json.dumps(event_data),
            data_content_type="application/json",
            publish_metadata={
                "cloudevent.type": "TriggerAction",
            },
        )

    logger.info(
        "Published to %s/%s for workflow_instance_id=%s", pubsub_name, topic, event_data["workflow_instance_id"]
    )
    return {"published": True}
