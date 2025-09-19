from __future__ import annotations
from dapr_agents import LLMOrchestrator
from services.llm_factory import create_chat_llm
import os
import logging
import asyncio

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
# Suppress werkzeug INFO logs
logging.getLogger("werkzeug").setLevel(logging.WARNING)

async def main():
    if os.getenv("DEBUGPY_ENABLE", "0") == "1":
        import debugpy
        debugpy.listen(("0.0.0.0", 5678))
        print("debugpy: Waiting for debugger attach on port 5678...")
        debugpy.wait_for_client()
        
    try:
        llm = create_chat_llm()
        orchestrator = LLMOrchestrator(
            name="IntentOrchestrator",
            llm=llm,
            local_state_path="./.dapr_state",
            message_bus_name=os.getenv("DAPR_PUBSUB_NAME", "pubsub"),
            state_store_name=os.getenv("DAPR_STATESTORE_NAME", "workflowstatestore"),
            state_key="workflow_state",
            agents_registry_store_name=os.getenv("DAPR_AGENTS_REGISTRY_STORE", "agentstatestore"),
            agents_registry_key="agents_registry",
            orchestrator_topic_name=os.getenv("DAPR_INTENT_ORCHESTRATOR_TOPIC", "IntentOrchestrator"),
            broadcast_topic_name=os.getenv("DAPR_BROADCAST_TOPIC", "beacon_channel"),
            max_iterations=int(os.getenv("INTENT_ORCH_MAX_ITERATIONS", "6")),
        ).as_service(port=int(os.getenv("DAPR_APP_PORT", "5100")))

        # Patch stop() to be a coroutine accepting arbitrary args to avoid signal handler TypeError
        async def stop_ignore_args(*args, **kwargs):  # pragma: no cover - runtime patch
            return None
        try:  # pragma: no cover - defensive
            orchestrator.stop = stop_ignore_args  # type: ignore[assignment]
            orchestrator.__class__.stop = stop_ignore_args  # type: ignore[assignment]
        except Exception:
            pass

        await orchestrator.start()
    except Exception as e:  # pragma: no cover - startup failure path
        logging.exception("Error starting IntentOrchestrator service: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
