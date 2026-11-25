from pydantic import BaseModel, model_validator
from typing import List, Dict, Optional, Any, Literal

# --- Classes                      ---
class CategorizerDecisionClass(BaseModel):
    decision: Literal["single", "multiple"]

class ChatRequest(BaseModel):
    message: str
    session_id: str
    user_id: Optional[int] = None
    image: Optional[str] = None

class LoginRequest(BaseModel):
    phone: str

class RegisterRequest(BaseModel):
    phone: str
    name: str
    last_name: str
    email: str
    address: str
    additional_phone: Optional[str] = None

class UpdateClientRequest(BaseModel):
    name: str
    last_name: str
    email: str
    address: str
    additional_phone: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    identified_categories: List[Dict[str, Any]] = []
    prompts: List[Dict[str, Any]] = []
    collected_details: Dict[str, str] = {}

# Graph State
class AgentState(BaseModel):
    messages: List[Dict[str, Any]]
    session_id: Optional[str] = None
    user_id: Optional[int] = None
    identified_categories: List[Dict[str, Any]] = []
    prompts: List[Dict[str, Any]] = []
    collected_details: Dict[str, str] = {}
    client_info: Dict[str, str] = {}
    confirmed_job_description: Optional[str] = None
    next_step: str = "determine_number_of_subtasks"
    ip_address: Optional[str] = None
    CategorizerDecision: Optional[CategorizerDecisionClass] = None
    project_id: Optional[int] = None
    is_finished: bool = False
    open_topics: List[str] = []
    has_fetched_past_feedback: bool = False


# --- Version-Agnostic Agent Testing Endpoint Models ---
OutcomeType = Literal[
    "generate_document",
    "request_hitl",
    "tool_use",
    "ask_additional_info",
]


class ExpectedToolCall(BaseModel):
    """Expected tool call assertion for a single turn."""
    name: str
    args_subset: Optional[Dict[str, Any]] = None


class ExpectedOutcome(BaseModel):
    """Action-focused gold standard assertion for a test turn.

    Evaluates only the action/step taken by the agent (outcome_type, tool calls,
    and optional state fields) rather than free-text wording.
    """
    outcome_type: OutcomeType
    expected_tools: Optional[List[ExpectedToolCall]] = None
    expected_state_fields: Optional[Dict[str, Any]] = None


class StateTestOptions(BaseModel):
    """Execution options for a single state test turn."""
    dry_run: bool = True
    algorithm_version: Optional[str] = None


class StateTestRequest(BaseModel):
    """Version-agnostic request payload for POST /api/{version}/tests/process-state.

    Client identification is performed via request headers (`jwt` / `Authorization`
    paired with `X-Test-Api-Key` in test mode, or a signed JWT in normal mode),
    so the body only requires conversation `messages`:
        {
          "messages": [{"role": "user", "content": "hello"}],
          "expected_step": "ask_additional_info"
        }
    """
    test_id: Optional[str] = None
    client_id: Optional[int] = None
    messages: Optional[List[Dict[str, Any]]] = None
    expected_step: Optional[OutcomeType] = None
    expected_tools: Optional[List[ExpectedToolCall]] = None
    dry_run: Optional[bool] = None
    session_id: Optional[str] = None

    # Optional backward-compatible nested fields
    state: Optional[AgentState] = None
    expected_outcome: Optional[ExpectedOutcome] = None
    options: Optional[StateTestOptions] = None

    @model_validator(mode="after")
    def validate_conversation_input(self) -> "StateTestRequest":
        """Ensure either flat `messages` or nested `state` is provided."""
        if self.messages is None and self.state is None:
            raise ValueError("Provide conversation 'messages' (or 'state.messages') in the request.")
        return self

    def resolve_state(self) -> AgentState:
        """Build an AgentState from flat `messages` or return a deep copy of `state`."""
        if self.state is not None:
            resolved = self.state.model_copy(deep=True)
            if self.messages is not None:
                resolved.messages = list(self.messages)
            if self.session_id is not None:
                resolved.session_id = self.session_id
            return resolved
        return AgentState(
            messages=list(self.messages or []),
            session_id=self.session_id or self.test_id or "test-session",
        )

    def resolve_expected_outcome(self) -> Optional[ExpectedOutcome]:
        """Resolve flat `expected_step` / `expected_tools` or nested `expected_outcome`."""
        if self.expected_outcome is not None:
            return self.expected_outcome
        if self.expected_step is not None:
            return ExpectedOutcome(
                outcome_type=self.expected_step,
                expected_tools=self.expected_tools,
            )
        return None

    def resolve_dry_run(self) -> bool:
        """Return the effective dry_run flag (defaults to True)."""
        if self.dry_run is not None:
            return self.dry_run
        if self.options is not None:
            return self.options.dry_run
        return True


class EvaluationResult(BaseModel):
    """Comparison result between ExpectedOutcome and actual turn behavior."""
    passed: bool
    expected_outcome_type: OutcomeType
    actual_outcome_type: OutcomeType
    mismatches: List[str] = []


class TurnSummary(BaseModel):
    """Extracted summary of actions, tool calls, and state changes during a single turn."""
    detected_outcome_type: OutcomeType
    new_messages: List[Dict[str, Any]] = []
    latest_message: Optional[Dict[str, Any]] = None
    tool_calls_made: List[Dict[str, Any]] = []
    updated_fields: Dict[str, Any] = {}


class StateTestResponse(BaseModel):
    """Version-agnostic response payload for POST /api/{version}/tests/process-state."""
    test_id: Optional[str] = None
    version: str = "v1"
    client_id: int
    step: OutcomeType
    expected_step: Optional[OutcomeType] = None
    is_step_correct: Optional[bool] = None
    success: bool
    reply: Optional[str] = None
    execution_time_ms: float
    messages: List[Dict[str, Any]] = []
    turn_summary: TurnSummary
    evaluation: Optional[EvaluationResult] = None
    state: AgentState


class BatchTestJobRequest(BaseModel):
    """Request payload for POST /api/{version}/tests/jobs.

    Can run many concurrent requests at once by:
    1. Loading single test case files from `backend/tests/agent_cases/` (all of them,
       or filtered by `test_cases`) and repeating them up to `total_requests`.
    2. Repeating an inline single conversation (`messages` + `expected_step`) `total_requests` times.
    3. Executing an explicit `requests` list.
    """
    job_name: Optional[str] = None
    concurrency: int = 1
    total_requests: Optional[int] = None
    fail_fast: bool = False
    test_cases: Optional[List[str]] = None
    messages: Optional[List[Dict[str, Any]]] = None
    expected_step: Optional[OutcomeType] = None
    expected_tools: Optional[List[ExpectedToolCall]] = None
    requests: Optional[List[StateTestRequest]] = None


class BatchTestJobResponse(BaseModel):
    """Summary response for POST /api/{version}/tests/jobs and GET /api/{version}/tests/jobs/{job_id}."""
    job_id: str
    job_name: Optional[str] = None
    version: Optional[str] = None
    status: Literal["PASSED", "FAILED"]
    total_requests: int
    passed: int
    failed: int
    concurrency: int
    total_execution_time_ms: float
    avg_execution_time_ms: float
    status_code_breakdown: Dict[str, int] = {}
    job_dir: str
    results: List[Dict[str, Any]] = []
    failed_requests: List[Dict[str, Any]] = []
