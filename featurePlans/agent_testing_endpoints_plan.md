# Feature Plan: Agent Testing Endpoints

## 1. Objective & Overview

Establish dedicated testing endpoints that enable deterministically validate the AI agent engine. By injecting conversation states (`AgentState`) directly, testers can execute individual turns or parallel batch scenarios in isolation to verify state transitions, tool invocations, and output messages without UI dependencies or persistent database side effects.

---

## 2. API Endpoints Specification

### 2.1 Single State Processing Endpoint

- **Method:** `POST`
- **Path:** `/api/v1/tests/process-state`
- **Purpose:** Executes a single turn against an injected conversation state. Ideal for debugging edge cases, testing specific agent transitions, and verifying tool invocations in Postman.
- **Authentication:** Direct HTTP Basic Auth (`Authorization: Basic <base64(phone:password)>`). Authenticates that the caller is an authorized developer or tester.
- **Target User Simulation:** Requires a mandatory `simulated_user_id` in the request body. The server verifies that this user exists in `dbo.Clients`. If not found, it immediately responds with `404 Not Found` (no fallback to tester). Upon verification, `state.user_id` is set to this ID and profile details are merged from the DB into `state.client_info`.

#### Request Interface (`StateTestRequest`)

```typescript
interface StateTestRequest {
  // Required: Target client persona to simulate. MUST exist in the database (no fallback to tester)
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

  // Tool execution context & environment flags
  options?: {
    dry_run?: boolean;        // Default: true. Prevents writing projects/conversations to real DB
    // Dynamic engine version (e.g., "v1", "v2", "v1.1", "v3").
    // Auto-loaded dynamically from `backend/{version}/engine.py` — zero manual registration required.
    algorithm_version?: string;
  };

}
```

#### Response Interface (`StateTestResponse`)

```typescript
interface StateTestResponse {
  success: boolean;
  execution_time_ms: number;
  
  // The complete mutated state returned by the engine
  state: AgentState;

  // Convenience extraction of updates produced during this turn
  turn_summary: {
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
    // Exactly which fields on the state were mutated/populated during this turn
    // (e.g. CategorizerDecision, is_finished, confirmed_job_description, next_step)
    updated_fields: Record<string, any>;
  };
}
```

---

### 2.2 Parallel Batch State Processing Endpoint

- **Method:** `POST`
- **Path:** `/api/v1/tests/process-batch`
- **Purpose:** Executes multiple independent conversation sessions concurrently across parallel asynchronous tasks. Ideal for regression suites and benchmarking without slow sequential execution.
- **Authentication:** Direct HTTP Basic Auth (`Authorization: Basic <base64(phone:password)>`). Allows automated batch regression runs in a single call without token pre-fetching.
- **Multi-User Simulation:** Every test case in the batch must specify a mandatory `simulated_user_id`. Each specified user is verified against `dbo.Clients`. If any `simulated_user_id` does not exist in the database, that case fails with a user not found error (no fallback to tester).

#### Request Interface (`BatchTestRequest`)

```typescript
interface BatchTestRequest {
  concurrency_limit?: number; // Maximum concurrent agent calls (default: 5)
  stop_on_first_failure?: boolean; // Default: false
  cases: Array<{
    id: string; // Unique test case identifier, e.g., "tc-plumbing-single-01"
    description?: string;
    // Required: Target client persona for this case. MUST exist in database (no fallback to tester)
    simulated_user_id: number;
    state: AgentState;
    options?: {
      dry_run?: boolean;
      // Dynamic engine version (e.g., "v1", "v2", "v1.1", "v3").
      // Auto-loaded dynamically from `backend/{version}/engine.py` — zero manual registration required.
      algorithm_version?: string;
    };
  }>;
}
```

#### Response Interface (`BatchTestResponse`)

```typescript
interface BatchTestResponse {
  summary: {
    total_cases: number;
    successful_cases: number;
    failed_cases: number;
    total_time_ms: number;
    concurrency_limit: number;
  };
  results: Array<{
    id: string;
    success: boolean;
    execution_time_ms: number;
    state: AgentState;
    turn_summary: {
      new_messages: Array<any>;
      latest_message: any;
      updated_fields: Record<string, any>;
    };
    error?: string;
  }>;
}
```

---

## 3. Parallel Execution Technique

Rather than streaming events to a single client, parallel processing uses asynchronous non-blocking task orchestration in FastAPI:

1. **Async Worker Semaphore (`asyncio.Semaphore`)**:
   Limits maximum concurrent LLM API calls to avoid hitting rate limits on local LM Studio or cloud providers:

   ```python
   semaphore = asyncio.Semaphore(req.concurrency_limit or 5)

   async def _run_single_case(test_case):
       async with semaphore:
           # Engine process execution in worker thread to prevent event loop blocking
           return await asyncio.to_thread(engine.process, state, dry_run=True)

   # Run all sessions concurrently
   results = await asyncio.gather(*[_run_single_case(c) for c in req.cases], return_exceptions=True)
   ```
2. **Deterministic Context Isolation**:
   Each test session instantiates its own isolated `AgentState` clone and memory context so tests do not leak variables across concurrent tasks.
3. **Dynamic Engine Auto-Discovery (Zero-Registration)**:
   To support future versions like `v1.1`, `v2.1`, or `v3` without requiring developers to register them in any central file:

   - Version strings in `options.algorithm_version` are normalized (dots converted to underscores, e.g. `"v1.1"` -> `"v1_1"`).
   - The engine is dynamically loaded at runtime using standard Python reflection:
     ```python
     import importlib

     def load_engine(version_str: str):
         # Normalizes "v1.1" -> "v1_1", "v2" -> "v2"
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
   - **Zero Future Registration Needed**: When you create a new version (e.g. `v1.1`), you simply create the directory `backend/v1_1/engine.py`. The testing endpoints will automatically discover, load, and execute it without touching any other file or interface in the system.

---

## 4. Message Schema & Bidirectional Mapping

To support complex multi-turn conversations and intermediate tool-calling states, the endpoint handles 4 core message roles:

| Role          | Meaning                                | Required Fields                                                 | Optional Fields      |
| :------------ | :------------------------------------- | :-------------------------------------------------------------- | :------------------- |
| `user`      | Human user prompt                      | `role: "user"`, `content: string`                           | `image: string`    |
| `assistant` | Agent response                         | `role: "assistant"`, `content: string`                      | `tool_calls: list` |
| `system`    | Context or system instruction override | `role: "system"`, `content: string`                         | -                    |
| `tool`      | Output from executed tool              | `role: "tool"`, `content: string`, `tool_call_id: string` | `name: string`     |

### Serialization Rules:

- **Inbound:** Dict messages are mapped directly to LangChain core primitives (`HumanMessage`, `AIMessage`, `SystemMessage`, `ToolMessage`).
- **Outbound:** LangChain messages returned from LangGraph / DeepAgent are converted back into pure JSON-serializable dictionaries preserving `tool_calls` and `tool_call_id`.

---

## 5. Authentication Architecture: Real App (JWT) vs. Testing Endpoints (Basic Auth)

To ensure strict security and stateless token handling for real users while maintaining effortless single-request ergonomics for QA and Postman automation, authentication is separated cleanly:

### 5.1 Real Application Endpoints (`/chat`, `/api/client/*`) — Strictly JWT

- **Transport:** Standard HTTP Bearer Token header: `Authorization: Bearer <jwt_token>`.
- **Identity Derivation:** The server verifies the JWT signature and extracts `user_id` strictly from token claims (`sub`).
- **Payload Sanitization:** `user_id` is removed completely from `ChatRequest` so clients cannot spoof or tamper with identity in the request body.
- **Login Flow:** Users log in via `POST /api/login` with `{ phone, password }`. The server validates against a hashed password (bcrypt) in `dbo.Clients` and returns a signed HS256 JWT with 24-hour expiry (`TokenResponse`).

### 5.2 Agent Testing Endpoints (`/api/v1/tests/*`) — Strictly HTTP Basic Auth

- **Caller Authentication:** Direct HTTP Basic Auth header: `Authorization: Basic <base64(phone:password)>`.
  - Authenticates the developer/tester executing the tests in a **single self-contained request** without needing tokens.
- **Mandatory Target Persona (`simulated_user_id`):**
  - Every test request (or batch case) **MUST** include `simulated_user_id: number`.
  - **Strict DB Validation:** The server queries `dbo.Clients` via `get_client_by_id(simulated_user_id)`. If the user does not exist in the database, the server returns an immediate `404 Not Found` error (`"Simulated user_id '{simulated_user_id}' does not exist in the database."`).
  - **No Fallback to Tester:** The test will never silently fall back to the authenticated tester's ID.
  - **Identity & Profile Injection:** Once verified, the server injects `state.user_id = client.id` into the engine and auto-populates `state.client_info` with the real client's name, phone, and address strictly from the DB record. Mock client info is neither accepted nor supported.
- **Payload Protection:** `user_id` inside `state` is prohibited and ignored.

### 5.3 Required Application Updates for JWT Migration

Migrating real endpoints from the current unsecured `user_id` body payload to JWT requires updates across both backend and frontend:

#### 1. Database Schema & Migration (`dbo.Clients`)

- **SQL Column Addition:** Add `password_hash VARCHAR(255) NULL` to table `dbo.Clients`.
- **Migration/Backfill Script:** Provide a script to populate existing client records with an initial hashed password so existing users remain operable.

#### 2. Database Repositories (`backend/db/clients_repository.py`)

- Update `create_client(...)` to accept `password_hash: str` and persist it.
- Update `get_client_by_phone(...)` (or create `get_client_auth_by_phone(...)`) to retrieve `password_hash` for password comparison.

#### 3. Backend Auth Module (`backend/auth.py` — New File)

- **Hashing Utilities:** Implement `hash_password(password: str) -> str` and `verify_password(plain: str, hashed: str) -> bool` using `bcrypt`.
- **JWT Utilities:** Implement `create_access_token(data: dict, expires_delta: Optional[timedelta]) -> str` and `decode_access_token(token: str) -> dict` using `PyJWT` (algorithm `HS256`, 24-hour default expiration).
- **FastAPI Auth Dependencies:**
  - `get_current_user_jwt(token: str = Depends(oauth2_scheme)) -> dict`: Enforces valid Bearer JWT on live endpoints (`/chat`, `/api/client/*`), extracting `user_id`.
  - `get_test_user_basic(credentials: HTTPBasicCredentials = Depends(security)) -> dict`: Enforces valid HTTP Basic Auth on testing endpoints (`/api/v1/tests/*`), extracting `user_id`.

#### 4. Dependencies & Configuration (`backend/requirements.txt`, `backend/config.py`)

- Add `pyjwt` and `bcrypt` to `backend/requirements.txt`.
- Add `JWT_SECRET_KEY`, `JWT_ALGORITHM`, and `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` to `backend/config.py` and `.env`.

#### 5. Backend Models & API Routes (`backend/models.py`, `backend/bootstrap.py`)

- **Models:**
  - `LoginRequest`: Require `phone: str` and `password: str`.
  - `RegisterRequest`: Add `password: str`.
  - `TokenResponse`: Define `{ access_token: str, token_type: "bearer", client: dict }`.
  - `ChatRequest`: Remove `user_id` field.
- **Routes:**
  - `POST /api/login`: Validate credentials against `password_hash`, issue JWT token in `TokenResponse`.
  - `POST /api/register`: Hash password, create client record, issue JWT token in `TokenResponse`.
  - `POST /chat`: Inject `current_user = Depends(get_current_user_jwt)`. Set `state.user_id = current_user["id"]`.
  - `GET/PUT /api/client/{client_id}/*`: Protect with `Depends(get_current_user_jwt)`, ensuring callers can only query their own records.

#### 6. Frontend Application Updates (`frontend/src/App.jsx`)

- **Token State:** Store JWT `token` in React state and synchronize with `localStorage.getItem('auth_token')` / `localStorage.setItem('auth_token', token)`.
- **Form Inputs:**
  - Add password input field to Login modal/form bound to `loginPassword`.
  - Add password input field to Register modal/form bound to `regData.password`.
- **Authenticated Requests:**
  - Attach `Authorization: Bearer ${token}` header to all real API calls:
    - `/chat`
    - `/api/client/${id}/projects`
    - `/api/client/${id}/conversations`
    - `/api/client/${id}`
  - Remove `user_id` from the `/chat` JSON request body payload.
  - Add 401 response handling to automatically clear stored token and show login dialog on expiration.
- **Logout:** Clear `token` from `localStorage` and reset React client state.

---

## 6. Tool Safety & Database Isolation

Tools like `save_project_and_tenders` and `fetch_available_categories` can fail during testing if:

1. Client intake information (`name`, `phone`, `address`) is absent or the client ID is invalid.
2. Database writes pollute the development or production project tables.

### Mitigation Strategies in the Testing Harness:

1. **`dry_run: true` (Default)**:
   - When `dry_run` is active, database insertion functions (`create_project`, `create_project_prompt`, `save_conversation`) are intercepted by an in-memory stub that generates a mock ID (e.g. `project_id: 9999`) and logs the payload without writing to SQLite/SQL Server.
2. **Dedicated Test Database with Real Client Records (No Mock Fallbacks)**:
   - The test harness runs against a dedicated test database populated with real test client records.
   - The system strictly loads `client_info` from `dbo.Clients` using `simulated_user_id`.
   - If `simulated_user_id` does not exist in the database, the request fails with `404 Not Found`. Mock client dictionaries are never accepted or used.
3. **Category Fallbacks**:
   - If `fetch_available_categories` cannot reach the database, it falls back to a built-in static category listing.

---

## 7. Observability & State Inspection Patterns

### 7.1 State Mutation Delta (`turn_summary.updated_fields`)

Rather than maintaining rigid server-side assertion rules, the endpoint calculates the delta between the input state and the mutated state after `engine.process(state)`.

Any field on the state that was added, modified, or populated during this single turn is extracted into `turn_summary.updated_fields`:
- `CategorizerDecision`: Populated when the categorizer determines single vs. multiple tasks.
- `confirmed_job_description`: Populated when the agent synthesizes the customer's requirements.
- `is_finished`: Set to `true` when the agent completes all conversational stages.
- `next_step`: Updated to reflect which agent/node runs next.
- `identified_categories`: Populated when matching categories are identified.
- `prompts`: Updated when category prompts are generated.
- `collected_details`: Updated when client provides task specifications.
- `project_id`: Updated when project record is created/stubbed.

This provides instant, at-a-glance visibility into the model's trajectory and state progression without having to hunt through complete state trees.

### 7.2 Postman Test Script Template (JavaScript)

Developers can paste the following snippet into the **Tests** tab of Postman requests:

```javascript
// Parse response
const res = pm.response.json();
pm.test("HTTP Status is 200", () => pm.response.to.have.status(200));
pm.test("Turn executed successfully", () => pm.expect(res.success).to.be.true);

// 1. Inspect Latest Assistant Message & Direction
pm.test("Agent produced response message", () => {
    pm.expect(res.turn_summary.latest_message).to.not.be.null;
    pm.expect(res.turn_summary.latest_message.role).to.eql("assistant");
    pm.expect(res.turn_summary.latest_message.content).to.be.a("string").and.not.empty;
});

// 2. Inspect Mutated State Fields (updated_fields)
pm.test("State updates detected", () => {
    const updated = res.turn_summary.updated_fields;
    pm.expect(updated).to.be.an("object");

    // Example: verify categorizer decision if mutated in this turn
    if (updated.CategorizerDecision) {
        pm.expect(updated.CategorizerDecision.decision).to.be.oneOf(["single", "multiple"]);
    }
});
```

---

## 8. Implementation Roadmap

### Step 1: Database Password Hashing & Backend JWT Infrastructure

- Add `password_hash` column to `dbo.Clients` and update `backend/db/clients_repository.py`.
- Add `pyjwt` and `bcrypt` to `backend/requirements.txt` and configure JWT settings in `backend/config.py`.
- Implement `backend/auth.py` with password hashing, JWT encoding/decoding, and FastAPI dependencies (`get_current_user_jwt` and `get_test_user_basic`).
- Update `/api/login` and `/api/register` to issue JWT `TokenResponse`.
- Update `/chat` to use `Depends(get_current_user_jwt)` and remove `user_id` from `ChatRequest`.
- Update frontend `App.jsx` to store JWT in `localStorage`, send `Authorization: Bearer <token>`, add password input, and remove `user_id` from `/chat` body.

### Step 2: Pydantic Request & Response Models for Testing (`backend/models.py`)

- Define `StateTestMessage`, `StateTestOptions`, `StateTestRequest`, `StateTestResponse`.
- Define `BatchTestCase`, `BatchTestRequest`, `BatchTestResponse`.
- Add mandatory `simulated_user_id: int` to `StateTestRequest` and `BatchTestCase`.
- Ensure raw `user_id` inside `AgentState` is excluded from request payloads.

### Step 3: Engine Dry Run & Tool Isolation (`backend/v1/engine.py` & `backend/v2/engine.py`)

- Add `dry_run: bool = False` argument to `Engine.process(state, dry_run=False)`.
- Ensure tool calls in `v2/engine.py` honor `dry_run` and don't insert database rows when flag is active.
- Ensure all message types (`user`, `assistant`, `system`, `tool`) are round-tripped cleanly.

### Step 4: Implement Testing Endpoints (`backend/v1/routes/testing.py`)

- Implement `POST /api/v1/tests/process-state` protected by `get_test_user_basic` (HTTP Basic Auth).
  - Validate that `simulated_user_id` exists in `dbo.Clients` (404 error if not found; no fallback).
  - Auto-populate `state.client_info` from the database record and inject `state.user_id`.
- Implement `POST /api/v1/tests/process-batch` protected by `get_test_user_basic` with `asyncio.Semaphore` and `asyncio.to_thread`.
  - Validate each test case's `simulated_user_id` against `dbo.Clients`.
- Implement state delta extractor helper to compute `turn_summary.updated_fields`.

### Step 5: Verification with Postman & Pytest

- Generate Postman Collection JSON export with HTTP Basic Auth configured for test endpoints.
- Run automated tests against the new endpoints via `pytest backend/tests/api/test_testing_endpoints.py`.
