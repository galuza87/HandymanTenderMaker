# Agent Testing Endpoints & CLI Runner Guide (`readme_tests.md`)

## 1. Overview

The **Version-Agnostic Agent Testing Endpoints** (`/api/{version}/tests/*`) let you test any turn of any bot version (`v1` Multi-Agent LangGraph, `v2` Autonomous Deep Agent, or future versions) by identifying the client in the **`Authorization: Bearer <value>`** header and passing **only a single conversation** in each test case file.

### Dual-Mode Header Authentication & Client Identification (`Authorization: Bearer <value>`)
1. **Test Mode (`X-Test-Api-Key` header is present and valid):**
   - Pass `X-Test-Api-Key: dev-test-api-key` (matching `TEST_API_KEY` in `.env`).
   - Pass `Authorization: Bearer <client_id>` where `<client_id>` is the integer `dbo.Clients.id` (e.g., `Authorization: Bearer 1`).
   - The server looks up that `Clients.id` in `dbo.Clients` (returning `404` if not found) and populates the client's real profile (`name`, `phone`, `address`).
2. **Real JWT Mode (`X-Test-Api-Key` header is NOT present):**
   - Pass a signed HS256 JWT token in `Authorization: Bearer <token>`.
   - The server verifies the JWT signature (`JWT_SECRET_KEY`), extracts `client_id` from the token payload, and looks up that client in `dbo.Clients`.

### Single-Request Test Case Files (`backend/tests/agent_cases/`)
Every file in `backend/tests/agent_cases/` contains **one single request**:
- `ask_additional_info.json` — Greeting (`"hello"`) → expects `ask_additional_info`.
- `tool_use_categories.json` — Plumbing request → expects `tool_use` (`fetch_available_categories`).
- `request_hitl_confirmation.json` — Detailed plumbing request → expects `request_hitl`.
- `generate_document_confirmed.json` — User confirms the draft → expects `generate_document`.

---

## 2. How to Run a Single Request in Postman

- **Method & URL:** `POST http://localhost:8000/api/v1/tests/process-state` *(or `/api/v2/tests/process-state`)*
- **Headers:**
  | Key | Value |
  | :--- | :--- |
  | `Content-Type` | `application/json` |
  | `X-Test-Api-Key` | `dev-test-api-key` |
  | `Authorization` | `Bearer 1` |

- **Body (`raw` → `JSON`):**
  ```json
  {
    "messages": [
      {
        "role": "user",
        "content": "hello"
      }
    ],
    "expected_step": "ask_additional_info"
  }
  ```

---

## 3. How to Run a Batch of Many Requests at Once (Concurrency & 503/504 Stress Testing)

You do **not** need a file with an array of requests to run a batch. Instead, send a single request to **`POST /api/{version}/tests/jobs`** specifying:
- `concurrency`: How many requests run **simultaneously at the exact same time** to test the real capacity of the system and find the maximum concurrent requests before starting to get **`503 Service Unavailable`** or **`504 Gateway Timeout`** (when execution exceeds `REQUEST_TIMEOUT_SECONDS`, default `60s`).
- `total_requests`: Total number of requests to fire in the batch.
- **Automated Capacity Test**: The pytest suite ([test_agent_testing_endpoints.py](file:///c:/Users/User/React/Projects/DynamicPromptWizard/backend/tests/api/test_agent_testing_endpoints.py)) includes `test_max_requests_before_503_error`, which tests running concurrent requests in a batch to determine the maximum requests handled before starting to get `503` errors.

### Option A: In Postman (`POST http://localhost:8000/api/v1/tests/jobs`)
Uses the same headers (`X-Test-Api-Key: dev-test-api-key`, `Authorization: Bearer 1`).

**1. Repeat a single test case file 20 times with 15 running simultaneously:**
```json
{
  "concurrency": 15,
  "total_requests": 20,
  "test_cases": ["ask_additional_info"]
}
```

**2. Or repeat an inline message 20 times with 15 running simultaneously:**
```json
{
  "concurrency": 15,
  "total_requests": 20,
  "messages": [
    {
      "role": "user",
      "content": "hello"
    }
  ],
  "expected_step": "ask_additional_info"
}
```

**3. Or cycle through all single test case files in `backend/tests/agent_cases/`:**
```json
{
  "concurrency": 12,
  "total_requests": 20
}
```

### Option B: Via the CLI (`scripts/run_test.py`)
```powershell
# Fire 20 requests of ask_additional_info with 15 running at once:
python scripts/run_test.py ask_additional_info --concurrency 15 --total-requests 20

# Fire 16 requests cycling across all single-case files with 8 running at once:
python scripts/run_test.py all --concurrency 8 --total-requests 16
```

### Where to See When 500-Type (`503` / `504`) Errors Happen
1. **Directly in the Postman JSON Response**:
   - `status_code_breakdown`: e.g. `{"200": 10, "503": 10}` or `{"200": 8, "504": 2}`.
   - `failed_requests`: Lists every request that failed or returned `500` / `503` / `504` along with its exact error detail and execution time in ms.
2. **In the Auto-Generated Job Folder (`backend/test_jobs/job_<job_id>/`)**:
   - `job.log`: Chronological log of every request (`PASS` / `FAIL`, HTTP status code, and latency).
   - `summary.json`, `results.json`, and `failed_requests.json`.
