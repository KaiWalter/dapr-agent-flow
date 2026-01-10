from __future__ import annotations

import logging
import os
from typing import Optional

import dapr.ext.workflow as wf
from dapr_agents import LLMOrchestrator
from dapr_agents.agents.configs import (
    AgentExecutionConfig,
    AgentPubSubConfig,
    AgentRegistryConfig,
    AgentStateConfig,
)
from dapr_agents.llm.chat import ChatClientBase
from dapr_agents.storage.daprstores.stateservice import StateStoreService
from dapr_agents.workflow.runners.agent import AgentRunner

from services.llm_factory import create_chat_llm

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
logging.getLogger("werkzeug").setLevel(logging.WARNING)
logger = logging.getLogger("intent.orchestrator")


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


def _log_final_summary(summary: str) -> None:
    if summary:
        logger.info("IntentOrchestrator final summary: %s", summary)
    else:
        logger.info("IntentOrchestrator completed without a summary.")


def _build_orchestrator(llm: ChatClientBase) -> LLMOrchestrator:
    pubsub = AgentPubSubConfig(
        pubsub_name=os.getenv("DAPR_PUBSUB_NAME", "pubsub"),
        agent_topic=os.getenv("DAPR_INTENT_ORCHESTRATOR_TOPIC", "intent.orchestrator.requests"),
        broadcast_topic=os.getenv("DAPR_BROADCAST_TOPIC", "beacon_channel"),
    )
    state = AgentStateConfig(
        store=StateStoreService(
        store_name=os.getenv("DAPR_STATESTORE_NAME", "workflowstatestore"),
        key_prefix="intent.orchestrator:",
    ),
    )
    registry = AgentRegistryConfig(
        store=StateStoreService(
            store_name=os.getenv("DAPR_AGENTS_REGISTRY_STORE", "agentstatestore"),
        ),
        team_name=os.getenv("INTENT_ORCH_TEAM_NAME", "voice2action"),
    )
    execution = AgentExecutionConfig(
        max_iterations=_get_env_int("INTENT_ORCH_MAX_ITERATIONS", 6)
    )

    orchestrator_name = os.getenv("ORCHESTRATOR_NAME", "intent.orchestrator.requests")

    return LLMOrchestrator(
        name=orchestrator_name,
        llm=llm,
        pubsub=pubsub,
        state=state,
        registry=registry,
        execution=execution,
        agent_metadata={
            "type": "LLMOrchestrator",
            "description": "LLM-driven Orchestrator",
        },
        final_summary_callback=_log_final_summary,
        runtime=wf.WorkflowRuntime(),
    )


def main() -> None:
    if os.getenv("DEBUGPY_ENABLE", "0") == "1":
        import debugpy

        debugpy.listen(("0.0.0.0", 5678))
        print("debugpy: Waiting for debugger attach on port 5678...")
        debugpy.wait_for_client()

    app_port = _get_env_int("DAPR_APP_PORT", 5100)
    llm = create_chat_llm()
    orchestrator = _build_orchestrator(llm)
    runner = AgentRunner()

    try:
        logger.info("IntentOrchestrator workflow runtime started")
        runner.serve(orchestrator, port=app_port)
    finally:
        runner.shutdown(orchestrator)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
