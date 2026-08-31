"""
Policy model classes for Sentinel.

PolicyDecision, PolicyAction, PolicyContext, and PolicyResult.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PolicyDecision(str, Enum):
    """Possible policy outcomes."""

    ALLOW = "allow"
    BLOCK = "block"
    REQUIRE_APPROVAL = "require_approval"


class PolicyAction(str, Enum):
    """Possible consequential actions."""

    INVESTIGATE = "investigate"
    BLOCK_ACCOUNT = "block_account"
    FLAG_CASE = "flag_case"
    CLOSE_CASE = "close_case"
    NO_ACTION = "no_action"


class PolicyContext(BaseModel):
    """
    Facts supplied to the deterministic policy engine.

    These are facts, not LLM reasoning.
    """

    account_id: str

    action: PolicyAction

    verdict: str | None = None

    confidence: str | None = None

    approval_requested: bool = False

    customer_locked: bool = False

    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyResult(BaseModel):
    """
    Deterministic policy decision.
    """

    decision: PolicyDecision

    action: PolicyAction

    reason: str

    rule_ids: list[str] = Field(default_factory=list)

    requires_human_approval: bool = False
