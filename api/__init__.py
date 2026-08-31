"""
Sentinel FastAPI application and REST API.

Exposes investigation submission, status polling, approval, and policy endpoints.
"""

from .routes import create_router
from .models import (
    InvestigationSubmitRequest,
    InvestigationSubmitResponse,
    ApprovalRequest,
    InvestigationStatusResponse,
)

__all__ = [
    "create_router",
    "InvestigationSubmitRequest",
    "InvestigationSubmitResponse",
    "ApprovalRequest",
    "InvestigationStatusResponse",
]
