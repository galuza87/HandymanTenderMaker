"""Unit and integration tests for the version-agnostic Agent Testing Endpoints (/api/{version}/tests/*).

Covers:
1. Dual-mode header authentication & client identification:
   - Test mode: `X-Test-Api-Key` present & valid + `jwt` (or `Authorization: Bearer`) header set to raw `Clients.id` (e.g. "1").
   - Real mode: `X-Test-Api-Key` omitted + `jwt` (or `Authorization: Bearer`) header set to a signed JWT token containing `client_id` / `sub`.
   - Invalid `X-Test-Api-Key`, missing JWT header, or raw ID without `X-Test-Api-Key` -> 401.
2. URL path parameter {version} selection (/api/v1/tests/*, /api/v2/tests/*, invalid version -> 400).
3. Client lookup in dbo.Clients from the header-resolved client ID (404 if not found).
4. Pure conversation-only request body (`messages` + `expected_step`, no `client_id` in body).
5. Version-agnostic step detection & evaluation (`step`, `expected_step`, `is_step_correct`, `reply`).
6. System capacity (503 Service Unavailable) and execution timeout (504 Gateway Timeout).
7. Batch job execution (POST /api/{version}/tests/jobs, GET /api/{version}/tests/jobs/{job_id}).
"""

import json
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import AgentState, CategorizerDecisionClass
from backend.services.jwt_auth import create_jwt_token


TEST_API_KEY = "test-secret-api-key"
TEST_JWT_SECRET = "test-jwt-secret-key"
AUTH_HEADERS = {
    "X-Test-Api-Key": TEST_API_KEY,
    "Authorization": "Bearer 1",
}

MOCK_CLIENT = {
    "id": 1,
    "name": "Andrew",
    "last_name": "Galuza",
    "phone": "0506687306",
    "additional_phone": None,
    "email": "galuza87@gmail.com",
    "address": "123 Main St, Tel Aviv",
}


class FakeEngine:
    """Deterministic fake engine for testing endpoint behavior, steps, and timeouts."""

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
            state.is_finished = False

        elif self.behavior == "request_hitl":
            new_messages.append({
                "role": "assistant",
                "content": (
                    "**Plumbing**\n\n**Description:**\nFix kitchen sink leak\n\n"
                    "**Address:**\n123 Main St\n\n---\nPlease confirm if this looks good."
                ),
            })
            state.messages = new_messages
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
            state.is_finished = True

        return state


