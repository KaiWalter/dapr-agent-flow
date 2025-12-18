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
            svc.send_email(to=recipient, subject=subject_safe, body_html=html, save_to_sent=True)
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
def create_todo_item(title: str, due_date: Optional[str] = None, reminder: Optional[str] = None, notes: Optional[str] = None) -> str:
    """Create a to-do item via webhook."""
    logger_instance = logging.getLogger("OfficeAutomation")
    
    try:
        webhook_url = os.getenv("CREATE_TODO_ITEM_WEBHOOK_URL")
        if not webhook_url:
            return "Task creation failed: CREATE_TODO_ITEM_WEBHOOK_URL is not configured"
        
        try:
            result = task_webhook.create_task(title=title, due=due_date, reminder=reminder)
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
DEFAULT_PORT = 5102


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
        logger.debug("Could not patch office automation agent stop; continuing without patch.")


def _build_agent(llm) -> DurableAgent:
    pubsub = AgentPubSubConfig(
        pubsub_name=os.getenv("DAPR_PUBSUB_NAME", "pubsub"),
        broadcast_topic=os.getenv("DAPR_BROADCAST_TOPIC", "beacon_channel"),
    )
    state = AgentStateConfig(
        store=StateStoreService(store_name=os.getenv("DAPR_STATESTORE_NAME", "workflowstatestore")),
        state_key=os.getenv("INTENT_OFFICE_STATE_KEY", "workflow_state"),
    )
    registry = AgentRegistryConfig(
        store=StateStoreService(store_name=os.getenv("DAPR_AGENTS_REGISTRY_STORE", "agentstatestore")),
        team_name=os.getenv("INTENT_ORCH_TEAM_NAME", "voice2action"),
    )
    memory = AgentMemoryConfig(
        store=ConversationDaprStateMemory(
            store_name=os.getenv("DAPR_MEMORY_STORE_NAME", "memorystatestore"),
            session_id=f"office-automation-{uuid.uuid4().hex[:8]}",
        )
    )

    return DurableAgent(
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
        logger.info("OfficeAutomation agent started and awaiting messages")
        runner.serve(agent, port=app_port)
    except KeyboardInterrupt:
        logger.info("OfficeAutomation agent interrupted")
    except Exception as exc:
        logger.exception("Error starting OfficeAutomation agent: %s", exc)
    finally:
        try:
            runner.shutdown()
        except Exception:
            logger.exception("Error shutting down AgentRunner for OfficeAutomation agent")
        if agent is not None:
            try:
                stop_fn = agent.stop
                if asyncio.iscoroutinefunction(stop_fn):
                    asyncio.run(stop_fn())
                else:
                    stop_fn()
            except Exception:
                logger.exception("Error stopping OfficeAutomation agent")


if __name__ == "__main__":
    main()
