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
SAMPLE_RATE = float(os.environ.get("INFORMATION_GATHERER_SAMPLE_RATE", "1.0"))
GOOD_QUEUE_ID = os.environ.get("INFORMATION_GATHERER_GOOD_QUEUE_ID")
CORRECTION_QUEUE_ID = os.environ.get("INFORMATION_GATHERER_CORRECTION_QUEUE_ID")
FEEDBACK_KEY = "information_gatherer_correctness"

SYSTEM_PROMPT = """You audit an "InformationGatherer" node in a handyman-job intake chatbot.
The node's only job is to ask ONE clarifying question when the user's request is too vague
to identify a trade.

Judge the question good only if it is a single question (not several bundled together),
directly relevant to what's missing from the conversation so far, and phrased in a way
that would actually help narrow down what trade is needed next.

Respond with strict JSON only: {"correct": true or false, "reasoning": "<one sentence>"}"""


def _extract_last_ai_text(messages: list) -> str | None:
    """Expects: message list. Modifies: nothing. Returns: last AI text or None."""
    if not messages:
        return None
    last = messages[-1]
    content = last.get("content") if isinstance(last, dict) else getattr(last, "content", "")
    if not isinstance(content, str) or content.startswith("InformationGatherer error:"):
        return None
    return content


def extract_status_from_run(run) -> str | None:
    """Expects: a LangSmith run. Modifies: nothing. Returns: question text or None."""
    return _extract_last_ai_text(run.outputs.get("messages", []))


def maybe_evaluate_async(messages: list, session_id: str | None = None) -> None:
    """Expects: messages and optional node session ID. Modifies: starts a background judge when sampling allows it. Returns: None."""
    if random.random() > SAMPLE_RATE:
        return

    question = _extract_last_ai_text(messages)
    if question is None:
        return

    run = get_current_run_tree()
    if run is None:
        return

    effective_session_id = session_id or getattr(run, "session_id", None)
    conversation_text = format_conversation(messages)

    threading.Thread(
        target=judge_and_route,
        args=(
            conversation_text, question, run.id, effective_session_id, run.trace_id,
            SYSTEM_PROMPT, FEEDBACK_KEY, GOOD_QUEUE_ID, CORRECTION_QUEUE_ID,
        ),
        daemon=True,
    ).start()