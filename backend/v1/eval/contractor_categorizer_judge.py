"""Node-specific judge config and the inline (live-traffic) trigger for
ContractorCategorizer.

The judge is given a category_id -> name/description mapping (fetched
once via `fetch_available_categories`, cached for the process lifetime)
as extra context, so it can check whether the chosen ID actually matches
the trade discussed -- not just whether the conversation makes some
category assignment plausible. The category list is fetched straight
from the DB-backed tool in Python, not via the judge model calling it
itself -- there's no need for the Groq client to do tool-calling here.

Still not covered: whether `identified_categories`' hardcoded
"Categorized by AI" placeholder name should be a real one. That's a
separate node-level fix, unrelated to this judge.
"""

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
    """Fetch (and cache) the category list as context text for the judge prompt.

    Degrades gracefully on failure -- if the DB call fails, the judge
    just falls back to reasoning from the conversation alone, same as
    it did before this context existed, rather than blocking evaluation
    entirely over a categories-lookup failure.

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
    """Check whether the node's own error-fallback text is in the transcript.

    contractor_categorizer_node's except block appends a message
    starting with "ContractorCategorizer error:" rather than setting a
    real next_agent -- that's not a categorization decision, so runs
    ending this way should be skipped rather than judged.

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
    return isinstance(content, str) and content.startswith("ContractorCategorizer error:")


def extract_status_from_run(run) -> str | None:
    """Reconstruct a historical run's identified category, if any.

    Returns None both when the node is still gathering information
    (next_agent looped back to "ContractorCategorizer") and when the
    node hit its error-fallback path -- neither is a completed
    categorization decision.

    Args:
        run: A LangSmith Run object for one ContractorCategorizer execution.

    Returns:
        The identified category_id as a string, or None if there's no
        completed decision to judge.
    """
    messages = run.outputs.get("messages", [])
    if _error_prefix_present(messages):
        return None
    if run.outputs.get("next_agent") != "IntakeCoordinator":
        return None
    identified = run.outputs.get("identified_categories") or []
    if not identified:
        return None
    return str(identified[-1].get("category_id"))


def maybe_evaluate_async(messages: list, category_id: list) -> None:
    """Fire the online judge for the current live ContractorCategorizer run.

    Call this from inside `contractor_categorizer_node`, right after a
    category_id is parsed out of the ALL_DONE_CATEGORY_<ID> sentinel --
    not from the "still gathering information" branch, where there's no
    completed decision yet.

    Args:
        messages: The conversation so far, as stored on `state["messages"]`.
        category_id: The category_id just identified, or None if the
            node is still gathering information -- call sites should
            pass None (or skip calling) in that case, mirroring
            `extract_status_from_run` above.
    """
    if category_id is None or random.random() > SAMPLE_RATE:
        return

    run = get_current_run_tree()
    if run is None:
        return

    conversation_text = format_conversation(messages)

    threading.Thread(
        target=judge_and_route,
        args=(
            conversation_text, str(category_id), run.id, run.trace_id,
            SYSTEM_PROMPT, FEEDBACK_KEY, GOOD_QUEUE_ID, CORRECTION_QUEUE_ID,
        ),
        kwargs={"extra_context": _get_categories_context()},
        daemon=True,
    ).start()