import os
import random
import threading

from langsmith.run_helpers import get_current_run_tree

from backend.v1.eval.eval_core import format_conversation, judge_and_route

SAMPLE_RATE = float(os.environ.get("DATA_VALIDATOR_SAMPLE_RATE", "1.0"))
GOOD_QUEUE_ID = os.environ.get("DATA_VALIDATOR_GOOD_QUEUE_ID")
CORRECTION_QUEUE_ID = os.environ.get("DATA_VALIDATOR_CORRECTION_QUEUE_ID")
FEEDBACK_KEY = "data_validator_correctness"

SYSTEM_PROMPT = """You audit a "DataValidator" node in a handyman-job intake chatbot.
Decide whether its decision was correct given the conversation so far.

The node should judge "not enough information" if the request is a bare greeting, too vague
to identify a trade, or clearly hides an unstated second trade (e.g. asks for a tiler but
describes a leak). Otherwise it should judge "enough information".

Respond with strict JSON only: {"correct": true or false, "reasoning": "<one sentence>"}"""


def extract_status_from_run(run) -> str:
    """Expects: a LangSmith run. Modifies: nothing. Returns: status text."""
    decided_not_enough_info = run.outputs.get("next_agent") == "DataValidator"
    return "not enough information" if decided_not_enough_info else "enough information"


def maybe_evaluate_async(messages: list, status: str, session_id: str | None = None) -> None:
    """Expects: messages, status, and optional node session ID. Modifies: starts a background judge when sampling allows it. Returns: None."""
    if random.random() > SAMPLE_RATE:
        return

    run = get_current_run_tree()
    if run is None:
        return

    effective_session_id = session_id or getattr(run, "session_id", None)
    conversation_text = format_conversation(messages)

    threading.Thread(
        target=judge_and_route,
        args=(
            conversation_text, status, run.id, effective_session_id, run.trace_id,
            SYSTEM_PROMPT, FEEDBACK_KEY, GOOD_QUEUE_ID, CORRECTION_QUEUE_ID,
        ),
        daemon=True,
    ).start()