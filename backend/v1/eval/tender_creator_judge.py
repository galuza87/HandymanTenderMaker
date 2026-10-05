import os
import random
import threading

from langsmith.run_helpers import get_current_run_tree

from backend.v1.eval.eval_core import format_conversation, judge_and_route

# Sample rate and queue IDs are read from the environment rather than
# hardcoded, so they can be set (or left unset, during initial rollout)
# per environment without a code change. A missing queue ID isn't an
# error -- judge_and_route() treats None as "skip queue routing, still
# record feedback" -- so this node can be judged before its queues exist.
SAMPLE_RATE = float(os.environ.get("TENDER_CREATOR_SAMPLE_RATE", "1.0"))
GOOD_QUEUE_ID = os.environ.get("TENDER_CREATOR_GOOD_QUEUE_ID")
CORRECTION_QUEUE_ID = os.environ.get("TENDER_CREATOR_CORRECTION_QUEUE_ID")
FEEDBACK_KEY = "tender_creator_quality"

SYSTEM_PROMPT = """You audit a "TenderCreator" node in a handyman-job intake chatbot.
The node finalizes a professional tender (job description) shown to contractors, based on
the conversation history.

Judge the tender good only if it is clear, complete (covers the scope of work discussed,
without inventing details not implied by the conversation), and written in a professional
tone with no leftover greetings or chatbot-style phrasing.

Respond with strict JSON only: {"correct": true or false, "reasoning": "<one sentence>"}"""


def extract_status_from_run(run) -> str | None:
    """Expects: a LangSmith run. Modifies: nothing. Returns: confirmed tender text or None."""
    try:
        inputs = run.inputs or {}
        return inputs.get("confirmed_job_description") or inputs.get("state", {}).get("confirmed_job_description")
    except Exception:
        return None


def maybe_evaluate_async(messages: list, tender_text: str, session_id: str | None = None) -> None:
    """Expects: messages, tender text, and optional node session ID. Modifies: starts background judge when sampling allows it. Returns: None."""
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
            conversation_text, tender_text, run.id, effective_session_id, run.trace_id,
            SYSTEM_PROMPT, FEEDBACK_KEY, GOOD_QUEUE_ID, CORRECTION_QUEUE_ID,
        ),
        daemon=True,
    ).start()