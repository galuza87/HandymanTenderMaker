"""Shared judge/feedback/queue-routing core for the HandymanDB online
evaluators.

Every node-specific judge module (data_validator_judge.py,
categorizer_judge.py, ...) imports from here instead of duplicating this
logic. This is what's called from two different places:

- Inline, from inside a node itself, on a background thread, while a
  real conversation is in flight (see e.g. data_validator_judge.py's
  `maybe_evaluate_async`).
- From backfill.py, synchronously, in a batch loop over historical runs.

Keeping the core in one place means a run judged live and a run judged
during backfill go through the exact same scoring and routing logic --
there is only one place that logic can drift.
"""

import json
import os
from typing import Any, cast

from langsmith import Client
from openai import OpenAI

# Two separate clients on purpose: one talks to LangSmith (reads runs,
# writes feedback, manages queues), the other talks to the judge model.
# Keeping them separate means swapping the judge backend later (Groq ->
# Gemini, say) only touches `judge`, never `langsmith_client`.
langsmith_client = Client()  # reads LANGSMITH_API_KEY from env

judge = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_API_KEY"],
)


def format_conversation(messages: list) -> str:
    """Render a message list (dicts or LangChain objects) as plain text.

    Shared across all node judge modules, since every node's judge
    prompt needs the same conversation-to-text rendering regardless of
    what decision it's judging.

    Args:
        messages: Conversation messages, in either the dict shape sent
            over the API or the LangChain object shape stored on a
            traced run's inputs (LangGraph runs store LangChain message
            objects, e.g. AIMessage/HumanMessage, not plain dicts, so
            both shapes are handled here).

    Returns:
        A newline-separated "role: content" transcript, in original order.
    """
    lines = []
    for m in messages:
        role = m.get("role") if isinstance(m, dict) else getattr(m, "type", "user")
        content = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def already_evaluated(run, feedback_key: str) -> bool:
    """Check whether a run already has feedback under the given key.

    Used by the backfill script to implement "was not evaluated yet" --
    checked client-side against each run's `feedback_stats`, rather than
    a server-side filter string, since there's no confirmed filter-DSL
    operator for "run lacks feedback key X" and it's better to be
    correct here than clever.

    Args:
        run: A LangSmith Run object, as returned by `Client.list_runs`.
        feedback_key: The feedback key to check for, e.g.
            "data_validator_correctness".

    Returns:
        True if the run already carries feedback under that key.
    """
    stats = getattr(run, "feedback_stats", None) or {}
    return feedback_key in stats


def judge_and_route(
    conversation_text: str,
    status: str,
    run_id,
    trace_id,
    system_prompt: str,
    feedback_key: str,
    good_queue_id: str | None,
    correction_queue_id: str | None,
    extra_context: str | None = None,
) -> None:
    """Call the judge model and record its verdict against a specific run.

    Generic across nodes -- the node-specific part is entirely the
    `system_prompt` (what "correct" means for that node) and the
    `feedback_key`/queue IDs (where the verdict gets recorded). Every
    exception is caught and logged rather than raised, since this is
    called both from a background thread during live traffic (where
    raising would be invisible to anyone) and from a batch backfill
    script (where one bad run shouldn't abort the whole run).

    Two queues, not one: runs the judge marks correct go to
    `good_queue_id`, where a human spot-checks before promoting into a
    "confirmed good" dataset -- skipping that check would let the
    judge's own blind spots quietly become ground truth. Runs the judge
    flags go to `correction_queue_id`, where a human writes the
    corrected expected output before it becomes a regression-test
    example -- the judge can flag that something's wrong, but only a
    human can supply what "right" should have looked like.

    Args:
        conversation_text: The conversation so far, already formatted
            as plain text (see `format_conversation`).
        status: The node's actual decision, in whatever short string
            form its own judge prompt expects (e.g. "single"/"multiple",
            "enough_information"/"not enough information").
        run_id: The LangSmith run ID of the node execution being judged.
        trace_id: The LangSmith trace ID that run belongs to -- passed
            to `create_feedback` so the client can background the write
            itself, on top of whatever threading the caller already does.
        system_prompt: The node-specific judge instructions, ending in
            an instruction to respond with strict JSON:
            {"correct": true|false, "reasoning": "<one sentence>"}.
        feedback_key: The feedback key this verdict is recorded under,
            e.g. "data_validator_correctness". Also what
            `already_evaluated` checks for during backfill.
        good_queue_id: Annotation queue ID for judge-confirmed-correct
            runs, or None if that queue isn't configured yet (e.g. its
            env var is unset) -- queue routing is skipped in that case,
            but the feedback score below is still recorded regardless.
        correction_queue_id: Same as `good_queue_id`, for judge-flagged runs.
        extra_context: Optional additional context appended to the
            judge's user prompt, after the conversation and decision --
            e.g. a category_id -> name/description mapping for nodes
            whose correctness depends on category assignment (see
            contractor_categorizer_judge.py, multi_task_architect_judge.py).
    """
    try:
        user_prompt = f"Conversation:\n{conversation_text}\n\nNode's decision: {status}"
        if extra_context:
            user_prompt += f"\n\n{extra_context}"

        # The OpenAI SDK's current type stubs expose ``chat`` as a method,
        # although at runtime it is the completions resource used here.
        completion = cast(Any, judge).chat.completions.create(
            model=os.environ.get("EVAL_MODEL", "llama3-70b-8192"),
            # Zero temperature: the verdict feeds a regression-test
            # dataset, so it needs to be repeatable, not creatively varied.
            temperature=0.0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        raw_content = completion.choices[0].message.content
        # The SDK types this as str | None since a response can in theory
        # come back with no content. Judge calls don't use tools, so this
        # shouldn't happen in practice -- but failing with a clear message
        # here is better than json.loads(None) raising a generic TypeError
        # that the except block below would catch anyway, just less legibly.
        if raw_content is None:
            raise ValueError("Judge model returned empty content")

        verdict = json.loads(raw_content)

        # Attach the score regardless of outcome -- this is what makes
        # pass rate over time queryable/chartable in the LangSmith UI,
        # independent of which queue the run ends up routed to below.
        langsmith_client.create_feedback(
            run_id=run_id,
            trace_id=trace_id,
            key=feedback_key,
            score=1 if verdict["correct"] else 0,
            comment=verdict["reasoning"],
        )

        target_queue = good_queue_id if verdict["correct"] else correction_queue_id
        # Queue routing is optional -- the feedback above is recorded
        # either way, so a node whose queue IDs aren't configured yet
        # still gets scored, just not routed anywhere for review yet.
        if target_queue is not None:
            langsmith_client.add_runs_to_annotation_queue(target_queue, run_ids=[run_id])

    except Exception as e:
        # Swallow, don't raise. When called from a background thread
        # during live traffic, nothing is watching this thread for
        # exceptions -- raising here would just be silently lost.
        # When called from backfill.py, one bad run shouldn't abort
        # the rest of the batch.
        print(f"[online eval] judge/feedback failed for run {run_id}: {e}")