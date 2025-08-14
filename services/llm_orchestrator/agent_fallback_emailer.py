from __future__ import annotations
from dapr_agents import DurableAgent
import asyncio
import logging
import os
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
        agent = (
            DurableAgent(
            name="FallbackEmailer",
            role="Emailer",
            goal=(
                "Send a concise email summary when no clear task action is found."
            ),
            instructions=[
                "Summarize the transcription in 1-2 sentences.",
                "Ask for clarification if needed.",
                "Keep tone professional and concise."
            ],
            message_bus_name=os.getenv("DAPR_PUBSUB_NAME", "pubsub"),
            state_store_name=os.getenv("DAPR_STATESTORE_NAME", "statestore"),
            state_key="workflow_state",
            agents_registry_store_name=os.getenv("DAPR_AGENTS_REGISTRY_STORE", "agentstatestore"),
            agents_registry_key="agents_registry",
            broadcast_topic_name=os.getenv("DAPR_BROADCAST_TOPIC", "beacon_channel"),
            )
            .as_service(port=int(os.getenv("FALLBACK_EMAILER_PORT", os.getenv("APP_PORT", "5102"))))
        )
        await agent.start()
    except Exception as e:
        logging.exception("Error starting FallbackEmailer agent: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
