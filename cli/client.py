"""
Thin HTTP client for the Sentinel CLI.

The CLI intentionally communicates with the API instead of
directly invoking the fraud service. This keeps the API and CLI
interfaces consistent.
"""

from __future__ import annotations

import os
from typing import Any

import requests


class SentinelAPIClient:
    """HTTP client for Sentinel API."""

    def __init__(
        self,
        base_url: str | None = None,
    ) -> None:

        self.base_url = (
            base_url
            or os.getenv(
                "SENTINEL_API_URL",
                "http://127.0.0.1:8000",
            )
        ).rstrip("/")

    def health(self) -> dict[str, Any]:
        """Check API health."""

        response = requests.get(
            f"{self.base_url}/api/v1/health",
            timeout=10,
        )

        response.raise_for_status()

        return response.json()

    def policies(self) -> dict[str, Any]:
        """Get policy rules."""

        response = requests.get(
            f"{self.base_url}/api/v1/policies",
            timeout=10,
        )

        response.raise_for_status()

        return response.json()

    def submit_investigation(
        self,
        account_id: str,
    ) -> dict[str, Any]:
        """Submit a fraud investigation."""

        response = requests.post(
            f"{self.base_url}/api/v1/investigations",
            json={"account_id": account_id},
            timeout=30,
        )

        response.raise_for_status()

        return response.json()

    def get_investigation(
        self,
        job_id: str,
    ) -> dict[str, Any]:
        """Get investigation status."""

        response = requests.get(
            f"{self.base_url}/api/v1/investigations/{job_id}",
            timeout=30,
        )

        response.raise_for_status()

        return response.json()

    def approve(
        self,
        job_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """Approve an investigation."""

        response = requests.post(
            f"{self.base_url}/api/v1/investigations/{job_id}/approval",
            json={
                "approved": True,
                "reason": reason,
            },
            timeout=60,
        )

        response.raise_for_status()

        return response.json()

    def reject(
        self,
        job_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """Reject an investigation."""

        response = requests.post(
            f"{self.base_url}/api/v1/investigations/{job_id}/approval",
            json={
                "approved": False,
                "reason": reason,
            },
            timeout=60,
        )

        response.raise_for_status()

        return response.json()
