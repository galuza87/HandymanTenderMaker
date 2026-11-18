"""Unit and integration tests for the Agent Testing Endpoints (/api/v1/tests/*).

Covers:
1. Authentication via X-Test-Api-Key / Bearer token and ENABLE_TEST_ENDPOINTS gate.
2. Target persona validation (simulated_user_id lookup in dbo.Clients).
3. Action-based outcome classification & gold-standard evaluation:
   - ask_additional_info
   - tool_use
   - request_hitl
   - generate_document
   - node/state transition checks (next_step, CategorizerDecision, is_finished)
4. Dynamic engine loading (v1, v2, invalid version -> 400) and dry_run isolation.
5. System capacity (503 Service Unavailable) and execution timeout (504 Gateway Timeout).
6. Batch job execution (POST /api/v1/tests/jobs, GET /api/v1/tests/jobs/{job_id})
   and job directory artifacts (job.log, summary.json, results.json, failed_requests.json).
"""

import asyncio
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import AgentState, CategorizerDecisionClass


TEST_API_KEY = "test-secret-api-key"
AUTH_HEADERS = {"X-Test-Api-Key": TEST_API_KEY}

MOCK_CLIENT = {
    "id": 1,
    "name": "Alice",
    "last_name": "Tester",
    "phone": "0501234567",
    "additional_phone": None,
    "email": "alice@example.com",
    "address": "123 Main St, Tel Aviv",
}


class FakeEngine:
    """Deterministic fake engine for testing endpoint behavior, state transitions, and timeouts."""

    def __init__(self, behavior: str = "ask_info", delay_seconds: float = 0.0):
        self.behavior = behavior
        self.delay_seconds = delay_seconds
        self.last_dry_run = None

    def process(self, state: AgentState, dry_run: bool = False) -> AgentState:
        """Simulate synchronous engine processing with configurable action outcomes."""
        self.last_dry_run = dry_run
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)

        new_messages = list(state.messages)

        if self.behavior == "ask_info":
            new_messages.append({
                "role": "assistant",
                "content": "Could you please provide more details about the issue?",
            })
            state.messages = new_messages
            state.next_step = "DataValidator"
            state.is_finished = False

        elif self.behavior == "tool_use":
            new_messages.append({
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_cat_1",
                        "name": "fetch_available_categories",
                        "args": {},
                    }
                ],
            })
            new_messages.append({
                "role": "tool",
                "content": "- ID: 2 | Plumbing: Pipe repair and installation",
                "tool_call_id": "call_cat_1",
                "name": "fetch_available_categories",
            })
            new_messages.append({
                "role": "assistant",
                "content": "Categorized request as Plumbing.",
            })
            state.messages = new_messages
            state.identified_categories = [{"category_id": 2, "name": "Plumbing"}]
            state.CategorizerDecision = CategorizerDecisionClass(decision="single")
            state.next_step = "IntakeCoordinator"
            state.is_finished = False

        elif self.behavior == "request_hitl":
            new_messages.append({
                "role": "assistant",
                "content": "**Plumbing**\n\n**Description:**\nFix kitchen sink leak\n\n**Address:**\n123 Main St\n\n---\nPlease confirm if this looks good.",
            })
            state.messages = new_messages
            state.next_step = "IntakeCoordinator"
            state.is_finished = False

        elif self.behavior == "generate_document":
            new_messages.append({
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_save_1",
                        "name": "confirm_and_save_document",
                        "args": {"document_markdown": "**Plumbing**\nFix leak"},
                    }
                ],
            })
            new_messages.append({
                "role": "tool",
                "content": "SAVED_PROJECT_9999_WITH_DOC:\n**Plumbing**\nFix leak",
                "tool_call_id": "call_save_1",
                "name": "confirm_and_save_document",
            })
            new_messages.append({
                "role": "assistant",
                "content": "Tenders have been finalized and saved!",
            })
            state.messages = new_messages
            state.project_id = 9999
            state.confirmed_job_description = "**Plumbing**\nFix leak"
            state.next_step = "TenderCreator"
            state.is_finished = True

        return state


@pytest.fixture(autouse=True)
def configure_test_env(monkeypatch):
    """Ensure testing endpoints and API key are configured deterministically for each test."""
    monkeypatch.setenv("ENABLE_TEST_ENDPOINTS", "true")
    monkeypatch.setenv("TEST_API_KEY", TEST_API_KEY)
    import backend.config as config_mod
    monkeypatch.setattr(config_mod, "ENABLE_TEST_ENDPOINTS", True, raising=False)
    monkeypatch.setattr(config_mod, "TEST_API_KEY", TEST_API_KEY, raising=False)


@pytest.fixture
def client():
    """Return a FastAPI TestClient."""
    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# 1. Authentication & Feature Gate Tests
