from __future__ import annotations

from dapr_agents import DurableAgent, tool
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import asyncio
import logging
import os
from services.outlook import OutlookService
from services import task_webhook

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


class SendEmailArgs(BaseModel):
    """Schema for the send_email tool."""
    subject: str = Field(description="Subject of the email - name of the transcription file without file extensions")
    body: str = Field(description="The complete transcription text or a summary of the user's intent")


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


class CreateTaskArgs(BaseModel):
    """Schema for the create_task tool."""
    title: str = Field(description="Title of the task - a summarization of the user's intent")
    due_date: Optional[str] = Field(
        default=None,
        description="Due date as ISO 8601 datetime string (e.g., 2025-08-16T14:30:00Z or 2025-08-16T14:30:00+00:00)",
    )
    reminder: Optional[str] = Field(
        default=None,
        description="Reminder ISO 8601 datetime string (e.g., 2025-08-16T14:30:00Z or 2025-08-16T14:30:00+00:00)",
    )
    notes: str = Field(default=None, description="Notes on the task - the complete transcription text or a summary of the user's intent")

    @field_validator("due_date", "reminder")
    @classmethod
    def _validate_iso8601(cls, v: Optional[str]):
        if v is None:
            return v
        import re
        # Basic ISO 8601 datetime with optional fractional seconds and timezone (Z or ±HH:MM)
        pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+\-]\d{2}:\d{2})$"
        if not re.match(pattern, v):
            raise ValueError(
                "must be an ISO 8601 datetime string, e.g., 2025-08-16T14:30:00Z")
        return v


@tool(args_model=CreateTaskArgs)
def create_task(title: str, due_date: Optional[str] = None, reminder: Optional[str] = None, notes: Optional[str] = None) -> str:
    """Create a task via webhook (FR008)."""
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
        agent = (
            DurableAgent(
                name="OfficeAutomation",
                role="Office Assistant",
                goal="Handle all jobs that require interaction with personal productivity like sending emails or creating to-do tasks.",
                instructions=[
                    "From the users intent or actionable items you provide those tools which help to conclude the process.",
                    "Synonomous to create task can be: follow up, to-do, todo, task, create to-do, create todo.",
                    "Available tools and arguments:",
                    "- create_task(title: string, due_date?: ISO8601 date time string, reminder?: ISO8601 date time string, notes?: string)",
                    "- send_email(subject?: string, body?: string)",
                    "All date time string information needs to be converted into ISO8601 format. Consider the following:",
                    "- when no time is specified, use the start of the business day (06:00:00) as default",
                    "- add timezone offset to the date time string, e.g., Z or +00:00",
                ],
                tools=[send_email, create_task],
                local_state_path="./.dapr_state",
                message_bus_name=os.getenv("DAPR_PUBSUB_NAME", "pubsub"),
                state_store_name=os.getenv(
                    "DAPR_STATESTORE_NAME", "workflowstatestore"),
                state_key="workflow_state",
                agents_registry_store_name=os.getenv(
                    "DAPR_AGENTS_REGISTRY_STORE", "agentstatestore"),
                agents_registry_key="agents_registry",
                broadcast_topic_name=os.getenv(
                    "DAPR_BROADCAST_TOPIC", "beacon_channel")
            )
            .as_service(port=int(os.getenv("DAPR_APP_PORT", "5102")))
        )
        await agent.start()
    except Exception as e:
        logging.exception("Error starting OfficeAutomation agent: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
