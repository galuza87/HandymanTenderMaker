"""Backward-compatible re-export of the version-agnostic test_evaluator service."""

from backend.services.test_evaluator import (  # noqa: F401
    DOCUMENT_SAVE_TOOLS,
    HITL_DRAFT_MARKERS,
    build_turn_summary,
    classify_outcome,
    compute_updated_fields,
    evaluate_outcome,
    extract_tool_calls,
    is_hitl_draft_message,
)
