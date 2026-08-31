"""
API request and response models for Sentinel.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class InvestigationSubmitRequest(BaseModel):
    """Request to submit a fraud investigation."""

    account_id: str = Field(
        min_length=1,
        max_length=128,
    )


class InvestigationSubmitResponse(BaseModel):
    """Response when investigation is submitted."""

    job_id: str

    account_id: str

    status: str

    graph_thread_id: str


class ApprovalRequest(BaseModel):
    """Request to approve or reject an investigation action."""

    approved: bool

    reason: str | None = None


class InvestigationStatusResponse(BaseModel):
    """Response with investigation status and results."""

    job_id: str

    account_id: str

    status: str

    graph_thread_id: str

    result: dict[str, Any] | None = None

    error: str | None = None
