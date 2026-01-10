from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
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
        # Check for OFFLINE_MODE
        if os.getenv("OFFLINE_MODE", "false").lower() == "true":
            work_dir = ".work"
            os.makedirs(work_dir, exist_ok=True)
            
            activity_id = str(uuid.uuid4())
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{activity_id}_send_email_{timestamp}.json"
            filepath = os.path.join(work_dir, filename)
            
            activity_data = {
                "tool": "send_email",
                "args": {
                    "subject": subject,
                    "body": body
                },
                "timestamp": datetime.now().isoformat()
            }
            
            with open(filepath, "w") as f:
                json.dump(activity_data, f, indent=2)
                
            return f"Activity recorded in offline mode: {filename}"

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
        # Check for OFFLINE_MODE
        if os.getenv("OFFLINE_MODE", "false").lower() == "true":
            work_dir = ".work"
            os.makedirs(work_dir, exist_ok=True)
            
            activity_id = str(uuid.uuid4())
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{activity_id}_create_todo_item_{timestamp}.json"
            filepath = os.path.join(work_dir, filename)
            
            activity_data = {
                "tool": "create_todo_item",
                "args": {
                    "title": title,
                    "due_date": due_date,
                    "reminder": reminder,
                    "notes": notes
                },
                "timestamp": datetime.now().isoformat()
            }
            
            with open(filepath, "w") as f:
                json.dump(activity_data, f, indent=2)
                
            return f"Activity recorded in offline mode: {filename}"

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
        llm=llm,
        tools=[send_email, create_todo_item],
        pubsub=pubsub,
        registry=registry,
        state=state,
        memory=memory,
    )


def main():
    if os.getenv("DEBUGPY_ENABLE", "0") == "1":
        import debugpy

        debugpy.listen(("0.0.0.0", 5678))
        print("debugpy: Waiting for debugger attach on port 5678...")
        debugpy.wait_for_client()

    runner = AgentRunner()
    llm = create_chat_llm()
    agent = _build_agent(llm)

    try:
        runner.serve(agent, host="0.0.0.0", port=int(os.getenv("DAPR_APP_PORT", 5102)))
    finally:
        runner.shutdown(agent)


if __name__ == "__main__":
    main()
