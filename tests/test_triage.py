from unittest.mock import patch

import pytest

from sentinel_app import FraudTriageService, FraudSupervisor, PolicyLoader


def test_known_legitimate_case_is_classified_correctly():
    service = FraudTriageService()
    result = service.triage_account("A00985")
    assert result["verdict"] == "legitimate"
    assert result["confidence"] in {"high", "medium", "low"}
    assert "phone" in result["reason"].lower() or "kyc" in result["reason"].lower()


def test_queue_sweep_returns_job_and_results():
    service = FraudTriageService()
    job = service.start_queue_sweep()
    assert job["job_id"]
    data = service.get_job_status(job["job_id"])
    assert data["status"] in {"queued", "running", "completed", "failed"}


def test_policy_threshold_changes_behaviour_without_code_change():
    loader = PolicyLoader()
    service = FraudTriageService()
    analyst = service.behaviour_tool.__class__(service.behaviour_data, loader)

    with patch.object(loader, "load", return_value="high_value_amount: 999999\nrapid_country_count: 99\n"):
        finding = analyst.analyze("A00985")

    assert not any("exceeded" in item for item in finding["evidence"])


def test_supervisor_has_tools_but_no_database_attribute():
    service = FraudTriageService()
    assert isinstance(service.supervisor, FraudSupervisor)
    assert set(service.supervisor.tools) == {"behaviour", "context", "network", "disposition"}
    assert not hasattr(service.supervisor, "db")


def test_swapping_specialist_prompts_is_visible_failure():
    service = FraudTriageService()
    original = service.behaviour_tool.prompt
    service.behaviour_tool.prompt = service.context_tool.prompt
    try:
        with pytest.raises(RuntimeError, match="wrong domain"):
            service.behaviour_tool.analyze("A00985")
    finally:
        service.behaviour_tool.prompt = original
