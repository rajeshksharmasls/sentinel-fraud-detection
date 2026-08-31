"""
Unit tests for the CLI client and commands.
"""

from unittest.mock import Mock, patch

import pytest

from cli.client import SentinelAPIClient


@patch("cli.client.requests.get")
def test_health(mock_get):
    """Health command calls the API."""

    mock_response = Mock()

    mock_response.json.return_value = {
        "status": "ok",
        "queue_size": 0,
    }

    mock_response.raise_for_status.return_value = None

    mock_get.return_value = mock_response

    client = SentinelAPIClient(base_url="http://test")

    result = client.health()

    assert result["status"] == "ok"

    mock_get.assert_called_once()


@patch("cli.client.requests.post")
def test_submit_investigation(mock_post):
    """Submit investigation command works."""

    mock_response = Mock()

    mock_response.json.return_value = {
        "job_id": "abc123",
        "account_id": "A00985",
        "status": "queued",
        "graph_thread_id": "investigation-abc123",
    }

    mock_response.raise_for_status.return_value = None

    mock_post.return_value = mock_response

    client = SentinelAPIClient(base_url="http://test")

    result = client.submit_investigation("A00985")

    assert result["account_id"] == "A00985"

    assert result["status"] == "queued"


@patch("cli.client.requests.post")
def test_approve(mock_post):
    """Approve command calls the API."""

    mock_response = Mock()

    mock_response.json.return_value = {
        "job_id": "abc123",
        "approved": True,
        "status": "completed",
    }

    mock_response.raise_for_status.return_value = None

    mock_post.return_value = mock_response

    client = SentinelAPIClient(base_url="http://test")

    result = client.approve("abc123", "Reviewed evidence")

    assert result["approved"] is True


@patch("cli.client.requests.post")
def test_reject(mock_post):
    """Reject command calls the API."""

    mock_response = Mock()

    mock_response.json.return_value = {
        "job_id": "abc123",
        "approved": False,
        "status": "completed",
    }

    mock_response.raise_for_status.return_value = None

    mock_post.return_value = mock_response

    client = SentinelAPIClient(base_url="http://test")

    result = client.reject("abc123", "Need more evidence")

    assert result["approved"] is False
