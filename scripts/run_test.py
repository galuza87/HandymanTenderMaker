"""CLI Runner Script for Agent Testing Endpoints.

Usage examples:
    python scripts/run_test.py ask_additional_info
    python scripts/run_test.py tool_use_categories --version v1
    python scripts/run_test.py batch_smoke_suite --concurrency 2
    python scripts/run_test.py all
    python scripts/run_test.py --list
"""

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

from dotenv import find_dotenv, load_dotenv
import httpx

load_dotenv(find_dotenv())

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENT_CASES_DIR = PROJECT_ROOT / "backend" / "tests" / "agent_cases"
DEFAULT_BASE_URL = os.getenv("TEST_SERVER_URL", "http://localhost:8000")
DEFAULT_API_KEY = os.getenv("TEST_API_KEY", "dev-test-api-key")


def list_available_tests() -> List[str]:
    """Return sorted test names (without .json extension) in backend/tests/agent_cases/."""
    if not AGENT_CASES_DIR.exists():
        return []
    return sorted(p.stem for p in AGENT_CASES_DIR.glob("*.json"))


def resolve_test_path(test_name: str) -> Path:
    """Resolve a test name or path to a JSON file in backend/tests/agent_cases/."""
    direct_path = Path(test_name)
    if direct_path.is_file():
        return direct_path

    filename = test_name if test_name.endswith(".json") else f"{test_name}.json"
    candidate = AGENT_CASES_DIR / filename
    if candidate.is_file():
        return candidate

    available = ", ".join(list_available_tests()) or "none"
    raise FileNotFoundError(
        f"Test '{test_name}' not found in {AGENT_CASES_DIR}.\nAvailable tests: {available}"
    )


def apply_overrides(
    payload: Dict[str, Any],
    is_batch: bool,
    version: Optional[str],
    concurrency: Optional[int],
    user_id: Optional[int],
) -> Dict[str, Any]:
    """Apply optional CLI overrides (algorithm_version, concurrency, simulated_user_id)."""
    if is_batch:
        if concurrency is not None:
            payload["concurrency"] = concurrency
        for req in payload.get("requests", []):
            if user_id is not None:
                req["simulated_user_id"] = user_id
            if version is not None:
                req.setdefault("options", {})["algorithm_version"] = version
    else:
        if user_id is not None:
            payload["simulated_user_id"] = user_id
        if version is not None:
            payload.setdefault("options", {})["algorithm_version"] = version
    return payload


def print_single_result(test_name: str, status_code: int, data: Dict[str, Any]) -> bool:
    """Print formatted output for a single /process-state test run and return True if passed."""
    print(f"\n=== Single Test: {test_name} (HTTP {status_code}) ===")
    if status_code != 200:
        print(f"Status: FAILED (HTTP {status_code})")
        print(f"Detail: {data.get('detail', data)}")
        return False

    passed = bool(data.get("success", True))
    summary = data.get("turn_summary", {})
    state = data.get("state", {})
    evaluation = data.get("evaluation")

    status_label = "PASSED" if passed else "FAILED"
    print(f"Result          : {status_label}")
    print(f"Execution Time  : {data.get('execution_time_ms')} ms")
    print(f"Action Detected : {summary.get('detected_outcome_type')}")
    print(f"Next Node/Step  : {state.get('next_step')}")
    print(f"Is Finished     : {state.get('is_finished')}")

    tool_calls = summary.get("tool_calls_made") or []
    tool_names = [t.get("name") for t in tool_calls]
    print(f"Tools Called    : {tool_names if tool_names else 'None'}")

    if evaluation and not evaluation.get("passed", True):
        print("Mismatches:")
        for mismatch in evaluation.get("mismatches", []):
            print(f"  - {mismatch}")

    return passed


