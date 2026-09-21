"""Node-specific judge config and the inline (live-traffic) trigger for
TenderCreator.

Known limitation, larger than the other nodes': the actual tender text
being judged is never part of `state["messages"]` or this node's
returned output -- only a generic confirmation message is. The real
`tender_text` exists solely inside the node's local scope, and, under
LangSmith tracing, inside a *child* run nested under this node's own run
(the `agent.invoke()` call that generated it). That means:

- The inline trigger below works cleanly, since the node has
  `tender_text` directly in scope and can pass it straight to
  `maybe_evaluate_async`.
- Backfilling this node from `run.outputs` alone does NOT work -- there
  is nothing there to judge. `extract_status_from_run` returns None
  unconditionally and is a placeholder until backfill is extended to
  fetch the child run(s) for a trace (e.g. via
  `list_runs(trace_id=..., tree_filter=...)`) and pull `tender_text`
  from there instead.
"""

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
The node writes a professional tender (job description) shown to contractors, based on
the conversation history.

Judge the tender good only if it is clear, complete (covers the scope of work discussed,
without inventing details not implied by the conversation), and written in a professional
tone with no leftover greetings or chatbot-style phrasing.

Respond with strict JSON only: {"correct": true or false, "reasoning": "<one sentence>"}"""


def extract_status_from_run(run) -> str | None:
    """Placeholder -- backfill is not supported for this node yet.

    The generated tender text lives in a child run of the trace, not in
    this run's own `outputs`, so there is nothing here to extract. See
    the module docstring for what extending this would require.

    Args:
        run: A LangSmith Run object for one TenderCreator execution.

    Returns:
        Always None.
    """
    return None


def maybe_evaluate_async(messages: list, tender_text: str) -> None:
    """Fire the online judge for one generated tender, on the live path.

    Call this once per tender generated -- i.e. inside
    `tender_creator_node`'s loop, right after each `tender_text` is
    produced, in both the single-tender case and the per-sub-task
    multi-tender case.

    Args:
        messages: The conversation so far, as stored on `state["messages"]`.
        tender_text: The tender text just generated for this project (or
            this sub-task, in the multi-tender case).
    """
    if random.random() > SAMPLE_RATE:
        return

    run = get_current_run_tree()
    if run is None:
        return

    conversation_text = format_conversation(messages)

    threading.Thread(
        target=judge_and_route,
        args=(
            conversation_text, tender_text, run.id, run.trace_id,
            SYSTEM_PROMPT, FEEDBACK_KEY, GOOD_QUEUE_ID, CORRECTION_QUEUE_ID,
        ),
        daemon=True,
    ).start()