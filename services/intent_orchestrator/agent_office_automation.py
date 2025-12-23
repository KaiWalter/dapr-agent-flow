from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Optional

from dapr_agents import DurableAgent, tool
from dapr_agents.agents.configs import (
    AgentMemoryConfig,
    AgentPubSubConfig,
    AgentRegistryConfig,
    AgentStateConfig,
)
from dapr_agents.agents.prompting import AgentProfileConfig
from dapr_agents.memory import ConversationDaprStateMemory
from dapr_agents.storage.daprstores.stateservice import StateStoreService
from dapr_agents.workflow.runners.agent import AgentRunner
from dapr_agents.workflow.utils.core import wait_for_shutdown

from models.agents import CreateTaskArgs, SendEmailArgs
from services import task_webhook
from services.llm_factory import create_chat_llm
from services.outlook import OutlookService

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
    logger_instance = logging.getLogger("OfficeAutomation")

    try:
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
            svc.send_email(
                to=recipient, subject=subject_safe, body_html=html, save_to_sent=True
            )
            return "Email sent successfully"
        except RuntimeError as re:
            logger_instance.warning("OutlookService runtime error: %s", re)
            return f"Email failed (auth/service): {str(re)}"
        except Exception as e:
            logger_instance.warning("Unexpected error in send_email: %s", e)
            return f"Email failed: {type(e).__name__}: {str(e)}"
    except Exception as outer_e:
        logger_instance.exception("Critical error in send_email tool: %s", outer_e)
        return f"Email tool failed: {type(outer_e).__name__}"


@tool(args_model=CreateTaskArgs)
def create_todo_item(
    title: str,
    due_date: Optional[str] = None,
    reminder: Optional[str] = None,
    notes: Optional[str] = None,
) -> str:
    """Create a to-do item via webhook."""
    logger_instance = logging.getLogger("OfficeAutomation")

    try:
        webhook_url = os.getenv("CREATE_TODO_ITEM_WEBHOOK_URL")
        if not webhook_url:
            return "Task creation failed: CREATE_TODO_ITEM_WEBHOOK_URL is not configured"

        try:
            result = task_webhook.create_task(
                title=title, due=due_date, reminder=reminder
            )
            return f"Task created successfully: {result}"
        except ValueError as ve:
            logger_instance.warning("Webhook configuration error: %s", ve)
            return f"Task creation failed (config): {str(ve)}"
        except Exception as e:
            logger_instance.warning("Unexpected error in create_todo_item: %s", e)
            return f"Task creation failed: {type(e).__name__}: {str(e)}"
    except Exception as outer_e:
        logger_instance.exception("Critical error in create_todo_item tool: %s", outer_e)
        return f"Task tool failed: {type(outer_e).__name__}"


logger = logging.getLogger("intent.agent_office_automation")


def _build_agent(llm) -> DurableAgent:
    pubsub = AgentPubSubConfig(
        pubsub_name=os.getenv("DAPR_PUBSUB_NAME", "pubsub"),
        agent_topic="office-automation.requests",
        broadcast_topic=os.getenv("DAPR_BROADCAST_TOPIC", "beacon_channel"),
    )
    state = AgentStateConfig(
        store=StateStoreService(
            store_name=os.getenv("DAPR_STATESTORE_NAME", "workflowstatestore"),
            key_prefix="office-automation:",
        )
    )
    registry = AgentRegistryConfig(
        store=StateStoreService(
            store_name=os.getenv("DAPR_AGENTS_REGISTRY_STORE", "agentstatestore")
        ),
        team_name=os.getenv("INTENT_ORCH_TEAM_NAME", "voice2action"),
    )
    memory = AgentMemoryConfig(
        store=ConversationDaprStateMemory(
            store_name=os.getenv("DAPR_MEMORY_STORE_NAME", "memorystatestore"),
            session_id="office-automation",
        )
    )

    profile = AgentProfileConfig(
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
    )

    return DurableAgent(
        profile=profile,
        tools=[send_email, create_todo_item],
        llm=llm,
        pubsub=pubsub,
        registry=registry,
        state=state,
        memory=memory,
    )


async def main() -> None:
    if os.getenv("DEBUGPY_ENABLE", "0") == "1":
        import debugpy

        debugpy.listen(("0.0.0.0", 5678))
        print("debugpy: Waiting for debugger attach on port 5678...")
        debugpy.wait_for_client()

    runner = AgentRunner()
    llm = create_chat_llm()
    agent = _build_agent(llm)

    try:
        runner.register_routes(agent)
        logger.info("OfficeAutomation agent started and awaiting messages")
        await wait_for_shutdown()
    finally:
        runner.shutdown(agent)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
