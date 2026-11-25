"""Version-agnostic routes for Agent Testing Endpoints (/api/{version}/tests/*).

Provides:
1. POST /api/{version}/tests/process-state: Single-turn conversation execution against
   the engine specified by `{version}` (e.g. `v1`, `v2`), returning the detected step
   (`ask_additional_info`, `tool_use`, `request_hitl`, `generate_document`) and whether
   it matches `expected_step`.
2. POST /api/{version}/tests/jobs: Batch test job execution (sequential or concurrent)
   with structured job directory logging in `backend/test_jobs/job_<job_id>/`.
3. GET /api/{version}/tests/jobs/{job_id}: Retrieve summary and failure breakdown for a batch job.
4. Legacy dashboard endpoints (/run, /history, /runs/{run_id}) preserved for TestingDashboard.jsx.
"""

import asyncio
from datetime import datetime
import importlib
import json
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

import backend.config as app_config
from backend.db import (
    get_client_by_id,
    get_test_results_by_run,
    get_test_runs,
    insert_test_result,
    insert_test_run,
)
from backend.models import (
    AgentState,
    BatchTestJobRequest,
    BatchTestJobResponse,
    CategorizerDecisionClass,
    StateTestRequest,
    StateTestResponse,
)
from backend.services.jwt_auth import extract_client_id_from_jwt
from backend.services.test_evaluator import (
    build_turn_summary,
    evaluate_outcome,
    is_hitl_draft_message,
)

router = APIRouter()

ALGORITHM_VERSION = os.getenv("ALGORITHM_VERSION", "v2")
ENABLE_TEST_ENDPOINTS: bool = getattr(app_config, "ENABLE_TEST_ENDPOINTS", True)
TEST_JOBS_DIR: Path = Path(__file__).resolve().parents[1] / "test_jobs"
AGENT_CASES_DIR: Path = Path(__file__).resolve().parents[1] / "tests" / "agent_cases"

_job_counter: int = 0


def _is_testing_enabled() -> bool:
    """Return True if testing endpoints are enabled in config/environment."""
    env_flag = os.getenv("ENABLE_TEST_ENDPOINTS", "true").lower() == "true"
    cfg_flag = getattr(app_config, "ENABLE_TEST_ENDPOINTS", True)
    return bool(ENABLE_TEST_ENDPOINTS and cfg_flag and env_flag)


def _extract_bearer_value(authorization: Optional[str]) -> Optional[str]:
    """Extract the bearer value from an `Authorization: Bearer <value>` header."""
    if not authorization or not authorization.strip():
        return None
    raw = authorization.strip()
    if not raw.lower().startswith("bearer "):
        return None
    value = raw[7:].strip()
    return value or None


def verify_test_access(
    x_test_api_key: Optional[str] = Header(default=None, alias="X-Test-Api-Key"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> int:
    """Authenticate the request and return the resolved `Clients.id` from `Authorization: Bearer <value>`.

    - If `X-Test-Api-Key` is provided: validates it against `TEST_API_KEY` and reads
      `Authorization: Bearer <client_id>` directly as the numeric `Clients.id`.
    - If `X-Test-Api-Key` is omitted: verifies and decodes `Authorization: Bearer <jwt_token>`
      as a signed JWT token and extracts `client_id`.
    """
    if not _is_testing_enabled():
        raise HTTPException(
            status_code=403,
            detail="Testing endpoints are disabled (ENABLE_TEST_ENDPOINTS=false).",
        )

    bearer_value = _extract_bearer_value(authorization)

    if x_test_api_key is not None:
        expected_key = getattr(app_config, "TEST_API_KEY", None) or os.getenv(
            "TEST_API_KEY", "dev-test-api-key"
        )
        if x_test_api_key != expected_key:
            raise HTTPException(
                status_code=401,
                detail="Invalid X-Test-Api-Key header.",
            )
        if not bearer_value:
            raise HTTPException(
                status_code=401,
                detail="Missing 'Authorization: Bearer <client_id>' header.",
            )
        try:
            return int(bearer_value)
        except ValueError as exc:
            raise HTTPException(
                status_code=401,
                detail="When X-Test-Api-Key is used, 'Authorization: Bearer <value>' must be an integer Clients.id.",
            ) from exc

    if not bearer_value:
        raise HTTPException(
            status_code=401,
            detail="Missing 'Authorization: Bearer <token>' header.",
        )

    try:
        return extract_client_id_from_jwt(bearer_value)
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid JWT token: {exc}",
        ) from exc


def load_engine(version_str: Optional[str] = None) -> Any:
    """Dynamically load an Engine instance from backend.<version>.engine."""
    target_version = (version_str or ALGORITHM_VERSION).strip()
    module_suffix = target_version.replace(".", "_")
    try:
        module = importlib.import_module(f"backend.{module_suffix}.engine")
        return module.Engine()
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Engine version '{target_version}' not found. Make sure backend/{module_suffix}/engine.py exists.",
        ) from exc


