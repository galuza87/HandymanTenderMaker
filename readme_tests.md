# Agent Testing Endpoints & CLI Runner Guide (`readme_tests.md`)

## 1. Overview

The **Agent Testing Endpoints** allow you to deterministically test any turn of the AI agent engine (`v1` Multi-Agent LangGraph or `v2` Autonomous Deep Agent) and measure system concurrency limits (`503 Service Unavailable` and `504 Gateway Timeout`).

### Action-Only Evaluation Philosophy
Tests do **not** evaluate free-text wording. Instead, every test evaluates **only the action taken by the agent**:
1. **Primary Action (`outcome_type`)**:
   - `ask_additional_info`: The agent detected missing context/information and paused to ask the user.
   - `tool_use`: The agent invoked one or more tools during the turn (e.g., `fetch_available_categories`, `update_open_topics`).
   - `request_hitl`: The agent finished gathering details and presented the structured draft for human-in-the-loop confirmation without saving prematurely.
   - `generate_document`: The agent confirmed and saved the final tender/project (`confirm_and_save_document` or `save_project_and_tenders` called, `confirmed_job_description` populated, or `is_finished: true`).
2. **Tool Calls (`expected_tools`)**: Verifies whether the expected tool(s) were called (and optional `args_subset`).
3. **Node & State Transitions (`expected_state_fields`)**: Verifies whether the engine transitioned to the expected node (`next_step`), set `CategorizerDecision`, or updated `is_finished`.

---

## 2. Where Tests and Logs Are Stored

| Directory | Purpose |
| :--- | :--- |
| `backend/tests/agent_cases/` | **JSON Test Definitions** triggered by `scripts/run_test.py <test_name>`. Stores both single-turn (`StateTestRequest`) and batch (`BatchTestJobRequest`) JSON files. |
| `backend/tests/api/` | **Pytest Endpoint & Integration Suite** (`test_agent_testing_endpoints.py`, `test_categories.py`). |
| `backend/test_jobs/job_<job_id>/` | **Batch Job Output Artifacts** generated automatically whenever `POST /api/v1/tests/jobs` runs (`job.log`, `summary.json`, `results.json`, `failed_requests.json`). |
| `scripts/run_test.py` | **CLI Runner Script** that sends a named test from `backend/tests/agent_cases/` to the live FastAPI server (`http://localhost:8000`). |

### Included Test Cases in `backend/tests/agent_cases/`
- `ask_additional_info.json` — Vague user greeting at `DataValidator`; verifies `ask_additional_info` and `is_finished: false`.
- `tool_use_categories.json` — Plumbing request at `ContractorCategorizer`; verifies `tool_use` (`fetch_available_categories`) and transition to `next_step: "IntakeCoordinator"`.
- `request_hitl_confirmation.json` — Resolved intake state at `IntakeCoordinator`; verifies `request_hitl` confirmation prompt before saving.
- `generate_document_confirmed.json` — User confirms the draft at `IntakeCoordinator`; verifies `generate_document`, `confirm_and_save_document` tool call, and `is_finished: true`.
- `batch_smoke_suite.json` — Batch job executing multiple action test cases (`concurrency: 2`).
- `batch_concurrency_stress.json` — Batch load test (`concurrency: 5`) to benchmark `503`/`504` system limits.

---

## 3. Environment & Authentication Setup (`.env`)

The testing endpoints use a dedicated API key + feature flag in `.env` while validating `simulated_user_id` against real client records in `dbo.Clients`:

```env
# Enable or disable /api/v1/tests/* endpoints (returns 403 when false)
ENABLE_TEST_ENDPOINTS=true

# Secret key required in X-Test-Api-Key or Authorization: Bearer <TEST_API_KEY>
TEST_API_KEY=dev-test-api-key

# Application-wide request timeout (used by both /chat and /api/v1/tests/*, configurable in backend/config.py or .env)
REQUEST_TIMEOUT_SECONDS=60.0

# Concurrency threshold for 503 testing
MAX_ACTIVE_REQUESTS=10
```

- **Caller Authentication**: Pass `X-Test-Api-Key: <TEST_API_KEY>` or `Authorization: Bearer <TEST_API_KEY>`.
- **Target Persona (`simulated_user_id`)**: Every test request includes `simulated_user_id` (e.g., `1`). The server verifies that this ID exists in `dbo.Clients` (returning `404 Not Found` if missing) and populates `state.user_id` and `state.client_info` (`name`, `phone`, `address`) from the database.
- **Database Isolation (`dry_run: true`)**: By default, `options.dry_run` is `true`, which stubs out database writes (`create_project`, `create_project_prompt`) with mock project ID `9999` so test runs never pollute production/dev tables.

