"""Backfill evaluation for past traces, across every node that has a
registered evaluator.

Run manually (`python -m backend.v1.eval.backfill`) whenever you want
historical runs scored -- e.g. right after adding a new evaluator (to
score everything that already happened before today), or after a batch
of manual test conversations.

Unlike the inline evaluators (see data_validator_judge.py,
categorizer_judge.py), this runs synchronously and sequentially -- there
is no live user-facing request waiting on it, so there's no need for the
background-thread dance the inline trigger functions do.
"""

from datetime import datetime, timezone

from langsmith import Client

from backend.v1.eval.eval_core import already_evaluated, format_conversation, judge_and_route
from backend.v1.eval import (
    categorizer_judge,
    contractor_categorizer_judge,
    data_validator_judge,
    information_gatherer_judge,
    multi_task_architect_judge,
)

langsmith_client = Client()

# One entry per node with a registered evaluator. Adding a new node's
# evaluator later means appending here -- `backfill_node` and the
# date/already-evaluated filtering below stay the same for every node.
#
# `extract_status` must return None for any run where the node didn't
# make a real decision (e.g. an error-fallback path) -- `backfill_node`
# skips those runs rather than sending them to the judge, same as the
# inline trigger functions already do for the same paths.
EVALUATORS = [
    {
        "node_name": "DataValidator",
        "feedback_key": data_validator_judge.FEEDBACK_KEY,
        "system_prompt": data_validator_judge.SYSTEM_PROMPT,
        "good_queue_id": data_validator_judge.GOOD_QUEUE_ID,
        "correction_queue_id": data_validator_judge.CORRECTION_QUEUE_ID,
        "extract_status": data_validator_judge.extract_status_from_run,
    },
    {
        "node_name": "Categorizer",
        "feedback_key": categorizer_judge.FEEDBACK_KEY,
        "system_prompt": categorizer_judge.SYSTEM_PROMPT,
        "good_queue_id": categorizer_judge.GOOD_QUEUE_ID,
        "correction_queue_id": categorizer_judge.CORRECTION_QUEUE_ID,
        "extract_status": categorizer_judge.extract_status_from_run,
    },
    {
        "node_name": "ContractorCategorizer",
        "feedback_key": contractor_categorizer_judge.FEEDBACK_KEY,
        "system_prompt": contractor_categorizer_judge.SYSTEM_PROMPT,
        "good_queue_id": contractor_categorizer_judge.GOOD_QUEUE_ID,
        "correction_queue_id": contractor_categorizer_judge.CORRECTION_QUEUE_ID,
        "extract_status": contractor_categorizer_judge.extract_status_from_run,
    },
    {
        "node_name": "MultiTaskArchitect",
        "feedback_key": multi_task_architect_judge.FEEDBACK_KEY,
        "system_prompt": multi_task_architect_judge.SYSTEM_PROMPT,
        "good_queue_id": multi_task_architect_judge.GOOD_QUEUE_ID,
        "correction_queue_id": multi_task_architect_judge.CORRECTION_QUEUE_ID,
        "extract_status": multi_task_architect_judge.extract_status_from_run,
    },
    {
        "node_name": "InformationGatherer",
        "feedback_key": information_gatherer_judge.FEEDBACK_KEY,
        "system_prompt": information_gatherer_judge.SYSTEM_PROMPT,
        "good_queue_id": information_gatherer_judge.GOOD_QUEUE_ID,
        "correction_queue_id": information_gatherer_judge.CORRECTION_QUEUE_ID,
        "extract_status": information_gatherer_judge.extract_status_from_run,
    },
    # TenderCreator is deliberately not registered yet: its
    # extract_status_from_run is a placeholder that always returns None
    # (see tender_creator_judge.py's module docstring for why -- the
    # tender text lives in a child run, not this run's own outputs), so
    # registering it here would only spend list_runs calls skipping
    # every single run.
]


def backfill_node(
    evaluator: dict,
    start_date: datetime,
    end_date: datetime,
    project_name: str = "HandymanTenderMaker",
) -> None:
    """Score every not-yet-evaluated run for one node within a date range.

    Args:
        evaluator: One entry from `EVALUATORS`.
        start_date: Only runs starting on or after this time are considered.
        end_date: Only runs starting on or before this time are considered.
        project_name: The LangSmith tracing project to pull runs from.
            Defaults to "HandymanTenderMaker".
    """
    run_filter = (
        f'and(eq(name, "{evaluator["node_name"]}"), '
        f'gte(start_time, "{start_date.isoformat()}"), '
        f'lte(start_time, "{end_date.isoformat()}"))'
    )

    runs = langsmith_client.list_runs(project_name=project_name, filter=run_filter)

    for run in runs:
        # Skip runs this evaluator has already scored, so re-running the
        # backfill (e.g. daily, or after a failed partial run) doesn't
        # re-judge and re-queue the same runs repeatedly.
        if already_evaluated(run, evaluator["feedback_key"]):
            continue

        status = evaluator["extract_status"](run)

        # Some nodes have a path where no real decision was made (e.g.
        # Categorizer's error-fallback to "InformationGatherer") --
        # `extract_status` returns None there, and there is nothing
        # meaningful for the judge to evaluate, so skip it rather than
        # judging a decision the node never actually made.
        if status is None:
            continue

        conversation_text = format_conversation(run.inputs.get("messages", []))

        judge_and_route(
            conversation_text,
            status,
            run.id,
            run.trace_id,
            evaluator["system_prompt"],
            evaluator["feedback_key"],
            evaluator["good_queue_id"],
            evaluator["correction_queue_id"],
        )


def run_backfill(
    start_date: datetime,
    end_date: datetime,
    project_name: str = "HandymanTenderMaker",
) -> None:
    """Backfill every registered evaluator over the same date range.

    Args:
        start_date: Only runs starting on or after this time are considered.
        end_date: Only runs starting on or before this time are considered.
        project_name: The LangSmith tracing project to pull runs from.
            Defaults to "HandymanTenderMaker".
    """
    for evaluator in EVALUATORS:
        # Keyword args, not positional -- backfill_node's project_name has
        # a default and comes last in its signature, so passing positionally
        # here would silently misassign start_date/end_date/project_name.
        backfill_node(
            evaluator,
            start_date=start_date,
            end_date=end_date,
            project_name=project_name,
        )


if __name__ == "__main__":
    run_backfill(
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_date=datetime.now(timezone.utc),
    )