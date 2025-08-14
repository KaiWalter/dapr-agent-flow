from __future__ import annotations
from dapr_agents import LLMOrchestrator
import os
import logging
import asyncio
import debugpy

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

async def main():
    if os.getenv("DEBUGPY_ENABLE", "0") == "1":
        import debugpy
        debugpy.listen(("0.0.0.0", 5678))
        print("debugpy: Waiting for debugger attach on port 5678...")
        debugpy.wait_for_client()
        
    try:
        orchestrator = (
            LLMOrchestrator(
                name="LLMOrchestrator",
                message_bus_name=os.getenv("DAPR_PUBSUB_NAME", "pubsub"),
                state_store_name=os.getenv("DAPR_STATESTORE_NAME", "workflowstatestore"),
                state_key="workflow_state",
                agents_registry_store_name=os.getenv("DAPR_AGENTS_REGISTRY_STORE", "agentstatestore"),
                agents_registry_key="agents_registry",
                broadcast_topic_name=os.getenv("DAPR_BROADCAST_TOPIC", "beacon_channel"),
                max_iterations=int(os.getenv("LLM_ORCH_MAX_ITERATIONS", "3")),
            ).as_service(port=int(os.getenv("LLM_ORCH_PORT", "5100")))
        )

        await orchestrator.start()
    except Exception as e:
        logging.exception("Error starting LLMOrchestrator service: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