### Timeout (`504`) & Concurrency (`503`) Configuration
- **Single System Timeout (`REQUEST_TIMEOUT_SECONDS`)**: Defined in `backend/config.py` (`REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "60.0"))`) and optionally overridden via `.env`. This single value governs **both** the main application (`/chat` endpoint and `ChatOpenAI` LLM client) and all agent testing endpoints (`/api/v1/tests/*`). When exceeded, the server aborts and returns **HTTP `504 Gateway Timeout`**.
- **Concurrency Limit (`MAX_ACTIVE_REQUESTS`)**: Controls the maximum number of simultaneous in-flight test requests before the server immediately returns **HTTP `503 Service Unavailable`** (default: `10`).

#### Where You See `504` Timeouts & Timing
- **Single Request (`POST /api/v1/tests/process-state`)**: Returns HTTP `504` with `{"detail": "Gateway Timeout: Agent execution exceeded <N>s timeout."}`.
- **Batch Job (`POST /api/v1/tests/jobs` / `scripts/run_test.py`)**:
  - **CLI Output**: Shown in `HTTP Breakdown` (e.g., `{'200': 4, '504': 1}`) and `Failed Requests Breakdown`.
  - **`backend/test_jobs/job_<job_id>/job.log`**: Logs the exact status and elapsed time in ms (e.g., `FAIL [req_05] test_id="..." | status=504 (Gateway Timeout: Agent execution exceeded 30s timeout.) | 30004ms`).
  - **`summary.json` & `failed_requests.json`**: Records `status_code_breakdown["504"]`, `execution_time_ms`, and the timeout `error` message.

---

## 4. How to Run Tests via the CLI Script

### Step 1: Start the FastAPI Backend Server
Make sure the backend server is running on `http://localhost:8000`:
```powershell
python -m backend.main
```

### Step 2: List Available Tests
```powershell
python scripts/run_test.py --list
```

### Step 3: Trigger a Specific Test by Name
Pass the test name (with or without `.json`) as the parameter to `scripts/run_test.py`:

```powershell
# Run a single-turn test case (calls POST /api/v1/tests/process-state)
python scripts/run_test.py ask_additional_info
python scripts/run_test.py tool_use_categories
python scripts/run_test.py request_hitl_confirmation
python scripts/run_test.py generate_document_confirmed

# Run a batch job test suite (calls POST /api/v1/tests/jobs)
python scripts/run_test.py batch_smoke_suite

# Run the concurrency stress test
python scripts/run_test.py batch_concurrency_stress
```

### Step 4: Run All Test Cases or Override Options
```powershell
# Run every JSON test in backend/tests/agent_cases/
python scripts/run_test.py all

# Override algorithm version (e.g., v1 or v2), simulated user ID, or batch concurrency
python scripts/run_test.py tool_use_categories --version v1 --user-id 1
python scripts/run_test.py batch_concurrency_stress --concurrency 8
```

---

## 5. How the API Endpoints Work

### 5.1 Single Request Endpoint (`POST /api/v1/tests/process-state`)
Executes a single turn from an injected `AgentState` and evaluates the action taken.

**Example Request:**
```json
{
  "test_id": "tool_use_categories",
  "simulated_user_id": 1,
  "state": {
    "session_id": "test-session-tool-use",
    "messages": [
      {
        "role": "user",
        "content": "I need a plumber to fix a leaking pipe under my kitchen sink."
      }
    ],
    "next_step": "ContractorCategorizer",
    "CategorizerDecision": {
      "decision": "single"
    },
    "is_finished": false
  },
  "expected_outcome": {
    "outcome_type": "tool_use",
    "expected_tools": [
      {
        "name": "fetch_available_categories"
      }
    ],
    "expected_state_fields": {
      "next_step": "IntakeCoordinator"
    }
  },
  "options": {
    "dry_run": true,
    "algorithm_version": "v1"
  }
}
```

### 5.2 Batch Job Endpoints (`POST /api/v1/tests/jobs` & `GET /api/v1/tests/jobs/{job_id}`)
Executes multiple `StateTestRequest` items (sequentially when `concurrency: 1`, or in parallel when `concurrency > 1`) and writes structured artifacts into `backend/test_jobs/job_<job_id>/`:
- `job.log`: Chronological execution log showing per-request status, action outcome, and latency.
- `summary.json`: Overall job status (`PASSED` / `FAILED`), pass/fail counts, latency metrics, and HTTP status breakdown (`200`, `503`, `504`).
- `results.json`: Full responses and evaluations for all requests in the batch.
- `failed_requests.json`: Filtered list of only the requests that failed assertions or hit `503`/`504` errors.

---

## 6. Running the Automated Pytest Suite

To run the unit and integration tests in `backend/tests/api/test_agent_testing_endpoints.py` (which mock the engine and DB for fast deterministic verification):

```powershell
pytest backend/tests/api/test_agent_testing_endpoints.py -v
```
