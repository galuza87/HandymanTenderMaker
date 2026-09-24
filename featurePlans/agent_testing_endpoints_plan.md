# Feature Plan: Agent Testing Endpoints

## Objective
To create dedicated testing endpoints that allow developers to send complete conversation states (`AgentState`) via Postman (or automated tests), process them using the AI engine, and receive the mutated state back. This includes both a standard synchronous REST endpoint and a real-time Server-Sent Events (SSE) streaming endpoint.

## 1. REST Endpoint: Synchronous State Processing
**Path:** `POST /api/v1/tests/process-state`

### Purpose
Ideal for automated testing and quick validation in Postman. Allows developers to assert final states (e.g., verifying that the agent successfully assigned the correct `category_id` based on the conversation history).

### Behavior
- **Input:** Accepts an entire `AgentState` object as JSON in the request body.
- **Action:**
  - Deserializes the payload into an `AgentState` object.
  - Passes the state synchronously to `engine.process(state)`.
  - Optionally bypasses database saves to avoid polluting the database with test runs.
- **Output:** Returns the final, mutated `AgentState` JSON block (including the newly appended assistant messages and extracted data).

## 2. SSE Endpoint: Real-time State Streaming
**Path:** `POST /api/v1/tests/stream-state`

### Purpose
Ideal for testing the exact user experience (UX) that the frontend will implement, such as real-time "typing" effects and exposing intermediate agent actions (e.g., tool calls). Postman natively supports connecting to SSE endpoints.

### Behavior
- **Input:** Accepts an entire `AgentState` object as JSON in the request body.
- **Action:** 
  - Deserializes the payload into an `AgentState`.
  - Invokes a new asynchronous generator method: `engine.process_stream(state)`.
  - Uses FastAPI's `StreamingResponse` (with `media_type="text/event-stream"`).
- **Output:** Yields a continuous stream of events. Example event formats:
  ```json
  {"event": "token", "data": "Hello"}
  {"event": "tool_call", "data": "fetch_available_categories"}
  {"event": "final_state", "data": { "... full AgentState ..." }}
  ```

## 3. Core Engine Modifications (`backend/v2/engine.py` or `backend/v1/engine.py`)

### Update `process(state)`
- Ensure the method safely handles injected states without strictly requiring predefined database rows (or provide a safe "dry run" mode if DB saves are usually enforced).

### Implement `async process_stream(state)`
- Add an `async def process_stream(self, state: AgentState)` generator method.
- Leverage Langchain's native async streaming (`.astream()` or `.astream_events()`).
- Parse the Langchain event stream and yield formatted JSON strings compatible with the SSE protocol.

## Next Steps for Execution
1. Update `backend/models.py` if any new Pydantic wrappers are needed for the requests.
2. Update the `Engine` class to implement the `process_stream()` method.
3. Create the new routes in `backend/v1/routes/testing.py`.
4. Run the Uvicorn server and test both endpoints via Postman.
