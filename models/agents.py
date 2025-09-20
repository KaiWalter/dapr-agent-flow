from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Optional


class SendEmailArgs(BaseModel):
    """Schema for the send_email tool.

    - subject: Subject of the email - name of the transcription file without file extensions
    - body: The complete transcription text or a summary of the user's intent
    """

    subject: str = Field(
        description=
        "Subject of the email - name of the transcription file without file extensions"
    )
    body: str = Field(
        description=
        "The complete transcription text or a summary of the user's intent"
    )


class CreateTaskArgs(BaseModel):
    """Schema for the create_task tool."""

    title: str = Field(
        description="Title of the task - a summarization of the user's intent"
    )
    due_date: Optional[str] = Field(
        default=None,
        description=
        "Due date as ISO 8601 datetime string (e.g., 2025-08-16T14:30:00Z or 2025-08-16T14:30:00+00:00)",
    )
    reminder: Optional[str] = Field(
        default=None,
        description=
        "Reminder ISO 8601 datetime string (e.g., 2025-08-16T14:30:00Z or 2025-08-16T14:30:00+00:00)",
    )
    notes: Optional[str] = Field(
        default=None,
        description=
        "Notes on the task - the complete transcription text or a summary of the user's intent",
    )

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
                "must be an ISO 8601 datetime string, e.g., 2025-08-16T14:30:00Z"
            )
        return v


class RetrieveTranscriptionArgs(BaseModel):
    """Schema for retrieving transcription content.

    Provide 'transcription_path' to read JSON from disk.
    """

    transcription_path: str = Field(
        description=
        "Path to the voice transcription JSON file on disk (e.g., /.work/transcriptions/meeting1.json)"
    )


__all__ = [
    "SendEmailArgs",
    "CreateTaskArgs",
    "RetrieveTranscriptionArgs",
]