def print_batch_result(test_name: str, status_code: int, data: Dict[str, Any]) -> bool:
    """Print formatted output for a batch /jobs run and return True if passed."""
    print(f"\n=== Batch Job: {test_name} (HTTP {status_code}) ===")
    if status_code != 200:
        print(f"Status: FAILED (HTTP {status_code})")
        print(f"Detail: {data.get('detail', data)}")
        return False

    overall_status = data.get("status", "FAILED")
    print(f"Job ID          : {data.get('job_id')}")
    print(f"Overall Status  : {overall_status}")
    print(f"Passed / Total  : {data.get('passed')}/{data.get('total_requests')} (Failed: {data.get('failed')})")
    print(f"Concurrency     : {data.get('concurrency')}")
    print(f"Total Time      : {data.get('total_execution_time_ms')} ms (Avg: {data.get('avg_execution_time_ms')} ms)")
    print(f"HTTP Breakdown  : {data.get('status_code_breakdown')}")
    print(f"Job Logs Dir    : {data.get('job_dir')}")

    failed_reqs = data.get("failed_requests") or []
    if failed_reqs:
        print("\nFailed Requests Breakdown:")
        for item in failed_reqs:
            reason = item.get("error") or "; ".join(item.get("mismatches") or [])
            print(f"  - [{item.get('test_id')}] HTTP {item.get('http_status')}: {reason}")

    return overall_status == "PASSED"


def execute_test_file(
    client: httpx.Client,
    test_path: Path,
    base_url: str,
    headers: Dict[str, str],
    version: Optional[str],
    concurrency: Optional[int],
    user_id: Optional[int],
) -> bool:
    """Load a JSON test file, call the live server endpoint, and print the outcome."""
    raw_payload = json.loads(test_path.read_text(encoding="utf-8"))
    is_batch = "requests" in raw_payload
    payload = apply_overrides(raw_payload, is_batch, version, concurrency, user_id)

    endpoint = "/api/v1/tests/jobs" if is_batch else "/api/v1/tests/process-state"
    url = f"{base_url.rstrip('/')}{endpoint}"

    try:
        response = client.post(url, json=payload, headers=headers)
    except httpx.RequestError as exc:
        print(f"\n[ERROR] Could not connect to live server at {url}: {exc}")
        print("Make sure the FastAPI server is running (e.g. `python -m backend.main`).")
        return False

    try:
        resp_data = response.json()
    except Exception:
        resp_data = {"detail": response.text}

    if is_batch:
        return print_batch_result(test_path.stem, response.status_code, resp_data)
    return print_single_result(test_path.stem, response.status_code, resp_data)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments for the test runner script."""
    parser = argparse.ArgumentParser(
        description="Trigger single or batch Agent Testing Endpoints against the live FastAPI server."
    )
    parser.add_argument(
        "test_name",
        nargs="?",
        help="Name of the test in backend/tests/agent_cases/ (e.g. 'ask_additional_info', 'batch_smoke_suite', or 'all').",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available test cases in backend/tests/agent_cases/.",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_BASE_URL,
        help=f"Base URL of the running FastAPI server (default: {DEFAULT_BASE_URL}).",
    )
    parser.add_argument(
        "--api-key",
        default=DEFAULT_API_KEY,
        help="TEST_API_KEY for authenticating with /api/v1/tests/* (defaults to TEST_API_KEY in .env).",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Override options.algorithm_version (e.g. 'v1' or 'v2').",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Override concurrency level for batch jobs.",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=None,
        help="Override simulated_user_id (must exist in dbo.Clients).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for scripts/run_test.py."""
    args = parse_args(argv)

    if args.list or not args.test_name:
        tests = list_available_tests()
        print(f"Test directory: {AGENT_CASES_DIR}")
        print("Available tests:")
        for name in tests:
            print(f"  - {name}")
        if not args.test_name and not args.list:
            print("\nPass a test name to execute: python scripts/run_test.py <test_name>")
            return 1
        return 0

    headers = {
        "X-Test-Api-Key": args.api_key,
        "Authorization": f"Bearer {args.api_key}",
    }

    if args.test_name.lower() == "all":
        test_paths = [AGENT_CASES_DIR / f"{name}.json" for name in list_available_tests()]
    else:
        try:
            test_paths = [resolve_test_path(args.test_name)]
        except FileNotFoundError as exc:
            print(f"[ERROR] {exc}")
            return 1

    all_passed = True
    with httpx.Client(timeout=300.0) as client:
        for path in test_paths:
            passed = execute_test_file(
                client=client,
                test_path=path,
                base_url=args.url,
                headers=headers,
                version=args.version,
                concurrency=args.concurrency,
                user_id=args.user_id,
            )
            if not passed:
                all_passed = False

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
