"""Routes for Agent Testing Endpoints (/api/v1/tests/*).

Provides:
1. POST /api/v1/tests/process-state: Single-turn manual/scripted state execution with
   action-based gold-standard evaluation, dry-run DB isolation, and 503/504 guards.
2. POST /api/v1/tests/jobs: Batch test job execution (sequential or concurrent) with
   structured job directory logging in `backend/test_jobs/job_<job_id>/`.
3. GET /api/v1/tests/jobs/{job_id}: Retrieve summary and failure breakdown for a batch job.
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
    StateTestRequest,
    StateTestResponse,
)
from backend.v1.services.test_evaluator import build_turn_summary, evaluate_outcome

router = APIRouter()

ALGORITHM_VERSION = os.getenv("ALGORITHM_VERSION", "v2")
ENABLE_TEST_ENDPOINTS: bool = getattr(app_config, "ENABLE_TEST_ENDPOINTS", True)
MAX_ACTIVE_REQUESTS: int = getattr(app_config, "MAX_ACTIVE_REQUESTS", 10)
TEST_REQUEST_TIMEOUT_SECONDS: float = getattr(app_config, "TEST_REQUEST_TIMEOUT_SECONDS", 60.0)
TEST_JOBS_DIR: Path = Path(__file__).resolve().parents[2] / "test_jobs"

_active_requests: int = 0
_job_counter: int = 0


def _is_testing_enabled() -> bool:
    """Return True if testing endpoints are enabled in config/environment."""
    env_flag = os.getenv("ENABLE_TEST_ENDPOINTS", "true").lower() == "true"
    cfg_flag = getattr(app_config, "ENABLE_TEST_ENDPOINTS", True)
    return bool(ENABLE_TEST_ENDPOINTS and cfg_flag and env_flag)


def verify_test_access(
    x_test_api_key: Optional[str] = Header(default=None, alias="X-Test-Api-Key"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> str:
    """Validate that testing endpoints are enabled and caller provided a valid TEST_API_KEY."""
    if not _is_testing_enabled():
        raise HTTPException(
            status_code=403,
            detail="Testing endpoints are disabled (ENABLE_TEST_ENDPOINTS=false).",
        )

    expected_key = getattr(app_config, "TEST_API_KEY", None) or os.getenv(
        "TEST_API_KEY", "dev-test-api-key"
    )

    provided_key = x_test_api_key
    if not provided_key and authorization:
        if authorization.lower().startswith("bearer "):
            provided_key = authorization[7:].strip()

    if not provided_key or provided_key != expected_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing test credentials. Provide X-Test-Api-Key or Authorization: Bearer <TEST_API_KEY>.",
        )

    return provided_key


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


def _prepare_simulated_state(req: StateTestRequest) -> AgentState:
    """Verify simulated_user_id exists in dbo.Clients and merge profile details into state."""
    client = get_client_by_id(req.simulated_user_id)
    if not client:
        raise HTTPException(
            status_code=404,
            detail=f"Simulated user with ID {req.simulated_user_id} was not found in dbo.Clients.",
        )

    state_copy = req.state.model_copy(deep=True)
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


async def _execute_single_state_test(req: StateTestRequest) -> StateTestResponse:
    """Execute a single StateTestRequest with capacity (503) and timeout (504) protection."""
    global _active_requests

    if _active_requests >= MAX_ACTIVE_REQUESTS:
        raise HTTPException(
            status_code=503,
            detail=f"Server at maximum concurrent capacity (active_requests={_active_requests})",
        )

    options = req.options
    dry_run = options.dry_run if options is not None else True
    version_str = options.algorithm_version if options is not None else None
    timeout_sec = (
        options.timeout_seconds
        if (options is not None and options.timeout_seconds is not None)
        else TEST_REQUEST_TIMEOUT_SECONDS
    )

    state_before = _prepare_simulated_state(req)
    working_state = state_before.model_copy(deep=True)
    engine = load_engine(version_str)

    _active_requests += 1
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
    finally:
        _active_requests = max(0, _active_requests - 1)

    execution_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
    turn_summary = build_turn_summary(state_before, state_after)

    evaluation = None
    if req.expected_outcome is not None:
        evaluation = evaluate_outcome(
            req.expected_outcome,
            state_before,
            state_after,
            turn_summary,
        )

    return StateTestResponse(
        test_id=req.test_id,
        success=True if evaluation is None else evaluation.passed,
        execution_time_ms=execution_time_ms,
        state=state_after,
        turn_summary=turn_summary,
        evaluation=evaluation,
    )


@router.post("/process-state", response_model=StateTestResponse)
async def process_state_endpoint(
    req: StateTestRequest,
    _auth: str = Depends(verify_test_access),
) -> StateTestResponse:
    """Execute a single turn against an injected AgentState and evaluate its action outcome."""
    return await _execute_single_state_test(req)


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
        actual_outcome = response.turn_summary.detected_outcome_type
        expected_outcome = (
            response.evaluation.expected_outcome_type
            if response.evaluation is not None
            else None
        )
        mismatches = response.evaluation.mismatches if response.evaluation else []
        level = "PASS" if passed else "FAIL"
        log_msg = (
            f"{level:<5} [req_{index:02d}] test_id=\"{test_id}\" | status={http_status} | "
            f"outcome={actual_outcome} | {response.execution_time_ms:.0f}ms"
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
        record = await _invoke_batch_item(idx, item_req)
        if not record["passed"]:
            state_tracker["aborted"] = True
        return record


async def _invoke_batch_item(idx: int, item_req: StateTestRequest) -> Dict[str, Any]:
    """Invoke _execute_single_state_test and convert any exception into a structured batch record."""
    item_start = time.perf_counter()
    try:
        resp = await _execute_single_state_test(item_req)
        return _build_batch_item_record(idx, item_req, resp, 200, None, 0.0)
    except HTTPException as http_exc:
        elapsed = (time.perf_counter() - item_start) * 1000.0
        return _build_batch_item_record(
            idx, item_req, None, http_exc.status_code, str(http_exc.detail), elapsed
        )
    except Exception as exc:
        elapsed = (time.perf_counter() - item_start) * 1000.0
        return _build_batch_item_record(idx, item_req, None, 500, str(exc), elapsed)


@router.post("/jobs", response_model=BatchTestJobResponse)
async def run_batch_test_job(
    batch_req: BatchTestJobRequest,
    _auth: str = Depends(verify_test_access),
) -> BatchTestJobResponse:
    """Execute a batch of StateTestRequest items and write structured logs to backend/test_jobs/."""
    global _job_counter
    if not batch_req.requests:
        raise HTTPException(status_code=400, detail="Batch job must include at least one request.")

    _job_counter += 1
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_id = f"{_job_counter:04d}_{timestamp_str}"
    job_dir = TEST_JOBS_DIR / f"job_{job_id}"

    concurrency = max(1, batch_req.concurrency)
    semaphore = asyncio.Semaphore(concurrency)
    state_tracker = {"aborted": False}

    log_lines: List[str] = [
        _format_log_line(
            f"INFO  Job #{job_id} started | total_requests={len(batch_req.requests)} | concurrency={concurrency}"
        )
    ]

    job_start = time.perf_counter()
    raw_records = await asyncio.gather(
        *[
            _execute_batch_item_safely(i, r, semaphore, batch_req.fail_fast, state_tracker)
            for i, r in enumerate(batch_req.requests, start=1)
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
    job_id: str,
    _auth: str = Depends(verify_test_access),
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
def run_tests(request: TestRunRequest) -> Dict[str, Any]:
    """Execute legacy contractor-intent test suite from TestingDashboard.jsx."""
    if not request.cases:
        raise HTTPException(status_code=400, detail="No test cases provided")

    engine = load_engine(ALGORITHM_VERSION)
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
    test_type_label = f"{request.test_type} ({ALGORITHM_VERSION})"
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
def get_history() -> List[Dict[str, Any]]:
    """Return historical test runs for TestingDashboard.jsx."""
    return get_test_runs()


@router.get("/runs/{run_id}")
def get_run_details(run_id: int) -> List[Dict[str, Any]]:
    """Return detailed test results for a specific historical run."""
    results = get_test_results_by_run(run_id)
    if not results:
        raise HTTPException(status_code=404, detail="Test run not found or no results")
    return results