def _infer_state_from_conversation(state: AgentState) -> None:
    """Infer mid-conversation state from messages when caller provides conversation-only input."""
    if state.next_step != "determine_number_of_subtasks":
        return

    has_hitl_draft = any(
        msg.get("role") == "assistant" and is_hitl_draft_message(str(msg.get("content", "")))
        for msg in state.messages
    )
    if not has_hitl_draft:
        return

    state.next_step = "IntakeCoordinator"
    state.has_fetched_past_feedback = True
    state.open_topics = []
    if state.CategorizerDecision is None:
        state.CategorizerDecision = CategorizerDecisionClass(decision="single")
    if not state.identified_categories:
        state.identified_categories = [{"category_id": 1, "name": "General"}]


def _prepare_client_state(req: StateTestRequest, header_client_id: int) -> AgentState:
    """Verify resolved client_id exists in dbo.Clients and merge client profile details into state."""
    effective_client_id = req.client_id if req.client_id is not None else header_client_id
    client = get_client_by_id(effective_client_id)
    if not client:
        raise HTTPException(
            status_code=404,
            detail=f"Client with ID {effective_client_id} was not found in dbo.Clients.",
        )

    state_copy = req.resolve_state()
    _infer_state_from_conversation(state_copy)
    state_copy.user_id = client["id"]

    full_name = f"{client.get('name', '')} {client.get('last_name', '')}".strip()
    merged_client_info = {
        "name": full_name,
        "phone": client.get("phone", "") or "",
        "address": client.get("address", "") or "",
    }
    if state_copy.client_info:
        merged_client_info.update({k: v for k, v in state_copy.client_info.items() if v})
    state_copy.client_info = merged_client_info
    return state_copy


async def _execute_single_state_test(
    req: StateTestRequest,
    version: str = "v1",
    header_client_id: int = 1,
) -> StateTestResponse:
    """Execute a single StateTestRequest against the specified version with timeout (504) protection."""
    dry_run = req.resolve_dry_run()
    target_version = (
        req.options.algorithm_version
        if req.options and req.options.algorithm_version
        else version
    )
    timeout_sec = getattr(app_config, "REQUEST_TIMEOUT_SECONDS", 60.0)

    state_before = _prepare_client_state(req, header_client_id)
    effective_client_id = state_before.user_id or header_client_id
    working_state = state_before.model_copy(deep=True)
    engine = load_engine(target_version)

    start_time = time.perf_counter()
    try:
        state_after = await asyncio.wait_for(
            asyncio.to_thread(engine.process, working_state, dry_run=dry_run),
            timeout=timeout_sec,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=f"Gateway Timeout: Agent execution exceeded {timeout_sec}s timeout.",
        ) from exc

    execution_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
    turn_summary = build_turn_summary(state_before, state_after)
    detected_step = turn_summary.detected_outcome_type

    expected_outcome = req.resolve_expected_outcome()
    evaluation = None
    expected_step = None
    is_step_correct = None
    if expected_outcome is not None:
        evaluation = evaluate_outcome(
            expected_outcome,
            state_before,
            state_after,
            turn_summary,
        )
        expected_step = expected_outcome.outcome_type
        is_step_correct = detected_step == expected_step

    latest_reply = (
        turn_summary.latest_message.get("content")
        if turn_summary.latest_message
        else None
    )

    return StateTestResponse(
        test_id=req.test_id,
        version=target_version,
        client_id=effective_client_id,
        step=detected_step,
        expected_step=expected_step,
        is_step_correct=is_step_correct,
        success=True if evaluation is None else evaluation.passed,
        reply=latest_reply,
        execution_time_ms=execution_time_ms,
        messages=state_after.messages,
        turn_summary=turn_summary,
        evaluation=evaluation,
        state=state_after,
    )


