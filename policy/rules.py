"""
Deterministic policy rules for Sentinel.

Each rule is a pure function that returns a PolicyResult or None.
Rules are evaluated in order; the first match wins.
"""

from __future__ import annotations

from .models import (
    PolicyContext,
    PolicyDecision,
    PolicyAction,
    PolicyResult,
)


def rule_investigation_always_allowed(
    context: PolicyContext,
) -> PolicyResult | None:
    """
    Investigations themselves are allowed.

    This rule prevents policy enforcement from accidentally
    blocking evidence gathering.
    """

    if context.action == PolicyAction.INVESTIGATE:

        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            action=context.action,
            reason=(
                "Investigation is an allowed "
                "non-destructive operation."
            ),
            rule_ids=["POL-INVESTIGATION-001"],
            requires_human_approval=False,
        )

    return None


def rule_customer_locked(
    context: PolicyContext,
) -> PolicyResult | None:
    """
    Customers with account restrictions are blocked.
    """

    if context.customer_locked:

        return PolicyResult(
            decision=PolicyDecision.BLOCK,
            action=context.action,
            reason=(
                "Customer is locked. "
                "The requested action is prohibited "
                "until the account restriction is resolved."
            ),
            rule_ids=["POL-ACCOUNT-001"],
            requires_human_approval=False,
        )

    return None


def rule_fraud_requires_confidence(
    context: PolicyContext,
) -> PolicyResult | None:
    """
    Account blocking requires fraud verdict and high confidence.
    """

    if context.action == PolicyAction.BLOCK_ACCOUNT:

        if context.verdict != "fraud":

            return PolicyResult(
                decision=PolicyDecision.BLOCK,
                action=context.action,
                reason=(
                    "Account blocking requires "
                    "a fraud disposition."
                ),
                rule_ids=["POL-FRAUD-001"],
                requires_human_approval=False,
            )

        if context.confidence not in {"high"}:

            return PolicyResult(
                decision=PolicyDecision.BLOCK,
                action=context.action,
                reason=(
                    "Account blocking requires "
                    "high-confidence fraud evidence."
                ),
                rule_ids=["POL-FRAUD-002"],
                requires_human_approval=False,
            )

    return None


def rule_irreversible_actions_require_approval(
    context: PolicyContext,
) -> PolicyResult | None:
    """
    Irreversible actions require human approval.
    """

    irreversible = {
        PolicyAction.BLOCK_ACCOUNT,
        PolicyAction.CLOSE_CASE,
    }

    if context.action in irreversible:

        if context.approval_requested:

            return PolicyResult(
                decision=PolicyDecision.REQUIRE_APPROVAL,
                action=context.action,
                reason=(
                    "This action is irreversible "
                    "and requires human approval."
                ),
                rule_ids=["POL-APPROVAL-001"],
                requires_human_approval=True,
            )

        return PolicyResult(
            decision=PolicyDecision.BLOCK,
            action=context.action,
            reason=(
                "This action cannot execute "
                "without an explicit approval gate."
            ),
            rule_ids=["POL-APPROVAL-002"],
            requires_human_approval=True,
        )

    return None


def rule_insufficient_evidence(
    context: PolicyContext,
) -> PolicyResult | None:
    """
    Insufficient evidence prevents consequential fraud actions.
    """

    if context.verdict == "insufficient_evidence":

        return PolicyResult(
            decision=PolicyDecision.BLOCK,
            action=context.action,
            reason=(
                "Insufficient evidence prevents "
                "a consequential fraud action."
            ),
            rule_ids=["POL-EVIDENCE-001"],
            requires_human_approval=False,
        )

    return None


POLICY_RULES = [
    rule_investigation_always_allowed,
    rule_customer_locked,
    rule_insufficient_evidence,
    rule_fraud_requires_confidence,
    rule_irreversible_actions_require_approval,
]
