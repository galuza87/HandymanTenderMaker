# Feature Plan: Agent Testing Endpoints

## 1. Objective & Overview

Establish dedicated backend testing endpoints to deterministically validate the AI agent engine and measure system capacity limits. By injecting conversation states (`AgentState`) along with an optional **Gold Standard (`expected_outcome`)** directly in the request, testers can:

1. **Run a Single Request Manually (Debug Mode):** Execute an individual conversation turn in isolation and inspect state transitions, tool calls, and gold-standard evaluation.
2. **Run a Batch Job of Many Requests:** Execute a suite of test requests in a single job (sequentially or concurrently), automatically persisting structured logs and failure reports into a dedicated job directory (`backend/test_jobs/job_<job_id>/`).
3. **Measure System Concurrency Limits (`503` / `504`):** Determine how many simultaneous requests the server and LLM backend can handle before returning `503 Service Unavailable` (capacity exceeded) or `504 Gateway Timeout` (upstream/LLM timeout).

---

## 2. API Endpoints Specification

### 2.1 Single Request Endpoint (Manual Debug)

- **Method:** `POST`
- **Path:** `/api/v1/tests/process-state`
- **Purpose:** Executes a single turn against an injected conversation state for manual debugging or external test runners, and evaluates the result against an optional `expected_outcome` (gold standard) provided inside the request.
- **Authentication:** HTTP Basic Auth (`Authorization: Basic <base64(phone:password)>`).
- **Target User Simulation:** Requires `simulated_user_id` in the request body. The server verifies that this user exists in `dbo.Clients`. If not found, it immediately responds with `404 Not Found` (no fallback to tester). Upon verification, `state.user_id` is set to this ID and profile details are merged from the DB into `state.client_info`.

#### Request Interface (`StateTestRequest`)

```typescript
type OutcomeType =
  | "generate_document"    // Agent generates final tender / confirmed_job_description
  | "request_hitl"         // Agent requests human-in-the-loop confirmation/approval
  | "tool_use"             // Agent invokes specific tool(s) during the turn
  | "ask_additional_info"; // Agent asks the user clarifying questions for missing details

interface ExpectedOutcome {
  // Primary expected behavior for this turn
  outcome_type: OutcomeType;

  // Optional gold-standard assertions depending on outcome_type:
  expected_tools?: Array<{
    name: string;
    args_subset?: Record<string, any>; // Expected key/values in tool arguments
  }>;
  expected_state_fields?: Record<string, any>; // e.g., { is_finished: true, CategorizerDecision: { decision: "single" } }
  required_keywords?: string[];                // Keywords/phrases expected in the assistant's reply or generated document
  reference_text?: string;                     // Gold-standard reference text for semantic/content comparison
}

interface StateTestRequest {
  // Optional identifier for tracking inside batch jobs and logs
  test_id?: string;

  // Required: Target client persona to simulate. MUST exist in the database
  simulated_user_id: number;

  // Injected conversation state to execute
  state: {
    session_id?: string;
    // Complete conversation history including user, assistant, system, and tool messages
    messages: Array<{
      role: "user" | "assistant" | "system" | "tool";
      content: string;
      tool_calls?: Array<{
        id: string;
        name: string;
        args: Record<string, any>;
      }>;
      tool_call_id?: string; // Required when role === "tool"
      name?: string;         // Optional tool name when role === "tool"
    }>;
    identified_categories?: Array<{ category_id: number; name: string }>;
    prompts?: Array<{ id: number; category_id: number; prompt_text: string }>;
    collected_details?: Record<string, string>;
    client_info?: {
      name?: string;
      phone?: string;
      address?: string;
    };
    confirmed_job_description?: string;
    next_step?: string;
    CategorizerDecision?: { decision: "single" | "multiple" };
    project_id?: number;
    is_finished?: boolean;
  };

  // Optional gold standard embedded directly in the request
  expected_outcome?: ExpectedOutcome;

  // Tool execution context & environment flags
  options?: {
    dry_run?: boolean;          // Default: true. Prevents writing projects/conversations to real DB
    algorithm_version?: string; // e.g., "v1", "v2", "v1.1" — auto-loaded from backend/{version}/engine.py
    timeout_seconds?: number;   // Optional per-request timeout before returning 504 Gateway Timeout
  };
}
```