@router.post("/process-state", response_model=StateTestResponse)
async def process_state_endpoint(
    version: str,
    req: StateTestRequest,
    client_id: int = Depends(verify_test_access),
) -> StateTestResponse:
    """Execute a single conversation turn against the engine version specified in the URL."""
    return await _execute_single_state_test(req, version=version, header_client_id=client_id)


def _format_log_line(message: str) -> str:
    """Format a timestamped log line for job.log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] {message}"


def _build_batch_item_record(
    index: int,
    item_req: StateTestRequest,
    response: Optional[StateTestResponse],
    http_status: int,
    error_detail: Optional[str],
    elapsed_ms: float,
) -> Dict[str, Any]:
    """Create a structured result record and log line for a single item in a batch job."""
    test_id = item_req.test_id or f"req_{index:02d}"
    if response is not None:
        passed = response.success
        actual_outcome = response.step
        expected_outcome = response.expected_step
        mismatches = response.evaluation.mismatches if response.evaluation else []
        level = "PASS" if passed else "FAIL"
        log_msg = (
            f"{level:<5} [req_{index:02d}] test_id=\"{test_id}\" | status={http_status} | "
            f"step={actual_outcome} | {response.execution_time_ms:.0f}ms"
        )
        if not passed and mismatches:
            log_msg += f" | mismatches={mismatches}"
        return {
            "index": index,
            "test_id": test_id,
            "http_status": http_status,
            "passed": passed,
            "execution_time_ms": response.execution_time_ms,
            "expected_outcome_type": expected_outcome,
            "actual_outcome_type": actual_outcome,
            "mismatches": mismatches,
            "response": response.model_dump(),
            "log_line": _format_log_line(log_msg),
        }

    log_msg = (
        f"FAIL  [req_{index:02d}] test_id=\"{test_id}\" | status={http_status} "
        f"({error_detail}) | {elapsed_ms:.0f}ms"
    )
    return {
        "index": index,
        "test_id": test_id,
        "http_status": http_status,
        "passed": False,
        "execution_time_ms": round(elapsed_ms, 2),
        "error": error_detail,
        "log_line": _format_log_line(log_msg),
    }


def _write_job_files(
    job_dir: Path,
    log_lines: List[str],
    summary_data: Dict[str, Any],
    results_list: List[Dict[str, Any]],
    failed_list: List[Dict[str, Any]],
) -> None:
    """Persist job.log, summary.json, results.json, and failed_requests.json into job_dir."""
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "job.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    (job_dir / "summary.json").write_text(
        json.dumps(summary_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (job_dir / "results.json").write_text(
        json.dumps(results_list, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (job_dir / "failed_requests.json").write_text(
        json.dumps(failed_list, indent=2, ensure_ascii=False), encoding="utf-8"
    )


async def _execute_batch_item_safely(
    idx: int,
    item_req: StateTestRequest,
    version: str,
    header_client_id: int,
    semaphore: asyncio.Semaphore,
    fail_fast: bool,
    state_tracker: Dict[str, bool],
) -> Optional[Dict[str, Any]]:
    """Run a single batch item under the concurrency semaphore and capture HTTP/runtime errors."""
    if fail_fast and state_tracker["aborted"]:
        return None

    async with semaphore:
        if fail_fast and state_tracker["aborted"]:
            return None
        record = await _invoke_batch_item(idx, item_req, version, header_client_id)
        if not record["passed"]:
            state_tracker["aborted"] = True
        return record


async def _invoke_batch_item(
    idx: int,
    item_req: StateTestRequest,
    version: str,
    header_client_id: int,
) -> Dict[str, Any]:
    """Invoke _execute_single_state_test and convert any exception into a structured batch record."""
    item_start = time.perf_counter()
    try:
        resp = await _execute_single_state_test(
            item_req, version=version, header_client_id=header_client_id
        )
        return _build_batch_item_record(idx, item_req, resp, 200, None, 0.0)
    except HTTPException as http_exc:
        elapsed = (time.perf_counter() - item_start) * 1000.0
        return _build_batch_item_record(
            idx, item_req, None, http_exc.status_code, str(http_exc.detail), elapsed
        )
    except Exception as exc:
        elapsed = (time.perf_counter() - item_start) * 1000.0
        return _build_batch_item_record(idx, item_req, None, 500, str(exc), elapsed)


def _load_single_case_files(case_names: Optional[List[str]] = None) -> List[StateTestRequest]:
    """Load single-request JSON test definitions from backend/tests/agent_cases/."""
    if not AGENT_CASES_DIR.exists():
        return []

    if case_names:
        paths = [
            AGENT_CASES_DIR / (name if name.endswith(".json") else f"{name}.json")
            for name in case_names
        ]
    else:
        paths = sorted(AGENT_CASES_DIR.glob("*.json"))

    loaded: List[StateTestRequest] = []
    for path in paths:
        if not path.is_file():
            raise HTTPException(
                status_code=404,
                detail=f"Test case file '{path.name}' not found in {AGENT_CASES_DIR}.",
            )
        raw = json.loads(path.read_text(encoding="utf-8"))
        if "messages" in raw or "state" in raw:
            req_item = StateTestRequest(**raw)
            if not req_item.test_id:
                req_item.test_id = path.stem
            loaded.append(req_item)
    return loaded


def _resolve_batch_requests(batch_req: BatchTestJobRequest) -> List[StateTestRequest]:
    """Build the list of StateTestRequest items to execute in a batch job."""
    if batch_req.requests:
        base_items = list(batch_req.requests)
    elif batch_req.messages is not None:
        base_items = [
            StateTestRequest(
                test_id=batch_req.job_name or "inline_case",
                messages=batch_req.messages,
                expected_step=batch_req.expected_step,
                expected_tools=batch_req.expected_tools,
            )
        ]
    else:
        base_items = _load_single_case_files(batch_req.test_cases)

    if not base_items:
        raise HTTPException(
            status_code=400,
            detail="Batch job must include at least one request, test_cases name, or messages list.",
        )

    target_count = batch_req.total_requests or len(base_items)
    if target_count <= 0:
        raise HTTPException(status_code=400, detail="total_requests must be at least 1.")

    expanded: List[StateTestRequest] = []
    for idx in range(target_count):
        template = base_items[idx % len(base_items)].model_copy(deep=True)
        base_id = template.test_id or f"case_{(idx % len(base_items)) + 1:02d}"
        if target_count > len(base_items):
            template.test_id = f"{base_id}_{idx + 1:02d}"
        expanded.append(template)
    return expanded


@router.post("/jobs", response_model=BatchTestJobResponse)
async def run_batch_test_job(
    version: str,
    batch_req: BatchTestJobRequest,
    client_id: int = Depends(verify_test_access),
) -> BatchTestJobResponse:
    """Execute a batch of StateTestRequest items against `{version}` and write logs to backend/test_jobs/."""
    global _job_counter
    resolved_requests = _resolve_batch_requests(batch_req)

    _job_counter += 1
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_id = f"{_job_counter:04d}_{timestamp_str}"
    job_dir = TEST_JOBS_DIR / f"job_{job_id}"

    concurrency = max(1, batch_req.concurrency)
    semaphore = asyncio.Semaphore(concurrency)
    state_tracker = {"aborted": False}

    log_lines: List[str] = [
        _format_log_line(
            f"INFO  Job #{job_id} started | version={version} | "
            f"total_requests={len(resolved_requests)} | concurrency={concurrency}"
        )
    ]

    job_start = time.perf_counter()
    raw_records = await asyncio.gather(
        *[
            _execute_batch_item_safely(
                i, r, version, client_id, semaphore, batch_req.fail_fast, state_tracker
            )
            for i, r in enumerate(resolved_requests, start=1)
        ]
    )
    total_job_ms = round((time.perf_counter() - job_start) * 1000.0, 2)

    records = [r for r in raw_records if r is not None]
    for r in records:
        log_lines.append(r.pop("log_line"))

    passed_count = sum(1 for r in records if r["passed"])
    failed_list = [r for r in records if not r["passed"]]
    failed_count = len(failed_list)
    status_breakdown: Dict[str, int] = {}
    for r in records:
        code_key = str(r["http_status"])
        status_breakdown[code_key] = status_breakdown.get(code_key, 0) + 1

    avg_ms = round(total_job_ms / len(records), 2) if records else 0.0
    overall_status = "PASSED" if failed_count == 0 else "FAILED"

    log_lines.append(
        _format_log_line(
            f"INFO  Job #{job_id} finished | status={overall_status} | passed={passed_count} | failed={failed_count}"
        )
    )

    summary_data = {
        "job_id": job_id,
        "job_name": batch_req.job_name,
        "version": version,
        "status": overall_status,
        "total_requests": len(records),
        "passed": passed_count,
        "failed": failed_count,
        "concurrency": concurrency,
        "total_execution_time_ms": total_job_ms,
        "avg_execution_time_ms": avg_ms,
        "status_code_breakdown": status_breakdown,
        "job_dir": str(job_dir),
    }

    _write_job_files(job_dir, log_lines, summary_data, records, failed_list)

    return BatchTestJobResponse(
        **summary_data,
        results=records,
        failed_requests=failed_list,
    )


@router.get("/jobs/{job_id}", response_model=BatchTestJobResponse)
async def get_batch_test_job(
    version: str,
    job_id: str,
    _client_id: int = Depends(verify_test_access),
) -> BatchTestJobResponse:
    """Retrieve the summary, results, and failed requests for a completed batch job."""
    folder_name = job_id if job_id.startswith("job_") else f"job_{job_id}"
    job_dir = TEST_JOBS_DIR / folder_name
    summary_path = job_dir / "summary.json"
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail=f"Test job '{job_id}' not found.")

    summary_data = json.loads(summary_path.read_text(encoding="utf-8"))
    results_path = job_dir / "results.json"
    failed_path = job_dir / "failed_requests.json"

    results_list = (
        json.loads(results_path.read_text(encoding="utf-8"))
        if results_path.exists()
        else []
    )
    failed_list = (
        json.loads(failed_path.read_text(encoding="utf-8"))
        if failed_path.exists()
        else []
    )

    return BatchTestJobResponse(
        **summary_data,
        results=results_list,
        failed_requests=failed_list,
    )


# ---------------------------------------------------------------------------
# Legacy Dashboard Endpoints (Preserved for frontend/src/TestingDashboard.jsx)
# ---------------------------------------------------------------------------

class TestCase(BaseModel):
    """Legacy single test case for contractor-intent dashboard runs."""
    id: Optional[int] = None
    input: str
    expected: str  # "single", "multiple", or "unknown"


class TestRunRequest(BaseModel):
    """Legacy test run request payload."""
    test_type: str
    cases: List[TestCase]


@router.post("/run")
def run_tests(version: str, request: TestRunRequest) -> Dict[str, Any]:
    """Execute legacy contractor-intent test suite from TestingDashboard.jsx."""
    if not request.cases:
        raise HTTPException(status_code=400, detail="No test cases provided")

    engine = load_engine(version or ALGORITHM_VERSION)
    results = []
    correct_count = 0
    total_time = 0.0

    for case in request.cases:
        start_time = time.time()
        state = AgentState(messages=[{"role": "user", "content": case.input}])

        if request.test_type == "contractor-intent":
            state = engine.process(state)
            actual = state.CategorizerDecision.decision if state.CategorizerDecision else "unknown"
        else:
            raise HTTPException(status_code=400, detail="Unknown test type")

        exec_time_ms = (time.time() - start_time) * 1000
        total_time += exec_time_ms
        is_correct = actual == case.expected
        if is_correct:
            correct_count += 1

        results.append({
            "id": case.id,
            "input": case.input,
            "expected": case.expected,
            "actual": actual,
            "exec_time": exec_time_ms,
            "is_correct": is_correct,
        })

    accuracy = (correct_count / len(request.cases)) * 100.0
    avg_time = total_time / len(request.cases)
    test_type_label = f"{request.test_type} ({version})"
    run_id = insert_test_run(test_type_label, accuracy, avg_time)
    if run_id:
        for res in results:
            insert_test_result(
                run_id,
                res["input"],
                res["expected"],
                res["actual"],
                res["exec_time"],
                res["is_correct"],
            )

    return {
        "run_id": run_id,
        "accuracy": accuracy,
        "avg_time_ms": avg_time,
        "results": results,
    }


@router.get("/history")
def get_history(version: str) -> List[Dict[str, Any]]:
    """Return historical test runs for TestingDashboard.jsx."""
    return get_test_runs()


@router.get("/runs/{run_id}")
def get_run_details(version: str, run_id: int) -> List[Dict[str, Any]]:
    """Return detailed test results for a specific historical run."""
    results = get_test_results_by_run(run_id)
    if not results:
        raise HTTPException(status_code=404, detail="Test run not found or no results")
    return results
