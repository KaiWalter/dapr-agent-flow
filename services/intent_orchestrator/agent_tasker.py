from __future__ import annotations

from dapr_agents import DurableAgent, tool, OpenAIChatClient
from dapr_agents.memory import ConversationDaprStateMemory
from models.agents import RetrieveTranscriptionArgs
from typing import Optional
import asyncio
import json
import logging
import os
import uuid

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


# Timezone tools: single source of truth for process timezone
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None  # type: ignore

def _get_office_timezone():
    tz_name = os.getenv("OFFICE_TIMEZONE")
    if tz_name and ZoneInfo is not None:
        try:
            return ZoneInfo(tz_name)
        except Exception:
            pass
    # fallback to system timezone via tzlocal; last resort UTC
    try:
        import tzlocal
        return tzlocal.get_localzone()
    except Exception:
        from datetime import timezone as _timezone
        return _timezone.utc

@tool()
def get_office_timezone(*, unused: str = "") -> str:
    """Return the effective timezone name for the process (from OFFICE_TIMEZONE or system default)."""
    tz = os.getenv("OFFICE_TIMEZONE")
    if tz:
        return tz
    try:
        import tzlocal
        return str(tzlocal.get_localzone())
    except Exception:
        return "UTC"

@tool()
def get_office_timezone_offset(*, unused: str = "") -> str:
    """Return the current offset for the effective timezone in ISO 8601 format (e.g., +02:00, Z)."""
    tz = _get_office_timezone()
    now = datetime.now(tz)
    offset = now.utcoffset()
    if offset is None or offset.total_seconds() == 0:
        return "Z"
    sign = "+" if offset.total_seconds() >= 0 else "-"
    hours, remainder = divmod(abs(int(offset.total_seconds())), 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{sign}{hours:02}:{minutes:02}"

async def main():
    if os.getenv("DEBUGPY_ENABLE", "0") == "1":
        import debugpy
        debugpy.listen(("0.0.0.0", 5678))
        print("debugpy: Waiting for debugger attach on port 5678...")
        debugpy.wait_for_client()

    try:
        openai_llm = OpenAIChatClient(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
        agent = (
            DurableAgent(
                name="TaskPlanner",
                role="Planner",
                goal= "Provide all kind of input information e.g. voice recording transcript and provide additional reference information which are helpful to the process.",
                instructions=[
                    "You are an agent in a multi-step process."
                    "You provide utility to the process and none of your actions are to be considered to conclude the process.",
                    "You add timezone and timezone offset information to the process when dates are handled e.g. due dates, reminders.",
                    "Available tools and arguments:",
                    "- read_transcription(transcription_path: string)",
                    "- get_office_timezone()",
                    "- get_office_timezone_offset()",
                ],
                tools=[retrieve_transcription, get_office_timezone, get_office_timezone_offset],
                llm=openai_llm,
                local_state_path="./.dapr_state",

                # PubSub input
                message_bus_name=os.getenv("DAPR_PUBSUB_NAME", "pubsub"),
                broadcast_topic_name=os.getenv(
                    "DAPR_BROADCAST_TOPIC", "beacon_channel"),

                # Execution state
                state_store_name=os.getenv(
                    "DAPR_STATESTORE_NAME", "workflowstatestore"),
                state_key="workflow_state",

                # Memory state
                memory=ConversationDaprStateMemory(
                    store_name="memorystatestore", session_id=f"task-planner-{uuid.uuid4().hex[:8]}"
                ),

                # Discovery                
                agents_registry_store_name=os.getenv(
                    "DAPR_AGENTS_REGISTRY_STORE", "agentstatestore"),
                agents_registry_key="agents_registry",
            )
            .as_service(port=int(os.getenv("DAPR_APP_PORT", "5101")))
        )
        # Patch stop() to be a coroutine accepting arbitrary args to avoid signal handler TypeError
        async def stop_ignore_args(*args, **kwargs):
            return None
        try:
            agent.stop = stop_ignore_args  # type: ignore[assignment]
            agent.__class__.stop = stop_ignore_args  # type: ignore[assignment]
        except Exception:
            pass

        await agent.start()
    except Exception as e:
        logging.exception("Error starting TaskPlanner agent: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