# ---------------------------------------------------------------------------

def test_missing_api_key_returns_401(client):
    """Requests without X-Test-Api-Key or Bearer token must be rejected with 401."""
    payload = {
        "simulated_user_id": 1,
        "state": {"messages": [{"role": "user", "content": "Hello"}]},
    }
    response = client.post("/api/v1/tests/process-state", json=payload)
    assert response.status_code == 401


def test_invalid_api_key_returns_401(client):
    """Requests with an incorrect API key must be rejected with 401."""
    payload = {
        "simulated_user_id": 1,
        "state": {"messages": [{"role": "user", "content": "Hello"}]},
    }
    response = client.post(
        "/api/v1/tests/process-state",
        json=payload,
        headers={"X-Test-Api-Key": "wrong-key"},
    )
    assert response.status_code == 401


def test_bearer_token_authentication_accepted(client):
    """Requests using Authorization: Bearer <TEST_API_KEY> should be accepted."""
    payload = {
        "simulated_user_id": 1,
        "state": {"messages": [{"role": "user", "content": "Hello"}]},
    }
    with patch("backend.v1.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.v1.routes.testing.load_engine", return_value=FakeEngine("ask_info")):
        response = client.post(
            "/api/v1/tests/process-state",
            json=payload,
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )
    assert response.status_code == 200


