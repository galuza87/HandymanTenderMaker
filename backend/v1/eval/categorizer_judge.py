import os
import random
import threading

from langsmith.run_helpers import get_current_run_tree

from backend.v1.eval.eval_core import format_conversation, judge_and_route
from backend.v1.tools import fetch_available_categories

# Sample rate and queue IDs are read from the environment rather than
# hardcoded, so they can be set (or left unset, during initial rollout)
# per environment without a code change. A missing queue ID isn't an
# error -- judge_and_route() treats None as "skip queue routing, still
# record feedback" -- so this node can be judged before its queues exist.
SAMPLE_RATE = float(os.environ.get("CONTRACTOR_CATEGORIZER_SAMPLE_RATE", "1.0"))
GOOD_QUEUE_ID = os.environ.get("CONTRACTOR_CATEGORIZER_GOOD_QUEUE_ID")
CORRECTION_QUEUE_ID = os.environ.get("CONTRACTOR_CATEGORIZER_CORRECTION_QUEUE_ID")
FEEDBACK_KEY = "contractor_categorizer_correctness"

SYSTEM_PROMPT = """You audit a "ContractorCategorizer" node in a handyman-job intake chatbot.
The node identifies a single category_id it believes matches the user's request. You are
given the list of available categories (ID, name, description) as context -- use it to
verify the assigned category_id genuinely matches the trade or service the conversation
describes, not just that some category was assigned.

If the request is still ambiguous about which single category fits, that would also be an
incorrect call, regardless of which ID was chosen.

Respond with strict JSON only: {"correct": true or false, "reasoning": "<one sentence>"}"""

# Cached at module level -- categories rarely change, and this is a DB
# call, so there's no reason to hit the DB on every single judge call.
# A process restart picks up any changes; that's an acceptable staleness
# window for a toy project.
_categories_context: str | None = None


def _get_categories_context() -> str:
    """Expects: nothing. Modifies: caches category context. Returns: context text or empty string."""
    global _categories_context
    if _categories_context is None:
        try:
            _categories_context = "Available categories:\n" + fetch_available_categories.invoke({})
        except Exception as e:
            print(f"[online eval] fetch_available_categories failed: {e}")
            _categories_context = ""
    return _categories_context or ""


def _error_prefix_present(messages: list) -> bool:
    """Expects: message list. Modifies: nothing. Returns: whether the last message is the node error prefix."""
    if not messages:
        return False
    last = messages[-1]
    content = last.get("content") if isinstance(last, dict) else getattr(last, "content", "")
    return isinstance(content, str) and content.startswith("ContractorCategorizer error:")


def extract_status_from_run(run) -> str | None:
    """Expects: a LangSmith run. Modifies: nothing. Returns: final category ID or None."""
    messages = run.outputs.get("messages", [])
    if _error_prefix_present(messages):
        return None
    if run.outputs.get("next_agent") != "IntakeCoordinator":
        return None
    identified = run.outputs.get("identified_categories") or []
    if not identified:
        return None
    return str(identified[-1].get("category_id"))


def maybe_evaluate_async(messages: list, category_id: int | None, session_id: str | None = None) -> None:
    """Expects: messages, category ID, and optional node session ID. Modifies: starts a background judge when sampling allows it. Returns: None."""
    if category_id is None or random.random() > SAMPLE_RATE:
        return

    run = get_current_run_tree()
    if run is None:
        return

    effective_session_id = session_id or getattr(run, "session_id", None)
    conversation_text = format_conversation(messages)

    threading.Thread(
        target=judge_and_route,
        args=(
            conversation_text, str(category_id), run.id, effective_session_id, run.trace_id,
            SYSTEM_PROMPT, FEEDBACK_KEY, GOOD_QUEUE_ID, CORRECTION_QUEUE_ID,
        ),
        kwargs={"extra_context": _get_categories_context()},
        daemon=True,
    ).start()