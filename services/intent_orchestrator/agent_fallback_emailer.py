from __future__ import annotations
from dapr_agents import DurableAgent, tool
import asyncio
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
def send_email(ctx) -> str:
    """
    Send an email.
    Expects the email content directly in ctx.
    """
    if ctx:
        text = ctx
    else:
        text = "(no email input provided)"

    html = f"""
    <html>
    <body>
        <p>{text}</p>
    </body>
    </html>
    """
    os.makedirs("downloads", exist_ok=True)
    with open("downloads/email.html", "w", encoding="utf-8") as f:
        f.write(html)
    return "Email stored as downloads/email.html"

@tool
def create_task(ctx) -> str:
    """
    Creates a task.
    Expects the task content directly in ctx.
    """
    if ctx:
        text = ctx
    else:
        text = "(no email task provided)"

    html = f"""
    <html>
    <body>
        <p>{text}</p>
    </body>
    </html>
    """
    os.makedirs("downloads", exist_ok=True)
    with open("downloads/task.html", "w", encoding="utf-8") as f:
        f.write(html)
    return "Task stored as downloads/task.html"

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
                role="Execution",
                goal=(
                    "Create a task if intended or send an email when no clear task action is found."
                ),
                instructions=[
                    "Create a task if intended.",
                    "If no task is intended, send an email."
                ],
                tools=[send_email, create_task],
                local_state_path="./.dapr_state",
                message_bus_name=os.getenv("DAPR_PUBSUB_NAME", "pubsub"),
                state_store_name=os.getenv("DAPR_STATESTORE_NAME", "workflowstatestore"),
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
