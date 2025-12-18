from __future__ import annotations

from dapr_agents import DurableAgent, tool
from dapr_agents.agents.configs import (
    AgentMemoryConfig,
    AgentPubSubConfig,
    AgentRegistryConfig,
    AgentStateConfig,
)
from dapr_agents.memory import ConversationDaprStateMemory
from dapr_agents.storage.daprstores.stateservice import StateStoreService
from dapr_agents.workflow.runners.agent import AgentRunner
from services.llm_factory import create_chat_llm
from models.agents import RetrieveTranscriptionArgs
from datetime import datetime, timezone
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
def retrieve_transcription(transcription_path: str) -> str:
    """Return transcription text from a file path or provided text string.

    - If 'transcription_path' is set, attempts to load JSON and read the 'text' field
      (or treat file contents as a raw string if not JSON).
    - Otherwise returns 'transcription_text' if provided.
    - Returns empty string if nothing is available.
    """
    if transcription_path:
        try:
            with open(transcription_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except Exception:
                    # Not JSON, read as plain text
                    f.seek(0)
                    return f.read()
            if isinstance(data, dict) and "text" in data:
                return data["text"]
            if isinstance(data, str):
                return data
            return json.dumps(data)
        except Exception as e:
            return f"[Error reading transcription: {e}]"
    return ""


# Timezone tools: single source of truth for process timezone

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


logger = logging.getLogger("intent.agent_facilitator")
DEFAULT_PORT = 5101


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning(
            "Invalid integer for %s (%r); falling back to %s",
            name,
            value,
            default,
        )
        return default


def _patch_stop(agent: DurableAgent) -> None:
    original_stop = getattr(agent, "stop", None)
    if original_stop is None or asyncio.iscoroutinefunction(original_stop):
        return

    async def _stop_async(*args, **kwargs):
        return original_stop(*args, **kwargs)

    try:
        agent.stop = _stop_async  # type: ignore[assignment]
        agent.__class__.stop = _stop_async  # type: ignore[assignment]
    except Exception:
        logger.debug("Could not patch facilitator agent stop; continuing without patch.")


def _build_agent(llm) -> DurableAgent:
    pubsub = AgentPubSubConfig(
        pubsub_name=os.getenv("DAPR_PUBSUB_NAME", "pubsub"),
        broadcast_topic=os.getenv("DAPR_BROADCAST_TOPIC", "beacon_channel"),
    )
    state = AgentStateConfig(
        store=StateStoreService(store_name=os.getenv("DAPR_STATESTORE_NAME", "workflowstatestore")),
        state_key=os.getenv("INTENT_FACILITATOR_STATE_KEY", "workflow_state"),
    )
    registry = AgentRegistryConfig(
        store=StateStoreService(store_name=os.getenv("DAPR_AGENTS_REGISTRY_STORE", "agentstatestore")),
        team_name=os.getenv("INTENT_ORCH_TEAM_NAME", "voice2action"),
    )
    memory = AgentMemoryConfig(
        store=ConversationDaprStateMemory(
            store_name=os.getenv("DAPR_MEMORY_STORE_NAME", "memorystatestore"),
            session_id=f"task-planner-{uuid.uuid4().hex[:8]}",
        )
    )

    return DurableAgent(
        name="Facilitator",
        role="Based on user requests provide essential and auxiliary services, tools and information.",
        goal="Respond to all inquiries as specific as possible. Do not conjecture intent that is not explicitly stated.",
        instructions=[
            "Essential services and tools that have highest priority:",
            "Use tool read_transcription to access, check or retrieve voice transcription. Take the path to transcription file from mission briefing or task instructions.\n",
            "Auxiliary services and tools to be used when one of the essential services already has been utilized:"
            "Add timezone and timezone offset information to the process when dates are handled e.g. due dates, reminders.\n",
            "Available tools and arguments:",
            "- read_transcription(transcription_path: string)",
            "- get_office_timezone()",
            "- get_office_timezone_offset()",
            "\n",
            "You provide utility to the process and none of your actions are to be considered to conclude the process.",
        ],
        tools=[
            retrieve_transcription,
            get_office_timezone,
            get_office_timezone_offset,
        ],
        llm=llm,
        pubsub=pubsub,
        registry=registry,
        state=state,
        memory=memory,
    )


def main() -> None:
    if os.getenv("DEBUGPY_ENABLE", "0") == "1":
        import debugpy

        debugpy.listen(("0.0.0.0", 5678))
        print("debugpy: Waiting for debugger attach on port 5678...")
        debugpy.wait_for_client()

    runner = AgentRunner()
    agent: DurableAgent | None = None
    app_port = _get_env_int("DAPR_APP_PORT", DEFAULT_PORT)

    try:
        llm = create_chat_llm()
        agent = _build_agent(llm)
        _patch_stop(agent)
        agent.start()
        logger.info("Facilitator agent started and awaiting messages")
        runner.serve(agent, port=app_port)
    except KeyboardInterrupt:
        logger.info("Facilitator agent interrupted")
    except Exception as exc:
        logger.exception("Error starting Facilitator agent: %s", exc)
    finally:
        try:
            runner.shutdown()
        except Exception:
            logger.exception("Error shutting down AgentRunner for Facilitator agent")
        if agent is not None:
            try:
                stop_fn = agent.stop
                if asyncio.iscoroutinefunction(stop_fn):
                    asyncio.run(stop_fn())
                else:
                    stop_fn()
            except Exception:
                logger.exception("Error stopping Facilitator agent")


if __name__ == "__main__":
    main()
