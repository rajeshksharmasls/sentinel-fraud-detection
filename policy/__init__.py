"""
Sentinel deterministic policy engine.

Policies are evaluated in order. The first applicable policy result wins.
The system is fail-closed: if no policy explicitly allows an action, it is blocked.
"""

from .engine import (
    PolicyEngine,
    create_policy_engine,
)

from .models import (
    PolicyAction,
    PolicyContext,
    PolicyDecision,
    PolicyResult,
)

__all__ = [
    "PolicyAction",
    "PolicyContext",
    "PolicyDecision",
    "PolicyEngine",
    "PolicyResult",
    "create_policy_engine",
]
