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
SAMPLE_RATE = float(os.environ.get("MULTI_TASK_ARCHITECT_SAMPLE_RATE", "1.0"))
GOOD_QUEUE_ID = os.environ.get("MULTI_TASK_ARCHITECT_GOOD_QUEUE_ID")
CORRECTION_QUEUE_ID = os.environ.get("MULTI_TASK_ARCHITECT_CORRECTION_QUEUE_ID")
FEEDBACK_KEY = "multi_task_architect_correctness"

SYSTEM_PROMPT = """You audit a "MultiTaskArchitect" node in a handyman-job intake chatbot.
The node breaks a multi-trade request into a JSON list of sub-tasks, each with a
description and a category_id. You are given the list of available categories (ID, name,
description) as context -- use it to check both that each sub-task's category_id genuinely
matches its description, and that the set of sub-task descriptions reasonably and
completely covers the work described in the conversation (no obviously missing trade, no
invented work not implied by the conversation, no single job split into unnecessary
duplicate sub-tasks).

Respond with strict JSON only: {"correct": true or false, "reasoning": "<one sentence>"}"""

# Cached at module level -- categories rarely change, and this is a DB
# call, so there's no reason to hit the DB on every single judge call.
_categories_context: str | None = None


def _get_categories_context() -> str:
    """Expects: nothing. Modifies: caches category text once. Returns: category context string."""
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
    return isinstance(content, str) and content.startswith("MultiTaskArchitect error:")


def extract_status_from_run(run) -> str | None:
    """Expects: a LangSmith run. Modifies: nothing. Returns: decision text or None."""
    messages = run.outputs.get("messages", [])
    if _error_prefix_present(messages):
        return None
    if run.outputs.get("next_agent") != "IntakeCoordinator":
        return None
    decision_text = run.outputs.get("multi_task_decision")
    return decision_text if isinstance(decision_text, str) and decision_text.strip() else None


def maybe_evaluate_async(messages: list, decision_text: str, session_id: str | None = None) -> None:
    """Expects: messages, decision text, and optional node session ID. Modifies: starts a background judge when sampling allows it. Returns: None."""
    if not decision_text.strip() or random.random() > SAMPLE_RATE:
        return

    run = get_current_run_tree()
    if run is None:
        return

    effective_session_id = session_id or getattr(run, "session_id", None)
    conversation_text = format_conversation(messages)

    threading.Thread(
        target=judge_and_route,
        args=(
            conversation_text, decision_text, run.id, effective_session_id, run.trace_id,
            SYSTEM_PROMPT, FEEDBACK_KEY, GOOD_QUEUE_ID, CORRECTION_QUEUE_ID,
        ),
        kwargs={"extra_context": _get_categories_context()},
        daemon=True,
    ).start()