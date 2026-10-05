import json
import os
from typing import Any, cast

from langsmith import Client
from openai import OpenAI

# Langsmith client to fetch the project and run data
langsmith_client = Client()

# Judge client to use for LLM-as-a-judge evaluation
judge = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_API_KEY"],
)


def format_conversation(messages: list) -> str:
    """Expects: message list. Modifies: nothing. Returns: newline transcript."""
    lines = []
    for m in messages:
        role = m.get("role") if isinstance(m, dict) else getattr(m, "type", "user")
        content = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def already_evaluated(run, feedback_key: str) -> bool:
    """Expects: run object and feedback key. Modifies: nothing. Returns: whether that key already exists."""
    stats = getattr(run, "feedback_stats", None) or {}
    return feedback_key in stats


def resolve_feedback_session_id(session_id: str | None) -> str | None:
    """Expects: optional LangSmith session ID. Modifies: nothing. Returns: a valid session/project UUID or None."""
    if session_id and str(session_id).strip():
        return str(session_id)

    project_name = os.environ.get("LANGSMITH_PROJECT") or os.environ.get("LANGCHAIN_PROJECT")
    if not project_name:
        return None

    try:
        project = langsmith_client.read_project(project_name=project_name)
        project_id = getattr(project, "id", None)
        if project_id:
            return str(project_id)
    except Exception:
        return None

    return None


def judge_and_route(
    conversation_text: str,
    status: str,
    run_id,
    session_id,
    trace_id,
    system_prompt: str,
    feedback_key: str,
    good_queue_id: str | None,
    correction_queue_id: str | None,
    extra_context: str | None = None,
) -> None:
    """Expects: judge data, run IDs, and session metadata. Modifies: scores and may route annotation queue. Returns: None."""
    try:
        resolved_session_id = resolve_feedback_session_id(session_id)
        if not resolved_session_id:
            print(f"[online eval] skipping feedback for run {run_id}: LangSmith session_id/project_id is empty")
            return

        user_prompt = f"Conversation:\n{conversation_text}\n\nNode's decision: {status}"
        if extra_context:
            user_prompt += f"\n\n{extra_context}"

        # The OpenAI SDK's type stubs expose ``chat`` as a method, although at
        # runtime it is the completions resource. Cast to Any to silence the
        # false positive for this call only, rather than ignoring the whole file.
        completion = cast(Any, judge).chat.completions.create(
            model=os.environ.get("EVAL_MODEL", "openai/gpt-oss-120b"),
            # Zero temperature: for repeatable verdicts, since we store it in regression-test dataaset
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
            session_id=resolved_session_id,
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