def test_disabled_test_endpoints_returns_403(client, monkeypatch):
    """When ENABLE_TEST_ENDPOINTS is false, testing endpoints should reject requests with 403."""
    import backend.config as config_mod
    import backend.v1.routes.testing as testing_mod

    monkeypatch.setenv("ENABLE_TEST_ENDPOINTS", "false")
    monkeypatch.setattr(config_mod, "ENABLE_TEST_ENDPOINTS", False, raising=False)
    monkeypatch.setattr(testing_mod, "ENABLE_TEST_ENDPOINTS", False, raising=False)

    payload = {
        "simulated_user_id": 1,
        "state": {"messages": [{"role": "user", "content": "Hello"}]},
    }
    response = client.post(
        "/api/v1/tests/process-state",
        json=payload,
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# 2. Target User Simulation (simulated_user_id in dbo.Clients)
# ---------------------------------------------------------------------------

def test_nonexistent_simulated_user_returns_404(client):
    """If simulated_user_id does not exist in dbo.Clients, endpoint must return 404."""
    payload = {
        "simulated_user_id": 999999,
        "state": {"messages": [{"role": "user", "content": "Hello"}]},
    }
    with patch("backend.v1.routes.testing.get_client_by_id", return_value=None):
        response = client.post(
            "/api/v1/tests/process-state",
            json=payload,
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 404
    assert "999999" in response.json()["detail"]


def test_simulated_user_populates_client_info(client):
    """Verified simulated_user_id should populate state.user_id and state.client_info."""
    payload = {
        "test_id": "verify_persona",
        "simulated_user_id": 1,
        "state": {"messages": [{"role": "user", "content": "Hello"}]},
    }
    with patch("backend.v1.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.v1.routes.testing.load_engine", return_value=FakeEngine("ask_info")):
        response = client.post(
            "/api/v1/tests/process-state",
            json=payload,
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["state"]["user_id"] == 1
    assert data["state"]["client_info"]["name"] == "Alice Tester"
    assert data["state"]["client_info"]["phone"] == "0501234567"
    assert data["state"]["client_info"]["address"] == "123 Main St, Tel Aviv"


# ---------------------------------------------------------------------------
# 3. Action & Outcome Evaluation Tests (No Text Testing - Action/Tool/Node Only)
# ---------------------------------------------------------------------------

def test_evaluate_ask_additional_info_outcome(client):
    """Verify ask_additional_info detection and next_step node evaluation."""
    payload = {
        "test_id": "test_ask_info",
        "simulated_user_id": 1,
        "state": {"messages": [{"role": "user", "content": "Hi"}]},
        "expected_outcome": {
            "outcome_type": "ask_additional_info",
            "expected_state_fields": {"next_step": "DataValidator", "is_finished": False},
        },
    }
    with patch("backend.v1.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.v1.routes.testing.load_engine", return_value=FakeEngine("ask_info")):
        response = client.post(
            "/api/v1/tests/process-state",
            json=payload,
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["turn_summary"]["detected_outcome_type"] == "ask_additional_info"
    assert data["evaluation"]["passed"] is True
    assert data["evaluation"]["mismatches"] == []


def test_evaluate_tool_use_and_node_transition(client):
    """Verify tool_use outcome checks tool call name/args and next_step node progression."""
    payload = {
        "test_id": "test_tool_use",
        "simulated_user_id": 1,
        "state": {
            "messages": [{"role": "user", "content": "I need a plumber for a leaking pipe"}],
            "next_step": "ContractorCategorizer",
        },
        "expected_outcome": {
            "outcome_type": "tool_use",
            "expected_tools": [{"name": "fetch_available_categories"}],
            "expected_state_fields": {
                "next_step": "IntakeCoordinator",
                "CategorizerDecision": {"decision": "single"},
            },
        },
    }
    with patch("backend.v1.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.v1.routes.testing.load_engine", return_value=FakeEngine("tool_use")):
        response = client.post(
            "/api/v1/tests/process-state",
            json=payload,
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["turn_summary"]["detected_outcome_type"] == "tool_use"
    assert any(t["name"] == "fetch_available_categories" for t in data["turn_summary"]["tool_calls_made"])
    assert data["evaluation"]["passed"] is True


def test_evaluate_request_hitl_outcome(client):
    """Verify request_hitl outcome when agent presents draft for confirmation."""
    payload = {
        "test_id": "test_hitl",
        "simulated_user_id": 1,
        "state": {
            "messages": [{"role": "user", "content": "No other questions, it is under the kitchen sink."}],
            "next_step": "IntakeCoordinator",
        },
        "expected_outcome": {
            "outcome_type": "request_hitl",
            "expected_state_fields": {"next_step": "IntakeCoordinator", "is_finished": False},
        },
    }
    with patch("backend.v1.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.v1.routes.testing.load_engine", return_value=FakeEngine("request_hitl")):
        response = client.post(
            "/api/v1/tests/process-state",
            json=payload,
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["turn_summary"]["detected_outcome_type"] == "request_hitl"
    assert data["evaluation"]["passed"] is True


def test_evaluate_generate_document_outcome(client):
    """Verify generate_document outcome when project/tender is confirmed and saved."""
    payload = {
        "test_id": "test_gen_doc",
        "simulated_user_id": 1,
        "state": {
            "messages": [{"role": "user", "content": "Yes, confirmed!"}],
            "next_step": "IntakeCoordinator",
        },
        "expected_outcome": {
            "outcome_type": "generate_document",
            "expected_tools": [{"name": "confirm_and_save_document"}],
            "expected_state_fields": {"is_finished": True, "next_step": "TenderCreator"},
        },
    }
    with patch("backend.v1.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.v1.routes.testing.load_engine", return_value=FakeEngine("generate_document")):
        response = client.post(
            "/api/v1/tests/process-state",
            json=payload,
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["turn_summary"]["detected_outcome_type"] == "generate_document"
    assert data["evaluation"]["passed"] is True


def test_evaluation_detects_action_and_node_mismatches(client):
    """When the agent takes a different action or node transition than expected, evaluation fails with reasons."""
    payload = {
        "test_id": "test_mismatch",
        "simulated_user_id": 1,
        "state": {"messages": [{"role": "user", "content": "Hi"}]},
        "expected_outcome": {
            "outcome_type": "generate_document",
            "expected_tools": [{"name": "save_project_and_tenders"}],
            "expected_state_fields": {"next_step": "TenderCreator"},
        },
    }
    with patch("backend.v1.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.v1.routes.testing.load_engine", return_value=FakeEngine("ask_info")):
        response = client.post(
            "/api/v1/tests/process-state",
            json=payload,
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["evaluation"]["passed"] is False
    assert data["evaluation"]["expected_outcome_type"] == "generate_document"
    assert data["evaluation"]["actual_outcome_type"] == "ask_additional_info"
    assert len(data["evaluation"]["mismatches"]) >= 2


# ---------------------------------------------------------------------------
# 4. Dynamic Engine Discovery & Dry-Run Isolation
# ---------------------------------------------------------------------------

def test_invalid_algorithm_version_returns_400(client):
    """Requesting an unknown algorithm_version should return 400 Bad Request."""
    payload = {
        "simulated_user_id": 1,
        "state": {"messages": [{"role": "user", "content": "Hello"}]},
        "options": {"algorithm_version": "v99"},
    }
    with patch("backend.v1.routes.testing.get_client_by_id", return_value=MOCK_CLIENT):
        response = client.post(
            "/api/v1/tests/process-state",
            json=payload,
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 400
    assert "v99" in response.json()["detail"]


def test_dry_run_default_is_true(client):
    """Verify dry_run defaults to True and is passed down to engine.process."""
    fake_engine = FakeEngine("ask_info")
    payload = {
        "simulated_user_id": 1,
        "state": {"messages": [{"role": "user", "content": "Hello"}]},
    }
    with patch("backend.v1.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.v1.routes.testing.load_engine", return_value=fake_engine):
        response = client.post(
            "/api/v1/tests/process-state",
            json=payload,
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    assert fake_engine.last_dry_run is True


# ---------------------------------------------------------------------------
# 5. Concurrency Limit (503) & Timeout (504) Tests
# ---------------------------------------------------------------------------

def test_capacity_limit_returns_503(client, monkeypatch):
    """When active requests reach MAX_ACTIVE_REQUESTS, endpoint immediately returns 503."""
    import backend.v1.routes.testing as testing_mod

    monkeypatch.setattr(testing_mod, "MAX_ACTIVE_REQUESTS", 1)
    monkeypatch.setattr(testing_mod, "_active_requests", 1)

    payload = {
        "simulated_user_id": 1,
        "state": {"messages": [{"role": "user", "content": "Hello"}]},
    }
    with patch("backend.v1.routes.testing.get_client_by_id", return_value=MOCK_CLIENT):
        response = client.post(
            "/api/v1/tests/process-state",
            json=payload,
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 503
    assert "capacity" in response.json()["detail"].lower()


def test_execution_timeout_returns_504(client, monkeypatch):
    """When engine execution exceeds config.REQUEST_TIMEOUT_SECONDS, endpoint returns 504."""
    import backend.config as config_mod

    monkeypatch.setattr(config_mod, "REQUEST_TIMEOUT_SECONDS", 0.05)
    assert not hasattr(config_mod, "TEST_REQUEST_TIMEOUT_SECONDS")

    slow_engine = FakeEngine("ask_info", delay_seconds=0.3)
    payload = {
        "simulated_user_id": 1,
        "state": {"messages": [{"role": "user", "content": "Hello"}]},
    }
    with patch("backend.v1.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.v1.routes.testing.load_engine", return_value=slow_engine):
        response = client.post(
            "/api/v1/tests/process-state",
            json=payload,
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 504


# ---------------------------------------------------------------------------
# 6. Batch Job Execution & Log Directory Creation
# ---------------------------------------------------------------------------

def test_batch_job_execution_and_artifacts(client, tmp_path, monkeypatch):
    """POST /api/v1/tests/jobs runs batch requests, writes job directory files, and GET retrieves summary."""
    import backend.v1.routes.testing as testing_mod

    monkeypatch.setattr(testing_mod, "TEST_JOBS_DIR", tmp_path)

    batch_payload = {
        "job_name": "unit_test_batch",
        "concurrency": 2,
        "fail_fast": False,
        "requests": [
            {
                "test_id": "case_pass",
                "simulated_user_id": 1,
                "state": {"messages": [{"role": "user", "content": "Hello"}]},
                "expected_outcome": {"outcome_type": "ask_additional_info"},
            },
            {
                "test_id": "case_fail",
                "simulated_user_id": 1,
                "state": {"messages": [{"role": "user", "content": "Hello"}]},
                "expected_outcome": {"outcome_type": "generate_document"},
            },
        ],
    }

    with patch("backend.v1.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.v1.routes.testing.load_engine", return_value=FakeEngine("ask_info")):
        response = client.post(
            "/api/v1/tests/jobs",
            json=batch_payload,
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 200
    summary = response.json()
    job_id = summary["job_id"]
    assert summary["total_requests"] == 2
    assert summary["passed"] == 1
    assert summary["failed"] == 1
    assert summary["status"] == "FAILED"

    # Verify artifacts in job directory
    job_dir = tmp_path / f"job_{job_id}"
    assert job_dir.exists()
    assert (job_dir / "job.log").exists()
    assert (job_dir / "summary.json").exists()
    assert (job_dir / "results.json").exists()
    assert (job_dir / "failed_requests.json").exists()

    failed_list = json.loads((job_dir / "failed_requests.json").read_text(encoding="utf-8"))
    assert len(failed_list) == 1
    assert failed_list[0]["test_id"] == "case_fail"

    # Verify GET /api/v1/tests/jobs/{job_id}
    get_resp = client.get(f"/api/v1/tests/jobs/{job_id}", headers=AUTH_HEADERS)
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["job_id"] == job_id
    assert get_data["passed"] == 1
    assert get_data["failed"] == 1
    assert len(get_data["failed_requests"]) == 1


# ---------------------------------------------------------------------------
# 7. CLI Runner Script Tests (scripts/run_test.py)
# ---------------------------------------------------------------------------

def test_cli_runner_list_and_resolve():
    """Verify scripts/run_test.py discovers JSON test cases in backend/tests/agent_cases/."""
    from scripts.run_test import list_available_tests, resolve_test_path

    available = list_available_tests()
    assert "ask_additional_info" in available
    assert "tool_use_categories" in available
    assert "request_hitl_confirmation" in available
    assert "generate_document_confirmed" in available
    assert "batch_smoke_suite" in available

    resolved = resolve_test_path("ask_additional_info")
    assert resolved.name == "ask_additional_info.json"
    assert resolved.exists()

