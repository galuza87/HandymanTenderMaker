"""Action-based outcome classifier and gold-standard evaluator for agent testing.

This module inspects the state before and after an engine turn and evaluates
ONLY the actions taken by the agent:
  1. Primary outcome type (`generate_document`, `request_hitl`, `tool_use`, `ask_additional_info`)
  2. Tool calls invoked (`expected_tools` with optional `args_subset`)
  3. Node and state transitions (`expected_state_fields`, e.g. `next_step`, `CategorizerDecision`, `is_finished`)
"""

from typing import Any, Dict, List, Optional

from backend.models import (
    AgentState,
    EvaluationResult,
    ExpectedOutcome,
    ExpectedToolCall,
    OutcomeType,
    TurnSummary,
)

DOCUMENT_SAVE_TOOLS = {"save_project_and_tenders", "confirm_and_save_document"}


def extract_tool_calls(new_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract a normalized list of tool calls (`name` and `args`) from new turn messages."""
    extracted: List[Dict[str, Any]] = []
    for msg in new_messages:
        if msg.get("role") != "assistant":
            continue
        raw_calls = msg.get("tool_calls") or []
        for call in raw_calls:
            extracted.append({
                "name": call.get("name", ""),
                "args": call.get("args", {}) or {},
            })
    return extracted


def compute_updated_fields(
    state_before: AgentState,
    state_after: AgentState,
) -> Dict[str, Any]:
    """Return a dictionary of top-level AgentState fields (excluding messages) that changed."""
    before_dict = state_before.model_dump(exclude={"messages"})
    after_dict = state_after.model_dump(exclude={"messages"})
    updated: Dict[str, Any] = {}
    for key, after_val in after_dict.items():
        if before_dict.get(key) != after_val:
            updated[key] = after_val
    return updated


def _is_document_generated(
    state_before: AgentState,
    state_after: AgentState,
    tool_names: set[str],
) -> bool:
    """Return True if the turn generated or confirmed a final project/tender document."""
    if bool(tool_names & DOCUMENT_SAVE_TOOLS):
        return True
    if not state_before.is_finished and state_after.is_finished:
        return True
    if state_after.confirmed_job_description and (
        state_after.confirmed_job_description != state_before.confirmed_job_description
    ):
        return True
    if state_after.next_step == "TenderCreator" and state_before.next_step != "TenderCreator":
        return True
    return False


def _is_requesting_hitl(
    state_before: AgentState,
    state_after: AgentState,
    tool_names: set[str],
) -> bool:
    """Return True if the agent is pausing at IntakeCoordinator for human confirmation of a draft."""
    if state_after.is_finished or state_after.confirmed_job_description:
        return False
    if state_after.next_step != "IntakeCoordinator":
        return False
    if state_after.open_topics:
        return False
    if not tool_names and state_before.next_step == "IntakeCoordinator":
        return True
    return False


def classify_outcome(
    state_before: AgentState,
    state_after: AgentState,
    tool_calls_made: List[Dict[str, Any]],
) -> OutcomeType:
    """Classify the primary action taken by the agent during this turn."""
    tool_names = {call.get("name", "") for call in tool_calls_made}

    if _is_document_generated(state_before, state_after, tool_names):
        return "generate_document"

    if _is_requesting_hitl(state_before, state_after, tool_names):
        return "request_hitl"

    if tool_calls_made:
        return "tool_use"

    return "ask_additional_info"


def build_turn_summary(
    state_before: AgentState,
    state_after: AgentState,
) -> TurnSummary:
    """Construct the TurnSummary comparing state_before and state_after."""
    old_count = len(state_before.messages)
    new_messages = state_after.messages[old_count:]
    tool_calls_made = extract_tool_calls(new_messages)
    updated_fields = compute_updated_fields(state_before, state_after)
    detected_outcome = classify_outcome(state_before, state_after, tool_calls_made)

    latest_message: Optional[Dict[str, Any]] = None
    if new_messages:
        last = new_messages[-1]
        latest_message = {
            "role": str(last.get("role", "assistant")),
            "content": str(last.get("content", "")),
        }

    return TurnSummary(
        detected_outcome_type=detected_outcome,
        new_messages=new_messages,
        latest_message=latest_message,
        tool_calls_made=tool_calls_made,
        updated_fields=updated_fields,
    )


def _matches_args_subset(
    expected_subset: Dict[str, Any],
    actual_args: Dict[str, Any],
) -> bool:
    """Return True if every key/value in expected_subset matches actual_args."""
    for key, expected_val in expected_subset.items():
        if key not in actual_args or actual_args[key] != expected_val:
            return False
    return True


def _check_expected_tools(
    expected_tools: List[ExpectedToolCall],
    actual_tools: List[Dict[str, Any]],
) -> List[str]:
    """Verify that all expected tool calls and argument subsets were invoked."""
    mismatches: List[str] = []
    for exp_tool in expected_tools:
        matching_name_calls = [
            call for call in actual_tools if call.get("name") == exp_tool.name
        ]
        if not matching_name_calls:
            mismatches.append(f"Expected tool '{exp_tool.name}' was not called.")
            continue

        if exp_tool.args_subset:
            matched_args = any(
                _matches_args_subset(exp_tool.args_subset, call.get("args", {}))
                for call in matching_name_calls
            )
            if not matched_args:
                mismatches.append(
                    f"Tool '{exp_tool.name}' was called, but arguments did not match subset {exp_tool.args_subset}."
                )
    return mismatches


def _check_expected_state_fields(
    expected_fields: Dict[str, Any],
    state_after: AgentState,
) -> List[str]:
    """Verify that expected node transitions and state fields match state_after."""
    mismatches: List[str] = []
    after_dict = state_after.model_dump()
    for field_name, expected_val in expected_fields.items():
        actual_val = after_dict.get(field_name)
        if actual_val != expected_val:
            mismatches.append(
                f"State field '{field_name}' mismatch: expected {expected_val!r}, got {actual_val!r}."
            )
    return mismatches


def evaluate_outcome(
    expected: ExpectedOutcome,
    state_before: AgentState,
    state_after: AgentState,
    turn_summary: TurnSummary,
) -> EvaluationResult:
    """Evaluate actual agent actions, tool calls, and node transitions against ExpectedOutcome."""
    mismatches: List[str] = []
    actual_outcome = turn_summary.detected_outcome_type

    if actual_outcome != expected.outcome_type:
        mismatches.append(
            f"Outcome type mismatch: expected '{expected.outcome_type}', got '{actual_outcome}'."
        )

    if expected.expected_tools:
        mismatches.extend(
            _check_expected_tools(expected.expected_tools, turn_summary.tool_calls_made)
        )

    if expected.expected_state_fields:
        mismatches.extend(
            _check_expected_state_fields(expected.expected_state_fields, state_after)
        )

    return EvaluationResult(
        passed=len(mismatches) == 0,
        expected_outcome_type=expected.outcome_type,
        actual_outcome_type=actual_outcome,
        mismatches=mismatches,
    )
