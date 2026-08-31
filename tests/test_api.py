"""
Unit tests for the FastAPI endpoints.
"""

import pytest

from fastapi.testclient import TestClient

from api.queue_api import app
from sentinel_app import FraudTriageService


def test_health():
    """Health endpoint returns 200."""

    with TestClient(app) as client:

        response = client.get("/api/v1/health")

        assert response.status_code == 200

        body = response.json()

        assert body["status"] == "ok"


def test_policy_endpoint():
    """Policy endpoint lists rules."""

    with TestClient(app) as client:

        response = client.get("/api/v1/policies")

        assert response.status_code == 200

        body = response.json()

        assert "rules" in body

        assert len(body["rules"]) >= 1


def test_submit_investigation():
    """Submit investigation endpoint works."""

    with TestClient(app) as client:

        response = client.post(
            "/api/v1/investigations",
            json={"account_id": "A00985"},
        )

        # Should return 202 Accepted
        assert response.status_code in (200, 202)

        body = response.json()

        assert "account_id" in body


def test_submit_requires_account_id():
    """Submit without account_id returns 422."""

    with TestClient(app) as client:

        response = client.post(
            "/api/v1/investigations",
            json={},
        )

        assert response.status_code == 422


def test_root_endpoint():
    """Root endpoint exists."""

    with TestClient(app) as client:

        response = client.get("/")

        assert response.status_code == 200

        body = response.json()

        assert "message" in body
