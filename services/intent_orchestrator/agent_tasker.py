from __future__ import annotations

from dapr_agents import DurableAgent, tool
import asyncio
import json
import logging
import os


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

@tool
def retrieve_transcription(ctx) -> str:
    """
    Retrieve the transcription text from the file at 'transcription_path' in ctx.input or ctx.event.
    """
    path = None
    if hasattr(ctx, 'input') and ctx.input and 'transcription_path' in ctx.input:
        path = ctx.input['transcription_path']
    elif hasattr(ctx, 'event') and ctx.event and 'transcription_path' in ctx.event:
        path = ctx.event['transcription_path']
    if path:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Expect either a dict with 'text' or just a string
            if isinstance(data, dict) and 'text' in data:
                return data['text']
            if isinstance(data, str):
                return data
        except Exception as e:
            return f"[Error reading transcription: {e}]"
    return ""

async def main():
    if os.getenv("DEBUGPY_ENABLE", "0") == "1":
        import debugpy
        debugpy.listen(("0.0.0.0", 5678))
        print("debugpy: Waiting for debugger attach on port 5678...")
        debugpy.wait_for_client()
    
    try:
        # The agent registry must be stored in the agentstatestore (not the workflowstatestore),
        # matching the orchestrator and other agents for correct agent discovery and coordination.
        agent = (
            DurableAgent(
                name="TaskPlanner",
                role="Planner",
                goal="Plan and create tasks from voice transcription.",
                instructions=[
                    "Extract actionable items and due dates.",
                    "Create structured task objects with title, due date, and notes.",
                    "Respond concisely and only with structured results."
                ],
                tools=[retrieve_transcription],
                message_bus_name=os.getenv("DAPR_PUBSUB_NAME", "pubsub"),
                state_store_name=os.getenv("DAPR_STATESTORE_NAME", "workflowstatestore"),
                state_key="workflow_state",
                agents_registry_store_name=os.getenv("DAPR_AGENTS_REGISTRY_STORE", "agentstatestore"),
                agents_registry_key="agents_registry",
                broadcast_topic_name=os.getenv("DAPR_BROADCAST_TOPIC", "beacon_channel"),
            )
            .as_service(port=int(os.getenv("TASKPLANNER_PORT", os.getenv("APP_PORT", "5101"))))
        )

        await agent.start()
    except Exception as e:
        logging.exception("Error starting TaskPlanner agent: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
