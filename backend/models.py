from pydantic import BaseModel
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
    identified_categories: List[Dict[str, Any]] = [] # e.g., [{"category_id": 1, "name": "plumbing"}]
    prompts: List[Dict[str, Any]] = [] # e.g., [{"id": 1, "category": "plumbing", "prompt_text": "fix pipe"}]
    collected_details: Dict[str, str] = {}
    client_info: Dict[str, str] = {}
    confirmed_job_description: Optional[str] = None
    next_step: str = "determine_number_of_subtasks" # Start at determine_number_of_subtasks
    ip_address: Optional[str] = None
    CategorizerDecision: Optional[CategorizerDecisionClass] = None
    project_id: Optional[int] = None
    is_finished: bool = False
    open_topics: List[str] = []
    has_fetched_past_feedback: bool = False


# --- Agent Testing Endpoint Models ---
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

    Evaluates only the action taken by the agent (outcome_type, tool calls,
    and node/state transitions) rather than free-text wording.
    """
    outcome_type: OutcomeType
    expected_tools: Optional[List[ExpectedToolCall]] = None
    expected_state_fields: Optional[Dict[str, Any]] = None


class StateTestOptions(BaseModel):
    """Execution options for a single state test turn."""
    dry_run: bool = True
    algorithm_version: Optional[str] = None
    timeout_seconds: Optional[float] = None


class StateTestRequest(BaseModel):
    """Request payload for POST /api/v1/tests/process-state."""
    test_id: Optional[str] = None
    simulated_user_id: int
    state: AgentState
    expected_outcome: Optional[ExpectedOutcome] = None
    options: Optional[StateTestOptions] = None


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
    """Response payload for POST /api/v1/tests/process-state."""
    test_id: Optional[str] = None
    success: bool
    execution_time_ms: float
    state: AgentState
    turn_summary: TurnSummary
    evaluation: Optional[EvaluationResult] = None


class BatchTestJobRequest(BaseModel):
    """Request payload for POST /api/v1/tests/jobs."""
    job_name: Optional[str] = None
    concurrency: int = 1
    fail_fast: bool = False
    requests: List[StateTestRequest]


class BatchTestJobResponse(BaseModel):
    """Summary response for POST /api/v1/tests/jobs and GET /api/v1/tests/jobs/{job_id}."""
    job_id: str
    job_name: Optional[str] = None
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
