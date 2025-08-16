from __future__ import annotations

from dapr_agents import DurableAgent, tool
import asyncio
import logging
import os
from pydantic import BaseModel
from typing import Optional
import json

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
    to: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None


@tool(args_model=SendEmailArgs)
def send_email(to: Optional[str] = None, subject: Optional[str] = None, body: Optional[str] = None) -> str:
    """Persist a minimal email preview to downloads/email.html.

    The tool only renders a simple HTML preview; real email sending is intentionally stubbed.
    """
    text = body or "(no email body provided)"
    header = "".join([
        f"<div><b>To:</b> {to}</div>" if to else "",
        f"<div><b>Subject:</b> {subject}</div>" if subject else "",
    ])
    html = f"""
    <html>
    <body>
        {header}
        <p>{text}</p>
    </body>
    </html>
    """
    os.makedirs("downloads", exist_ok=True)
    with open("downloads/email.html", "w", encoding="utf-8") as f:
        f.write(html)
    return "Email stored as downloads/email.html"


class CreateTaskArgs(BaseModel):
    """Schema for the create_task tool."""
    title: str
    due_date: Optional[str] = None
    notes: Optional[str] = None


@tool(args_model=CreateTaskArgs)
def create_task(title: str, due_date: Optional[str] = None, notes: Optional[str] = None) -> str:
    """Persist a minimal task preview to downloads/task.html.

    The tool only renders a simple HTML preview; real task creation is intentionally stubbed.
    """
    html = f"""
    <html>
    <body>
        <h3>{title}</h3>
        {f"<div><b>Due:</b> {due_date}</div>" if due_date else ""}
        {f"<div><b>Notes:</b> {notes}</div>" if notes else ""}
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
                name="OfficeAutomation",
                role="Office Assistant",
                goal=(
                    "Handle all activity related to office automation, communication: send emails, create to-do tasks."
                ),
                instructions=[
                    "You MUST complete tasks by invoking tools, not by describing actions.",
                    "Available tools and arguments:",
                    "- send_email(to?: string, subject?: string, body?: string)",
                    "- create_task(title: string, due_date?: string, notes?: string)",
                    "Decision policy: Prefer create_task when the user mentions todos/tasks/reminders; otherwise fallback to send_email.",
                    "Execution policy for send_email: call the tool immediately with best-effort arguments; derive a concise subject from the request (default 'Note' if unclear) and ALWAYS provide a non-empty body (use the user's message or a short summary). The 'to' field may be omitted if unknown; do not block on it.",
                    "Execution policy for create_task: always provide a clear, action-oriented title; include due_date and notes when available.",
                    "Do NOT ask for confirmation unless explicitly requested by the user. Do not end with only a plan; if an action is required, end by calling a tool.",
                    "Post-action: after a tool returns, output only a brief confirmation (e.g., 'Email stored...' or 'Task stored...'). Do not claim an action occurred unless the tool was actually called.",
                ],
                tools=[send_email, create_task],
                local_state_path="./.dapr_state",
                message_bus_name=os.getenv("DAPR_PUBSUB_NAME", "pubsub"),
                state_store_name=os.getenv("DAPR_STATESTORE_NAME", "workflowstatestore"),
                state_key="workflow_state",
                agents_registry_store_name=os.getenv("DAPR_AGENTS_REGISTRY_STORE", "agentstatestore"),
                agents_registry_key="agents_registry",
                broadcast_topic_name=os.getenv("DAPR_BROADCAST_TOPIC", "beacon_channel")
            )
            .as_service(port=int(os.getenv("OFFICE_AUTOMATION_PORT", os.getenv("APP_PORT", "5102"))))
        )
        await agent.start()
    except Exception as e:
        logging.exception("Error starting OfficeAutomation agent: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
