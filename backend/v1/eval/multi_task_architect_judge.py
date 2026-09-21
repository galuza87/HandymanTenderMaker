"""Node-specific judge config and the inline (live-traffic) trigger for
MultiTaskArchitect.

The judge is given the same category_id -> name/description mapping as
contractor_categorizer_judge.py (fetched once via
`fetch_available_categories`, cached for the process lifetime), so it
can check each sub-task's category_id against a real name, not just
assess whether the sub-task descriptions sound reasonable in isolation.
"""

import json
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
    """Fetch (and cache) the category list as context text for the judge prompt.

    Degrades gracefully on failure -- if the DB call fails, the judge
    falls back to reasoning from the conversation and sub-task
    descriptions alone, rather than blocking evaluation entirely over a
    categories-lookup failure.

    Returns:
        A formatted "Available categories:\n..." string, or an empty
        string if the lookup failed.
    """
    global _categories_context
    if _categories_context is None:
        try:
            _categories_context = "Available categories:\n" + fetch_available_categories.invoke({})
        except Exception as e:
            print(f"[online eval] fetch_available_categories failed: {e}")
            _categories_context = ""
    return _categories_context or ""


def _error_prefix_present(messages: list) -> bool:
    """Check for this node's own error-fallback text in the transcript.

    Mirrors the same check in contractor_categorizer_judge.py --
    multi_task_architect_node's except block appends a message starting
    with "MultiTaskArchitect error:" instead of setting a real
    next_agent, so those runs aren't a real decomposition decision.

    Args:
        messages: The conversation, in either dict or LangChain-object
            message shape.

    Returns:
        True if the last message is this node's error-fallback text.
    """
    if not messages:
        return False
    last = messages[-1]
    content = last.get("content") if isinstance(last, dict) else getattr(last, "content", "")
    return isinstance(content, str) and content.startswith("MultiTaskArchitect error:")


def extract_status_from_run(run) -> str | None:
    """Reconstruct a historical run's sub-task list, if the decomposition completed.

    Args:
        run: A LangSmith Run object for one MultiTaskArchitect execution.

    Returns:
        A JSON string of the sub_tasks list, or None if the node is
        still gathering information, hit its error path, or produced no
        sub-tasks.
    """
    messages = run.outputs.get("messages", [])
    if _error_prefix_present(messages):
        return None
    if run.outputs.get("next_agent") != "IntakeCoordinator":
        return None
    sub_tasks = run.outputs.get("sub_tasks") or []
    if not sub_tasks:
        return None
    return json.dumps(sub_tasks)


def maybe_evaluate_async(messages: list, sub_tasks: list | None) -> None:
    """Fire the online judge for the current live MultiTaskArchitect run.

    Call this from inside `multi_task_architect_node`, right after the
    sub-task JSON has been parsed out of the ALL_DONE-marked response --
    not from the "still gathering information" branch.

    Args:
        messages: The conversation so far, as stored on `state["messages"]`.
        sub_tasks: The finalized sub_tasks list, or None/empty if the
            node is still gathering information -- call sites should
            pass None in that case, mirroring `extract_status_from_run`
            above.
    """
    if not sub_tasks or random.random() > SAMPLE_RATE:
        return

    run = get_current_run_tree()
    if run is None:
        return

    conversation_text = format_conversation(messages)
    status = json.dumps(sub_tasks)

    threading.Thread(
        target=judge_and_route,
        args=(
            conversation_text, status, run.id, run.trace_id,
            SYSTEM_PROMPT, FEEDBACK_KEY, GOOD_QUEUE_ID, CORRECTION_QUEUE_ID,
        ),
        kwargs={"extra_context": _get_categories_context()},
        daemon=True,
    ).start()