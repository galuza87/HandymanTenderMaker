"""Node-specific judge config and the inline (live-traffic) trigger for
DataValidator.

Backfilling past DataValidator runs is handled separately in
backfill.py, which reuses `judge_and_route` from eval_core.py directly
rather than going through `maybe_evaluate_async` here -- the inline
trigger's job (sampling, background-thread dispatch, live run-tree
lookup) only makes sense while a real conversation is in flight.
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
    """Reconstruct a historical run's DataValidator decision from its output.

    Backfilled runs don't have the live `parsed.status` the inline call
    has direct access to -- only what the node actually returned.
    Looping back to "DataValidator" is how the node signals "not enough
    information" (see `data_validator_edge` in graph.py), so that's
    reconstructed from `next_agent` here, same as the very first
    (pre-inline, polling) version of this evaluator did.

    Args:
        run: A LangSmith Run object for one DataValidator execution.

    Returns:
        "not enough information" or "enough information". DataValidator
        has no error-fallback path that skips a real decision (unlike
        Categorizer), so this never returns None.
    """
    decided_not_enough_info = run.outputs.get("next_agent") == "DataValidator"
    return "not enough information" if decided_not_enough_info else "enough information"


def maybe_evaluate_async(messages: list, status: str) -> None:
    """Fire the online judge for the current live DataValidator run, if sampled in.

    Call this from inside `data_validator_node`, after `parsed` (the
    node's real decision) has been computed. Safe to call
    unconditionally -- it no-ops if tracing isn't active (e.g. local
    dev without LANGSMITH_TRACING set) or the sample roll misses, and
    it never blocks or raises into the caller.

    Args:
        messages: The conversation so far, in the same shape stored on
            `state["messages"]`.
        status: `DataValidatorOutput.status`, taken directly from the
            node's real output -- more accurate than reconstructing it
            from routing, since it's the actual decision rather than an
            inference from `next_agent`.
    """
    if random.random() > SAMPLE_RATE:
        return

    # Only judge runs LangSmith is actually tracing -- get_current_run_tree()
    # returns None when tracing is off, and there's nothing to attach
    # feedback to in that case.
    run = get_current_run_tree()
    if run is None:
        return

    conversation_text = format_conversation(messages)

    # Background thread, not a direct call: the judge is a network call
    # to Groq that takes a second or two, and the user is waiting on
    # data_validator_node's return value. Running it here would tax
    # every real conversation turn with judge latency.
    threading.Thread(
        target=judge_and_route,
        args=(
            conversation_text, status, run.id, run.trace_id,
            SYSTEM_PROMPT, FEEDBACK_KEY, GOOD_QUEUE_ID, CORRECTION_QUEUE_ID,
        ),
        daemon=True,
    ).start()