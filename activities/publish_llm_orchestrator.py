from __future__ import annotations
import json
import logging
import os
from typing import Any, Dict
from dapr.clients import DaprClient

logger = logging.getLogger("voice2action")


def publish_llm_plan_activity(ctx, input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Publish a planning/execution request to the LLM Orchestrator via Dapr pub/sub.
    Input:
      - correlation_id: str
      - transcription_text: str
      - transcription_path: str
      - audio_path: str
      - file_name: str
      - metadata: dict (optional)
    """
    pubsub_name = os.getenv("DAPR_PUBSUB_NAME", "pubsub")
    # Topic the LLM Orchestrator service listens on; default matches orchestrator name
    topic = os.getenv("DAPR_LLM_ORCHESTRATOR_TOPIC", "LLMOrchestrator")

    # LLM Orchestrator expects a TriggerAction message format
    event_data = {
        "task": f"Process voice transcription from {input.get('file_name', 'audio file')}. "
                f"Transcription: {input.get('transcription_text', '')[:200]}..."
                f"Additional details: correlation_id={input.get('correlation_id')}, "
                f"transcription_path={input.get('transcription_path')}, "
                f"audio_path={input.get('audio_path')}, "
                f"metadata={input.get('metadata', {})}",
        "workflow_instance_id": input.get("correlation_id"),  # Use correlation_id as workflow instance
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
