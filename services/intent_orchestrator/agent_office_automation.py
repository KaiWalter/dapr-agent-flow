from __future__ import annotations

from dapr_agents import DurableAgent, tool
from services.llm_factory import create_chat_llm
from dapr_agents.memory import ConversationDaprStateMemory
from models.agents import SendEmailArgs, CreateTaskArgs
from services import task_webhook
from services.outlook import OutlookService
from typing import Optional
import asyncio
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


@tool(args_model=SendEmailArgs)
def send_email(subject: Optional[str] = None, body: Optional[str] = None) -> str:
    """Send an email to the configured recipient using Outlook (MS Graph)."""
    recipient = os.getenv("SEND_MAIL_RECIPIENT")
    if not recipient:
        return "Email failed: SEND_MAIL_RECIPIENT is not configured"

    subject_safe = subject.strip() if subject else "No subject"
    text = body or "(no email body provided)"
    html = f"""
    <html>
    <body>
        <p>{text}</p>
    </body>
    </html>
    """
    try:
        svc = OutlookService()
        svc.send_email(to=recipient, subject=subject_safe, body_html=html, save_to_sent=True)
        return "Email sent"
    except Exception as e:
        logging.getLogger("OfficeAutomation").exception("send_email failed: %s", e)
        return f"Email failed: {e}"


@tool(args_model=CreateTaskArgs)
def create_todo_item(title: str, due_date: Optional[str] = None, reminder: Optional[str] = None, notes: Optional[str] = None) -> str:
    """Create a to-do item via webhook."""
    try:
        _ = task_webhook.create_task(title=title, due=due_date, reminder=reminder)
        return "Task created"
    except Exception as e:
        logging.getLogger("OfficeAutomation").exception("create_task failed: %s", e)
        return f"Task creation failed: {e}"


async def main():
    if os.getenv("DEBUGPY_ENABLE", "0") == "1":
        import debugpy
        debugpy.listen(("0.0.0.0", 5678))
        print("debugpy: Waiting for debugger attach on port 5678...")
        debugpy.wait_for_client()

    try:
        llm = create_chat_llm()
        agent = (
            DurableAgent(
                name="OfficeAutomation",
                role="Office Assistant",
                goal="Handle all jobs that require interaction with personal productivity tools like sending emails or creating to-do items.",
                instructions=[
                    "From the users intent or actionable items you provide those tools which help to conclude the process.",
                    "Synonomous to create a to-do item in the user's intent can be: follow up, create a task.",
                    "Available tools and arguments:",
                    "- create_todo_item(title: string, due_date?: ISO8601 date time string, reminder?: ISO8601 date time string, notes?: string)",
                    "- send_email(subject?: string, body?: string)",
                    "All date time information needs to be converted into ISO8601 format. Consider the following:",
                    "- when no time is specified, use the start of the business day (06:00:00) as default",
                    "- add timezone offset to the date time string, e.g., Z or +00:00",
                ],
                tools=[send_email, create_todo_item],
                llm=llm,
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
                    store_name="memorystatestore", session_id=f"office-automation-{uuid.uuid4().hex[:8]}"
                ),

                # Discovery                
                agents_registry_store_name=os.getenv(
                    "DAPR_AGENTS_REGISTRY_STORE", "agentstatestore"),
                agents_registry_key="agents_registry",
            )
            .as_service(port=int(os.getenv("DAPR_APP_PORT", "5102")))  # type: ignore[attr-defined]
        )
        # Patch stop() to be a coroutine accepting arbitrary args to avoid signal handler TypeError
        async def stop_ignore_args(*args, **kwargs):
            return None
        try:
            agent.stop = stop_ignore_args  # type: ignore[assignment]
            # Also patch the class method so internal references use the same signature
            agent.__class__.stop = stop_ignore_args  # type: ignore[assignment]
        except Exception:
            pass

        await agent.start()
    except Exception as e:
        logging.exception("Error starting OfficeAutomation agent: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