#### Response Interface (`StateTestResponse`)

```typescript
interface EvaluationResult {
  passed: boolean;
  expected_outcome_type: OutcomeType;
  actual_outcome_type: OutcomeType;
  mismatches: string[]; // Detailed reasons if passed === false
}

interface StateTestResponse {
  test_id?: string;
  success: boolean;
  execution_time_ms: number;

  // The complete mutated state returned by the engine
  state: AgentState;

  // Convenience extraction of updates produced during this turn
  turn_summary: {
    detected_outcome_type: OutcomeType;
    new_messages: Array<{
      role: "user" | "assistant" | "system" | "tool";
      content: string;
      tool_calls?: Array<any>;
      tool_call_id?: string;
    }>;
    latest_message: {
      role: string;
      content: string;
    } | null;
    tool_calls_made: Array<{
      name: string;
      args: Record<string, any>;
    }>;
    updated_fields: Record<string, any>;
  };

  // Present when expected_outcome was supplied in the request
  evaluation?: EvaluationResult;
}
```

---

### 2.2 Batch Job Endpoints (Many Requests & Job Directory Logging)

To run a batch of test cases (either for regression verification or concurrency stress testing) and inspect detailed logs of what passed or failed:

- **`POST /api/v1/tests/jobs`**: Submits and executes a batch job of multiple `StateTestRequest` items.
- **`GET /api/v1/tests/jobs/{job_id}`**: Retrieves the status, summary metrics, and failure breakdown of a job from its job directory.

#### Batch Job Request (`BatchTestJobRequest`)

```typescript
interface BatchTestJobRequest {
  job_name?: string;
  // Number of requests to execute in parallel (1 = sequential, N = concurrent stress test)
  concurrency?: number;
  // Stop job early on first failure if true (default: false)
  fail_fast?: boolean;
  // Array of individual test requests (each with its own conversation state and optional expected_outcome)
  requests: StateTestRequest[];
}
```

#### Dedicated Job Directory & Log Files (`backend/test_jobs/job_<job_id>/`)

Every batch job creates a dedicated folder named with its unique `job_id` (e.g., `backend/test_jobs/job_0001_20261118_184500/`):

```text
backend/test_jobs/
└── job_0001_20261118_184500/
    ├── job.log               # Chronological execution log (start, per-request status, errors, completion)
    ├── summary.json          # Overall job status (PASSED / FAILED), counts, latency metrics, HTTP status breakdown
    ├── results.json          # Full responses and evaluations for all requests in the job
    └── failed_requests.json  # Filtered details of only the requests that failed (gold-standard mismatch, 503, 504, or 500)
```

- **`job.log` Example:**
  ```text
  [2026-11-18 18:45:01] INFO  Job #0001 started | total_requests=20 | concurrency=5
  [2026-11-18 18:45:03] PASS  [req_01] test_id="plumbing_ask_info" | status=200 | outcome=ask_additional_info | 1840ms
  [2026-11-18 18:45:04] FAIL  [req_02] test_id="plumbing_generate_doc" | status=200 | expected=generate_document actual=ask_additional_info | 2110ms
  [2026-11-18 18:45:05] FAIL  [req_08] test_id="load_spike_08" | status=503 Service Unavailable (Active capacity limit reached) | 12ms
  [2026-11-18 18:45:31] FAIL  [req_09] test_id="load_spike_09" | status=504 Gateway Timeout (Exceeded 30s timeout) | 30004ms
  [2026-11-18 18:45:32] INFO  Job #0001 finished | status=FAILED | passed=17 | failed=3 (1 assertion, 1x 503, 1x 504)
  ```

---

## 3. Outcome Classification & Gold Standard Evaluation

After `engine.process(state)` finishes a turn, the test harness classifies the turn's actual outcome (`detected_outcome_type`) and compares it against `expected_outcome`:

| Outcome Type | Detection Criteria | Gold Standard Assertions Checked |
| :--- | :--- | :--- |
| `generate_document` | `confirmed_job_description` is newly populated, `save_project_and_tenders` is called, or `is_finished === true`. | Checks `confirmed_job_description` / reply against `required_keywords`, `reference_text`, and `expected_state_fields`. |
| `request_hitl` | Agent presents a synthesized draft/summary and asks the user for confirmation/approval before saving or finalizing (e.g., `next_step` transitions to confirmation or assistant awaits approval). | Checks that the assistant prompts for confirmation without prematurely writing the final project record. |
| `tool_use` | One or more `tool_calls` were emitted by the assistant during this turn. | Verifies every entry in `expected_tools` (matching tool `name` and `args_subset`). |
| `ask_additional_info` | Assistant replies with clarifying questions to gather task specifications (`is_finished === false`, no final tender generated). | Verifies assistant response is non-empty and checks `required_keywords` or `expected_state_fields` (such as `collected_details`). |

---

## 4. System Limitation & Concurrency Testing (`503` & `504`)

Rather than hiding concurrency limits behind an infinite wait queue, the testing architecture explicitly surfaces system bottlenecks so testers can measure how many simultaneous requests the server can handle:

1. **Non-Blocking Worker Execution (`asyncio.to_thread`)**:
   - Synchronous graph/LLM execution runs inside `asyncio.to_thread(engine.process, isolated_state, dry_run=dry_run)` so FastAPI's event loop stays responsive and can accurately track in-flight requests and timeouts.
2. **`503 Service Unavailable` (Capacity / Overload Limit)**:
   - The server tracks `active_requests` in flight.
   - Instead of silently queuing excess requests forever, if active concurrent requests exceed the system capacity threshold (`MAX_ACTIVE_REQUESTS`, configurable per environment or test run) or when the underlying worker/connection pool is exhausted, the endpoint immediately rejects the request with **HTTP `503 Service Unavailable`** (`{"detail": "Server at maximum concurrent capacity", "active_requests": N}`).
3. **`504 Gateway Timeout` (LLM / Execution Timeout)**:
   - Each turn execution is wrapped in `asyncio.wait_for(..., timeout=timeout_seconds)` (default configurable via `TEST_REQUEST_TIMEOUT_SECONDS`, e.g., `30s`, or overridden per request via `options.timeout_seconds`).
   - When high concurrency causes the LLM backend (e.g., LM Studio or OpenAI) to stall or take longer than the allowed threshold, the server aborts waiting and returns **HTTP `504 Gateway Timeout`**.
4. **Capacity Benchmark Test**:
   - Using `POST /api/v1/tests/jobs` (with `concurrency: N`) or Postman Performance Runner, testers can ramp up `concurrency` (e.g., `1 -> 5 -> 10 -> 20`) and inspect `summary.json` / `job.log` to see the exact concurrency level where `503 Service Unavailable` or `504 Gateway Timeout` responses begin appearing.

---

## 5. Dynamic Engine Auto-Discovery (Zero-Registration)

To support testing any engine version (e.g., `v1`, `v2`, future `v1.1` or `v3`) without requiring developers to register them in a central file:

1. **Version Normalization**: Version strings in `options.algorithm_version` are normalized (`"v1.1"` -> `"v1_1"`). If omitted, the default `ALGORITHM_VERSION` from server configuration is used.
2. **Dynamic Reflection**:
   ```python
   import importlib

   def load_engine(version_str: str):
       module_suffix = version_str.replace(".", "_")
       try:
           module = importlib.import_module(f"backend.{module_suffix}.engine")
           return module.Engine()
       except ModuleNotFoundError:
           raise HTTPException(
               status_code=400,
               detail=f"Engine version '{version_str}' not found. Make sure backend/{module_suffix}/engine.py exists."
           )
   ```

---

## 6. Message Schema & Bidirectional Mapping

To support multi-turn conversations and intermediate tool-calling states, the endpoint handles 4 core message roles:

| Role | Meaning | Required Fields | Optional Fields |
| :--- | :--- | :--- | :--- |
| `user` | Human user prompt | `role: "user"`, `content: string` | `image: string` |
| `assistant` | Agent response | `role: "assistant"`, `content: string` | `tool_calls: list` |
| `system` | Context or system instruction override | `role: "system"`, `content: string` | - |
| `tool` | Output from executed tool | `role: "tool"`, `content: string`, `tool_call_id: string` | `name: string` |

- **Inbound:** Dict messages are mapped directly to LangChain core primitives (`HumanMessage`, `AIMessage`, `SystemMessage`, `ToolMessage`).
- **Outbound:** LangChain messages returned from LangGraph / DeepAgent are converted back into JSON-serializable dictionaries preserving `tool_calls` and `tool_call_id`.

---

## 7. Authentication & Database Isolation

### 7.1 Testing Endpoint Authentication (`/api/v1/tests/*`)
- **Caller Authentication:** Direct HTTP Basic Auth header (`Authorization: Basic <base64(phone:password)>`) via `get_test_user_basic` so single requests and batch jobs are completely self-contained.
- **Mandatory Target Persona (`simulated_user_id`):**
  - Every test request **MUST** include `simulated_user_id: number`.
  - The server queries `dbo.Clients` via `get_client_by_id(simulated_user_id)`. If the user does not exist, it returns `404 Not Found`.
  - Once verified, the server sets `state.user_id = client.id` and populates `state.client_info` (`name`, `phone`, `address`) from the database record.

### 7.2 Tool Safety & `dry_run` Isolation
- **`dry_run: true` (Default):**
  - When `dry_run` is active, database write operations (`create_project`, `create_project_prompt`, `save_conversation`) are intercepted by an in-memory stub that returns a mock ID (e.g., `project_id: 9999`) without polluting SQLite/SQL Server tables.
- **Category Fallbacks:**
  - If `fetch_available_categories` cannot reach the database, it falls back to a static category listing.

---

## 8. Implementation Roadmap

### Step 1: Pydantic Request, Gold Standard & Job Models (`backend/models.py`)
- Define `OutcomeType`, `ExpectedOutcome`, `EvaluationResult`.
- Define `StateTestMessage`, `StateTestOptions`, `StateTestRequest`, `StateTestResponse`.
- Define `BatchTestJobRequest` and `BatchTestJobResponse`.

### Step 2: Engine Dry Run & Message Serialization (`backend/v1/engine.py` & `backend/v2/engine.py`)
- Add `dry_run: bool = False` support to `Engine.process(state, dry_run=False)`.
- Ensure tool calls in `v1` and `v2` honor `dry_run` and skip persistent DB writes when enabled.
- Ensure all message types (`user`, `assistant`, `system`, `tool`) serialize and deserialize cleanly.

### Step 3: Gold Standard Evaluator & Outcome Classifier (`backend/v1/services/test_evaluator.py`)
- Implement outcome detection (`generate_document`, `request_hitl`, `tool_use`, `ask_additional_info`).
- Implement state delta extraction (`turn_summary.updated_fields` and `tool_calls_made`).
- Implement `evaluate_outcome(expected: ExpectedOutcome, state_before, state_after, turn_summary) -> EvaluationResult`.

### Step 4: Single Request & Batch Job Endpoints with `503`/`504` Guard (`backend/v1/routes/testing.py`)
- Implement `POST /api/v1/tests/process-state` for single manual debug execution.
- Enforce active capacity tracking (`503 Service Unavailable` when overloaded) and `asyncio.wait_for` execution timeout (`504 Gateway Timeout`).
- Implement `POST /api/v1/tests/jobs` and `GET /api/v1/tests/jobs/{job_id}` with per-job directory creation (`backend/test_jobs/job_<job_id>/`) and structured log outputs (`job.log`, `summary.json`, `results.json`, `failed_requests.json`).

### Step 5: Verification with Automated Tests & Postman Collection
- Create unit/integration tests for single-turn gold-standard validation (`generate_document`, `request_hitl`, `tool_use`, `ask_additional_info`), batch job logging, and `503`/`504` capacity/timeout responses.
- Provide a Postman Collection JSON for manual single-request debugging, batch job execution, and concurrency limit testing.
