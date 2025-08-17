from __future__ import annotations

from .http_client import HttpClient
from typing import Optional, Dict, Any
import logging
import os

logger = logging.getLogger("task_webhook")


def create_task(title: str, due: Optional[str] = None, reminder: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a task by invoking an external webhook (FR008).

    Uses environment variable CREATE_TASK_WEBHOOK_URL and POSTs exactly:
      { "title": str, "due"?: str, "reminder"?: str }

    Returns the parsed JSON response if available; otherwise returns a minimal ack dict.
    Raises requests-related exceptions for non-2xx responses.
    """
    url = os.getenv("CREATE_TASK_WEBHOOK_URL")
    if not url:
        raise ValueError("CREATE_TASK_WEBHOOK_URL is not set")

    payload: Dict[str, Any] = {"title": title}
    if due:
        payload["due"] = due
    if reminder:
        payload["reminder"] = reminder

    client = HttpClient()
    resp = client.post(url, json=payload, headers={"Content-Type": "application/json"})
    resp.raise_for_status()

    try:
        return resp.json()
    except Exception:
        return {"status": "ok", "status_code": resp.status_code}
