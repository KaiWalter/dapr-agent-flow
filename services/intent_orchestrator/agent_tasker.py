from __future__ import annotations

from dapr_agents import DurableAgent, tool
import asyncio
import json
import logging
import os
from typing import Optional
from pydantic import BaseModel


# Root logger setup
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


class RetrieveTranscriptionArgs(BaseModel):
    """Schema for retrieving transcription content.

    Provide either a 'transcription_path' to read JSON from disk or a raw
    'transcription_text' directly. If both are provided, the file path wins.
    """
    transcription_path: Optional[str] = None
    transcription_text: Optional[str] = None


@tool(args_model=RetrieveTranscriptionArgs)
def retrieve_transcription(
    transcription_path: Optional[str] = None,
    transcription_text: Optional[str] = None,
) -> str:
    """Return transcription text from a file path or provided text string.

    - If 'transcription_path' is set, attempts to load JSON and read the 'text' field
      (or treat file contents as a raw string if not JSON).
    - Otherwise returns 'transcription_text' if provided.
    - Returns empty string if nothing is available.
    """
    if transcription_path:
        try:
            with open(transcription_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except Exception:
                    # Not JSON, read as plain text
                    f.seek(0)
                    return f.read()
            if isinstance(data, dict) and 'text' in data:
                return data['text']
            if isinstance(data, str):
                return data
            return json.dumps(data)
        except Exception as e:
            return f"[Error reading transcription: {e}]"
    if transcription_text:
        return transcription_text
    return ""


async def main():
    if os.getenv("DEBUGPY_ENABLE", "0") == "1":
        import debugpy
        debugpy.listen(("0.0.0.0", 5678))
        print("debugpy: Waiting for debugger attach on port 5678...")
        debugpy.wait_for_client()

    try:
        agent = (
            DurableAgent(
                name="TaskPlanner",
                role="Planner",
                goal="Handle and provide all kind of input information e.g. voice recording transcript and provide additional reference information which are helpful to the process.",
                instructions=[
                    "Start retrieving transcription content which states the users intent.",
                    "Use tool read_transcription to get the transcription text.",
                    "Focus on extracting users intent, actionable items, due dates or reminders.",
                    "You provide utility to the process and none of your actions are to be considered to conclude the process.",
                    "Available tools and arguments:",
                    "- read_transcription(transcription_path: string)",
                ],
                tools=[retrieve_transcription],
                local_state_path="./.dapr_state",
                message_bus_name=os.getenv("DAPR_PUBSUB_NAME", "pubsub"),
                state_store_name=os.getenv(
                    "DAPR_STATESTORE_NAME", "workflowstatestore"),
                state_key="workflow_state",
                agents_registry_store_name=os.getenv(
                    "DAPR_AGENTS_REGISTRY_STORE", "agentstatestore"),
                agents_registry_key="agents_registry",
                broadcast_topic_name=os.getenv(
                    "DAPR_BROADCAST_TOPIC", "beacon_channel")
            )
            .as_service(port=int(os.getenv("TASKPLANNER_PORT", os.getenv("APP_PORT", "5101"))))
        )

        await agent.start()
    except Exception as e:
        logging.exception("Error starting TaskPlanner agent: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