@pytest.fixture(autouse=True)
def configure_test_env(monkeypatch):
    """Ensure testing endpoints, API key, and JWT secret are configured deterministically."""
    monkeypatch.setenv("ENABLE_TEST_ENDPOINTS", "true")
    monkeypatch.setenv("TEST_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("JWT_SECRET_KEY", TEST_JWT_SECRET)
    import backend.config as config_mod
    monkeypatch.setattr(config_mod, "ENABLE_TEST_ENDPOINTS", True, raising=False)
    monkeypatch.setattr(config_mod, "TEST_API_KEY", TEST_API_KEY, raising=False)
    monkeypatch.setattr(config_mod, "JWT_SECRET_KEY", TEST_JWT_SECRET, raising=False)


@pytest.fixture
def client():
    """Return a FastAPI TestClient."""
    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# 1. Dual-Mode Header Authentication & Client Identification Tests
# ---------------------------------------------------------------------------

def test_missing_headers_returns_401(client):
    """Requests without X-Test-Api-Key and without JWT must be rejected with 401."""
    payload = {"messages": [{"role": "user", "content": "hello"}]}
    response = client.post("/api/v1/tests/process-state", json=payload)
    assert response.status_code == 401


def test_invalid_test_api_key_returns_401(client):
    """If X-Test-Api-Key is provided with an incorrect value, request must be rejected with 401."""
    payload = {"messages": [{"role": "user", "content": "hello"}]}
    response = client.post(
        "/api/v1/tests/process-state",
        json=payload,
        headers={"X-Test-Api-Key": "wrong-key", "Authorization": "Bearer 1"},
    )
    assert response.status_code == 401


def test_valid_test_api_key_with_missing_authorization_header_returns_401(client):
    """When X-Test-Api-Key is valid, Authorization: Bearer <client_id> is still required."""
    payload = {"messages": [{"role": "user", "content": "hello"}]}
    response = client.post(
        "/api/v1/tests/process-state",
        json=payload,
        headers={"X-Test-Api-Key": TEST_API_KEY},
    )
    assert response.status_code == 401


def test_custom_jwt_header_is_rejected_401(client):
    """Only Authorization: Bearer <value> is accepted; custom 'jwt' header must return 401."""
    payload = {"messages": [{"role": "user", "content": "hello"}]}
    response = client.post(
        "/api/v1/tests/process-state",
        json=payload,
        headers={"X-Test-Api-Key": TEST_API_KEY, "jwt": "1"},
    )
    assert response.status_code == 401


def test_valid_test_api_key_identifies_client_by_authorization_bearer_client_id(client):
    """When X-Test-Api-Key is valid, Authorization: Bearer <client_id> identifies Clients.id."""
    payload = {"messages": [{"role": "user", "content": "hello"}]}
    with patch("backend.routes.testing.get_client_by_id", return_value=MOCK_CLIENT) as mock_get_client, \
         patch("backend.routes.testing.load_engine", return_value=FakeEngine("ask_info")):
        response = client.post(
            "/api/v1/tests/process-state",
            json=payload,
            headers={"X-Test-Api-Key": TEST_API_KEY, "Authorization": "Bearer 1"},
        )
    assert response.status_code == 200
    mock_get_client.assert_called_once_with(1)
    assert response.json()["client_id"] == 1


def test_without_test_api_key_valid_signed_jwt_identifies_client(client):
    """When X-Test-Api-Key is absent, Authorization: Bearer <signed_jwt> identifies the client."""
    signed_token = create_jwt_token(client_id=1, secret_key=TEST_JWT_SECRET)
    payload = {"messages": [{"role": "user", "content": "hello"}]}
    with patch("backend.routes.testing.get_client_by_id", return_value=MOCK_CLIENT) as mock_get_client, \
         patch("backend.routes.testing.load_engine", return_value=FakeEngine("ask_info")):
        response = client.post(
            "/api/v1/tests/process-state",
            json=payload,
            headers={"Authorization": f"Bearer {signed_token}"},
        )
    assert response.status_code == 200
    mock_get_client.assert_called_once_with(1)
    assert response.json()["client_id"] == 1


def test_login_issues_jwt_token_usable_in_authorization_header(client):
    """POST /api/login returns a signed JWT token that identifies the client in Authorization: Bearer."""
    with patch("backend.bootstrap.get_client_by_phone", return_value=MOCK_CLIENT):
        login_resp = client.post("/api/login", json={"phone": "0506687306"})

    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert "token" in login_data and login_data["token"]

    token = login_data["token"]
    payload = {"messages": [{"role": "user", "content": "hello"}]}
    with patch("backend.routes.testing.get_client_by_id", return_value=MOCK_CLIENT) as mock_get_client, \
         patch("backend.routes.testing.load_engine", return_value=FakeEngine("ask_info")):
        test_resp = client.post(
            "/api/v1/tests/process-state",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
    assert test_resp.status_code == 200
    mock_get_client.assert_called_once_with(1)
    assert test_resp.json()["client_id"] == 1


def test_without_test_api_key_raw_client_id_is_rejected_401(client):
    """When X-Test-Api-Key is absent, passing raw client ID 'Bearer 1' instead of a signed JWT returns 401."""
    payload = {"messages": [{"role": "user", "content": "hello"}]}
    response = client.post(
        "/api/v1/tests/process-state",
        json=payload,
        headers={"Authorization": "Bearer 1"},
    )
    assert response.status_code == 401


def test_disabled_test_endpoints_returns_403(client, monkeypatch):
    """When ENABLE_TEST_ENDPOINTS is false, testing endpoints should reject requests with 403."""
    import backend.config as config_mod
    import backend.routes.testing as testing_mod

    monkeypatch.setenv("ENABLE_TEST_ENDPOINTS", "false")
    monkeypatch.setattr(config_mod, "ENABLE_TEST_ENDPOINTS", False, raising=False)
    monkeypatch.setattr(testing_mod, "ENABLE_TEST_ENDPOINTS", False, raising=False)

    payload = {"messages": [{"role": "user", "content": "hello"}]}
    response = client.post(
        "/api/v1/tests/process-state",
        json=payload,
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# 2. Client Lookup from dbo.Clients via Header-Resolved Client ID
# ---------------------------------------------------------------------------

def test_nonexistent_header_client_id_returns_404(client):
    """If the header client_id does not exist in dbo.Clients, endpoint must return 404."""
    payload = {"messages": [{"role": "user", "content": "hello"}]}
    with patch("backend.routes.testing.get_client_by_id", return_value=None):
        response = client.post(
            "/api/v1/tests/process-state",
            json=payload,
            headers={"X-Test-Api-Key": TEST_API_KEY, "Authorization": "Bearer 999999"},
        )
    assert response.status_code == 404
    assert "999999" in response.json()["detail"]


def test_header_client_id_populates_client_info_from_db(client):
    """Verified client_id from header should populate state.user_id and state.client_info."""
    payload = {
        "test_id": "verify_client_db",
        "messages": [{"role": "user", "content": "hello"}],
    }
    with patch("backend.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.routes.testing.load_engine", return_value=FakeEngine("ask_info")):
        response = client.post(
            "/api/v1/tests/process-state",
            json=payload,
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["client_id"] == 1
    assert data["state"]["user_id"] == 1
    assert data["state"]["client_info"]["name"] == "Andrew Galuza"
    assert data["state"]["client_info"]["phone"] == "0506687306"
    assert data["state"]["client_info"]["address"] == "123 Main St, Tel Aviv"


# ---------------------------------------------------------------------------
# 3. Version-Agnostic Conversation-Only Input & Step Evaluation Tests
# ---------------------------------------------------------------------------

def test_flat_conversation_ask_additional_info_step(client):
    """Sending only messages + expected_step in body evaluates ask_additional_info."""
    payload = {
        "messages": [{"role": "user", "content": "hello"}],
        "expected_step": "ask_additional_info",
    }
    with patch("backend.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.routes.testing.load_engine", return_value=FakeEngine("ask_info")) as mock_loader:
        response = client.post(
            "/api/v1/tests/process-state",
            json=payload,
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    mock_loader.assert_called_once_with("v1")
    data = response.json()
    assert data["version"] == "v1"
    assert data["client_id"] == 1
    assert data["step"] == "ask_additional_info"
    assert data["expected_step"] == "ask_additional_info"
    assert data["is_step_correct"] is True
    assert data["success"] is True
    assert "more details" in data["reply"]
    assert data["evaluation"]["passed"] is True


def test_url_version_parameter_selects_v2_engine(client):
    """Calling /api/v2/tests/process-state loads v2 engine directly from URL parameter."""
    payload = {
        "messages": [{"role": "user", "content": "hello"}],
        "expected_step": "ask_additional_info",
    }
    with patch("backend.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.routes.testing.load_engine", return_value=FakeEngine("ask_info")) as mock_loader:
        response = client.post(
            "/api/v2/tests/process-state",
            json=payload,
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    mock_loader.assert_called_once_with("v2")
    data = response.json()
    assert data["version"] == "v2"
    assert data["step"] == "ask_additional_info"
    assert data["is_step_correct"] is True


def test_evaluate_tool_use_step_from_conversation_only(client):
    """Verify tool_use step detection when only conversation messages are provided."""
    payload = {
        "test_id": "test_tool_use",
        "messages": [{"role": "user", "content": "I need a plumber for a leaking pipe"}],
        "expected_step": "tool_use",
        "expected_tools": [{"name": "fetch_available_categories"}],
    }
    with patch("backend.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.routes.testing.load_engine", return_value=FakeEngine("tool_use")):
        response = client.post(
            "/api/v1/tests/process-state",
            json=payload,
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["step"] == "tool_use"
    assert data["is_step_correct"] is True
    assert any(t["name"] == "fetch_available_categories" for t in data["turn_summary"]["tool_calls_made"])
    assert data["evaluation"]["passed"] is True


def test_evaluate_request_hitl_step_version_agnostic(client):
    """Verify request_hitl step detection from the assistant's confirmation draft across versions."""
    payload = {
        "test_id": "test_hitl",
        "messages": [
            {"role": "user", "content": "I need a plumber to fix a leaking pipe under my kitchen sink."}
        ],
        "expected_step": "request_hitl",
    }
    with patch("backend.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.routes.testing.load_engine", return_value=FakeEngine("request_hitl")):
        response = client.post(
            "/api/v2/tests/process-state",
            json=payload,
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "v2"
    assert data["step"] == "request_hitl"
    assert data["is_step_correct"] is True
    assert data["evaluation"]["passed"] is True


def test_evaluate_generate_document_step(client):
    """Verify generate_document step when project/tender is confirmed and saved."""
    payload = {
        "test_id": "test_gen_doc",
        "messages": [
            {"role": "user", "content": "I need a plumber to fix a leaking pipe."},
            {
                "role": "assistant",
                "content": "**Plumbing**\n\n**Description:**\nFix leak\n\n**Address:**\n123 Main St\n\n---\nConfirm?",
            },
            {"role": "user", "content": "Yes, confirmed!"},
        ],
        "expected_step": "generate_document",
    }
    with patch("backend.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.routes.testing.load_engine", return_value=FakeEngine("generate_document")):
        response = client.post(
            "/api/v1/tests/process-state",
            json=payload,
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["step"] == "generate_document"
    assert data["is_step_correct"] is True
    assert data["evaluation"]["passed"] is True


def test_step_mismatch_sets_is_step_correct_false(client):
    """When actual step differs from expected_step, is_step_correct and success must be False."""
    payload = {
        "test_id": "test_mismatch",
        "messages": [{"role": "user", "content": "hello"}],
        "expected_step": "generate_document",
    }
    with patch("backend.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.routes.testing.load_engine", return_value=FakeEngine("ask_info")):
        response = client.post(
            "/api/v1/tests/process-state",
            json=payload,
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["step"] == "ask_additional_info"
    assert data["expected_step"] == "generate_document"
    assert data["is_step_correct"] is False
    assert data["success"] is False
    assert data["evaluation"]["passed"] is False


# ---------------------------------------------------------------------------
# 4. Dynamic Engine Discovery via URL & Dry-Run Isolation
# ---------------------------------------------------------------------------

def test_invalid_url_version_returns_400(client):
    """Requesting an unknown version in /api/{version}/tests/process-state returns 400 Bad Request."""
    payload = {"messages": [{"role": "user", "content": "hello"}]}
    with patch("backend.routes.testing.get_client_by_id", return_value=MOCK_CLIENT):
        response = client.post(
            "/api/v99/tests/process-state",
            json=payload,
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 400
    assert "v99" in response.json()["detail"]


def test_dry_run_default_is_true(client):
    """Verify dry_run defaults to True and is passed down to engine.process."""
    fake_engine = FakeEngine("ask_info")
    payload = {"messages": [{"role": "user", "content": "hello"}]}
    with patch("backend.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.routes.testing.load_engine", return_value=fake_engine):
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

def test_max_requests_before_503_error(client, tmp_path, monkeypatch):
    """Test batch concurrency to observe maximum concurrent requests before 503 errors start."""
    import backend.config as config_mod
    import backend.routes.testing as testing_mod
    from fastapi import HTTPException

    assert not hasattr(config_mod, "MAX_ACTIVE_REQUESTS")
    monkeypatch.setattr(testing_mod, "TEST_JOBS_DIR", tmp_path)

    class CapacityLimitedEngine:
        """Simulates an engine/LLM backend that starts returning 503 after 3 requests."""

        def __init__(self, max_before_503: int = 3):
            self.max_before_503 = max_before_503
            self.count = 0

        def process(self, state: AgentState, dry_run: bool = False) -> AgentState:
            self.count += 1
            if self.count > self.max_before_503:
                raise HTTPException(
                    status_code=503,
                    detail="Service Unavailable: Upstream LLM overloaded",
                )
            state.messages = list(state.messages) + [
                {"role": "assistant", "content": "Could you provide more details?"}
            ]
            return state

    batch_payload = {
        "job_name": "max_requests_before_503",
        "concurrency": 5,
        "total_requests": 5,
        "test_cases": ["ask_additional_info"],
    }

    with patch("backend.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.routes.testing.load_engine", return_value=CapacityLimitedEngine(max_before_503=3)):
        response = client.post(
            "/api/v1/tests/jobs",
            json=batch_payload,
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 200
    summary = response.json()
    assert summary["total_requests"] == 5
    assert summary["passed"] == 3
    assert summary["failed"] == 2
    assert summary["status_code_breakdown"] == {"200": 3, "503": 2}


def test_execution_timeout_returns_504(client, monkeypatch):
    """When engine execution exceeds config.REQUEST_TIMEOUT_SECONDS, endpoint returns 504."""
    import backend.config as config_mod

    monkeypatch.setattr(config_mod, "REQUEST_TIMEOUT_SECONDS", 0.05)

    slow_engine = FakeEngine("ask_info", delay_seconds=0.3)
    payload = {"messages": [{"role": "user", "content": "hello"}]}
    with patch("backend.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.routes.testing.load_engine", return_value=slow_engine):
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
    """POST /api/{version}/tests/jobs runs batch requests using header client ID and writes artifacts."""
    import backend.routes.testing as testing_mod

    monkeypatch.setattr(testing_mod, "TEST_JOBS_DIR", tmp_path)

    batch_payload = {
        "job_name": "unit_test_batch",
        "concurrency": 2,
        "fail_fast": False,
        "requests": [
            {
                "test_id": "case_pass",
                "messages": [{"role": "user", "content": "hello"}],
                "expected_step": "ask_additional_info",
            },
            {
                "test_id": "case_fail",
                "messages": [{"role": "user", "content": "hello"}],
                "expected_step": "generate_document",
            },
        ],
    }

    with patch("backend.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.routes.testing.load_engine", return_value=FakeEngine("ask_info")):
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


def test_batch_job_repeats_single_case_with_total_requests_and_concurrency(client, tmp_path, monkeypatch):
    """POST /api/{version}/tests/jobs can run many requests at once from single test case files."""
    import backend.routes.testing as testing_mod

    monkeypatch.setattr(testing_mod, "TEST_JOBS_DIR", tmp_path)

    batch_payload = {
        "job_name": "stress_single_case",
        "concurrency": 4,
        "total_requests": 6,
        "test_cases": ["ask_additional_info"],
    }

    with patch("backend.routes.testing.get_client_by_id", return_value=MOCK_CLIENT), \
         patch("backend.routes.testing.load_engine", return_value=FakeEngine("ask_info")):
        response = client.post(
            "/api/v1/tests/jobs",
            json=batch_payload,
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 200
    summary = response.json()
    assert summary["total_requests"] == 6
    assert summary["concurrency"] == 4
    assert summary["passed"] == 6
    assert summary["status_code_breakdown"] == {"200": 6}


# ---------------------------------------------------------------------------
# 7. CLI Runner Script Tests (scripts/run_test.py)
# ---------------------------------------------------------------------------

def test_cli_runner_list_and_resolve():
    """Verify every JSON file in backend/tests/agent_cases/ is a single request."""
    from scripts.run_test import AGENT_CASES_DIR, list_available_tests, resolve_test_path

    available = list_available_tests()
    assert "ask_additional_info" in available
    assert "tool_use_categories" in available
    assert "request_hitl_confirmation" in available
    assert "generate_document_confirmed" in available
    assert "batch_smoke_suite" not in available
    assert "batch_concurrency_stress" not in available

    for name in available:
        path = AGENT_CASES_DIR / f"{name}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "messages" in data and "requests" not in data

    resolved = resolve_test_path("ask_additional_info")
    assert resolved.name == "ask_additional_info.json"
    assert resolved.exists()
