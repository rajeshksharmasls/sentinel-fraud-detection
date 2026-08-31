"""
Deterministic policy engine for Sentinel.

Evaluates rules in order. First match wins.
Fails closed: unknown actions are blocked.
"""

from __future__ import annotations

from collections.abc import Callable

from .models import (
    PolicyContext,
    PolicyResult,
    PolicyDecision,
    PolicyAction,
)


PolicyRule = Callable[
    [PolicyContext],
    PolicyResult | None,
]


class PolicyEngine:
    """
    Deterministic Sentinel policy engine.

    Policies are evaluated in order.
    The first applicable policy result wins.
    """

    def __init__(
        self,
        rules: list[PolicyRule],
    ):
        self.rules = rules

    def evaluate(
        self,
        context: PolicyContext,
    ) -> PolicyResult:

        for rule in self.rules:

            result = rule(context)

            if result is not None:
                return result

        # Fail closed.
        return PolicyResult(
            decision=PolicyDecision.BLOCK,
            action=context.action,
            reason=(
                "No policy explicitly allowed "
                "the requested operation."
            ),
            rule_ids=["POL-DEFAULT-001"],
            requires_human_approval=False,
        )


def create_policy_engine() -> PolicyEngine:
    """Create a new policy engine with default rules."""
    from .rules import POLICY_RULES

    return PolicyEngine(rules=POLICY_RULES)
