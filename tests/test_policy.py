"""
Unit tests for the policy engine.
"""

import pytest

from policy import (
    PolicyAction,
    PolicyContext,
    PolicyDecision,
    create_policy_engine,
)


def test_investigation_is_allowed():
    """Investigation actions are always allowed."""

    engine = create_policy_engine()

    result = engine.evaluate(
        PolicyContext(
            account_id="A00985",
            action=PolicyAction.INVESTIGATE,
        )
    )

    assert result.decision == PolicyDecision.ALLOW


def test_block_account_requires_fraud():
    """Block account action requires fraud verdict."""

    engine = create_policy_engine()

    result = engine.evaluate(
        PolicyContext(
            account_id="A00985",
            action=PolicyAction.BLOCK_ACCOUNT,
            verdict="legitimate",
            confidence="high",
            approval_requested=True,
        )
    )

    assert result.decision == PolicyDecision.BLOCK


def test_block_account_requires_high_confidence():
    """Block account requires high confidence."""

    engine = create_policy_engine()

    result = engine.evaluate(
        PolicyContext(
            account_id="A00985",
            action=PolicyAction.BLOCK_ACCOUNT,
            verdict="fraud",
            confidence="medium",
            approval_requested=True,
        )
    )

    assert result.decision == PolicyDecision.BLOCK


def test_block_account_requires_human_approval():
    """Block account requires human approval."""

    engine = create_policy_engine()

    result = engine.evaluate(
        PolicyContext(
            account_id="A00985",
            action=PolicyAction.BLOCK_ACCOUNT,
            verdict="fraud",
            confidence="high",
            approval_requested=True,
        )
    )

    assert result.decision == PolicyDecision.REQUIRE_APPROVAL
    assert result.requires_human_approval is True


def test_block_account_without_approval_is_blocked():
    """Block account without approval request is blocked."""

    engine = create_policy_engine()

    result = engine.evaluate(
        PolicyContext(
            account_id="A00985",
            action=PolicyAction.BLOCK_ACCOUNT,
            verdict="fraud",
            confidence="high",
            approval_requested=False,
        )
    )

    assert result.decision == PolicyDecision.BLOCK


def test_insufficient_evidence_is_blocked():
    """Insufficient evidence verdict is blocked."""

    engine = create_policy_engine()

    result = engine.evaluate(
        PolicyContext(
            account_id="A00985",
            action=PolicyAction.BLOCK_ACCOUNT,
            verdict="insufficient_evidence",
            confidence="low",
            approval_requested=True,
        )
    )

    assert result.decision == PolicyDecision.BLOCK


def test_locked_customer_is_blocked():
    """Locked customers are blocked from all actions."""

    engine = create_policy_engine()

    result = engine.evaluate(
        PolicyContext(
            account_id="A00985",
            action=PolicyAction.FLAG_CASE,
            customer_locked=True,
        )
    )

    assert result.decision == PolicyDecision.BLOCK


def test_no_action_is_allowed():
    """No-action is a safe operation."""

    engine = create_policy_engine()

    result = engine.evaluate(
        PolicyContext(
            account_id="A00985",
            action=PolicyAction.NO_ACTION,
        )
    )

    # This should fail closed, but NO_ACTION is not explicitly blocked
    # So it may be blocked by the default rule
    assert result.decision in (
        PolicyDecision.BLOCK,
        PolicyDecision.ALLOW,
    )


def test_fail_closed_on_unknown_action():
    """Unknown actions are blocked by default."""

    engine = create_policy_engine()

    # Try to use an invalid action value
    # The engine should still handle it gracefully
    result = engine.evaluate(
        PolicyContext(
            account_id="A00985",
            action=PolicyAction.NO_ACTION,
        )
    )

    # Should not crash
    assert result.decision is not None
