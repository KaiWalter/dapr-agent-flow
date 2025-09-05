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
        "task": (
            "Process voice transcription from file "
            f"[{input.get('transcription_path')}]. Text inside [...] is a file path — preserve it exactly. "
            "Identify explicit intent only (do not infer). Intent priority order:\n"
            "1. THOUGHT_COLLECTION: phrase matches 'this is a thought on {topic}'. {topic} is the immediately following words up to punctuation or newline.\n"
            "2. TASK_CREATION: explicit directive to create a task / follow up / reminder.\n"
            "3. FALLBACK_EMAIL: if neither above applies.\n"
            "If THOUGHT_COLLECTION is detected, plan to call the 'store_thought' tool with the full transcription text. "
            "Do not attempt other actions once a thought is stored. "
            "Multiple thought phrases may exist; store all distinct topics. "
            "Only treat a phrase as thought if the wording is explicit (case-insensitive) and starts exactly with 'this is a thought on'. "
            "If wording deviates, ignore it. "
            "If no valid thought phrase exists, continue evaluating for task creation, else fallback email."
        ),
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
