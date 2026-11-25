"""CLI Runner Script for Version-Agnostic Agent Testing Endpoints (/api/{version}/tests/*).

Every JSON file in `backend/tests/agent_cases/` represents a single request.
You can run a single request, or run a batch of many concurrent requests at once
using `--concurrency` and `--total-requests` to benchmark 503/504 limits.

Usage examples:
    # Run one single-turn test case:
    python scripts/run_test.py ask_additional_info

    # Run a single test case 20 times with 15 concurrent requests at once:
    python scripts/run_test.py ask_additional_info --concurrency 15 --total-requests 20

    # Run all single test cases in a batch with concurrency 8:
    python scripts/run_test.py all --concurrency 8 --total-requests 16
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
DEFAULT_VERSION = os.getenv("ALGORITHM_VERSION", "v1")


def list_available_tests() -> List[str]:
    """Return sorted single-request test names in backend/tests/agent_cases/."""
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


def print_single_result(test_name: str, status_code: int, data: Dict[str, Any]) -> bool:
    """Print formatted output for a single /process-state test run and return True if passed."""
    print(f"\n=== Single Test: {test_name} (HTTP {status_code}) ===")
    if status_code != 200:
        print(f"Status: FAILED (HTTP {status_code})")
        print(f"Detail: {data.get('detail', data)}")
        return False

    passed = bool(data.get("success", True))
    summary = data.get("turn_summary", {})
    evaluation = data.get("evaluation")

    status_label = "PASSED" if passed else "FAILED"
    print(f"Result          : {status_label}")
    print(f"Bot Version     : {data.get('version')}")
    print(f"Client ID       : {data.get('client_id')}")
    print(f"Execution Time  : {data.get('execution_time_ms')} ms")
    print(f"Detected Step   : {data.get('step')}")
    print(f"Expected Step   : {data.get('expected_step')}")
    print(f"Step Correct?   : {data.get('is_step_correct')}")
    print(f"Agent Reply     : {data.get('reply')}")

    tool_calls = summary.get("tool_calls_made") or []
    tool_names = [t.get("name") for t in tool_calls]
    print(f"Tools Called    : {tool_names if tool_names else 'None'}")

    if evaluation and not evaluation.get("passed", True):
        print("Mismatches:")
        for mismatch in evaluation.get("mismatches", []):
            print(f"  - {mismatch}")

    return passed


def print_batch_result(job_label: str, status_code: int, data: Dict[str, Any]) -> bool:
    """Print formatted output for a batch /jobs run and return True if passed."""
    print(f"\n=== Batch Job: {job_label} (HTTP {status_code}) ===")
    if status_code != 200:
        print(f"Status: FAILED (HTTP {status_code})")
        print(f"Detail: {data.get('detail', data)}")
        return False

    overall_status = data.get("status", "FAILED")
    print(f"Job ID          : {data.get('job_id')}")
    print(f"Bot Version     : {data.get('version')}")
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


def execute_single_test_file(
    client: httpx.Client,
    test_path: Path,
    base_url: str,
    headers: Dict[str, str],
    version: str,
) -> bool:
    """Load a single-request JSON test file and send it to POST /api/{version}/tests/process-state."""
    payload = json.loads(test_path.read_text(encoding="utf-8"))
    url = f"{base_url.rstrip('/')}/api/{version}/tests/process-state"

    try:
        response = client.post(url, json=payload, headers=headers)
    except httpx.RequestError as exc:
        print(f"\n[ERROR] Could not connect to live server at {url}: {exc}")
        return False

    try:
        resp_data = response.json()
    except Exception:
        resp_data = {"detail": response.text}

    return print_single_result(test_path.stem, response.status_code, resp_data)


def execute_batch_job(
    client: httpx.Client,
    test_cases: Optional[List[str]],
    base_url: str,
    headers: Dict[str, str],
    version: str,
    concurrency: int,
    total_requests: Optional[int],
) -> bool:
    """Trigger POST /api/{version}/tests/jobs to run many concurrent requests at once."""
    url = f"{base_url.rstrip('/')}/api/{version}/tests/jobs"
    label = ",".join(test_cases) if test_cases else "all_cases"
    batch_payload: Dict[str, Any] = {
        "job_name": f"batch_{label}",
        "concurrency": concurrency,
    }
    if test_cases:
        batch_payload["test_cases"] = test_cases
    if total_requests is not None:
        batch_payload["total_requests"] = total_requests

    try:
        response = client.post(url, json=batch_payload, headers=headers)
    except httpx.RequestError as exc:
        print(f"\n[ERROR] Could not connect to live server at {url}: {exc}")
        return False

    try:
        resp_data = response.json()
    except Exception:
        resp_data = {"detail": response.text}

    return print_batch_result(label, response.status_code, resp_data)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments for the test runner script."""
    parser = argparse.ArgumentParser(
        description="Trigger single or concurrent batch Agent Testing Endpoints against /api/{version}/tests/*."
    )
    parser.add_argument(
        "test_name",
        nargs="?",
        help="Name of a single test in backend/tests/agent_cases/ (e.g. 'ask_additional_info') or 'all'.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available single-request test cases in backend/tests/agent_cases/.",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_BASE_URL,
        help=f"Base URL of the running FastAPI server (default: {DEFAULT_BASE_URL}).",
    )
    parser.add_argument(
        "--api-key",
        default=DEFAULT_API_KEY,
        help="TEST_API_KEY for authenticating with /api/{version}/tests/* (defaults to TEST_API_KEY in .env).",
    )
    parser.add_argument(
        "--version",
        default=DEFAULT_VERSION,
        help=f"Bot engine version parameter in /api/{{version}}/tests/* (default: {DEFAULT_VERSION}).",
    )
    parser.add_argument(
        "--concurrency",
        "-c",
        type=int,
        default=None,
        help="Number of simultaneous requests to run at once via POST /api/{version}/tests/jobs.",
    )
    parser.add_argument(
        "--total-requests",
        "-n",
        type=int,
        default=None,
        help="Total number of requests to fire in a batch job (repeats the selected single test case(s)).",
    )
    parser.add_argument(
        "--client-id",
        "--user-id",
        dest="user_id",
        type=int,
        default=None,
        help="Client ID sent in 'Authorization: Bearer <client_id>' (default: 1).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for scripts/run_test.py."""
    args = parse_args(argv)

    if args.list or not args.test_name:
        tests = list_available_tests()
        print(f"Test directory: {AGENT_CASES_DIR}")
        print("Available single-request test cases:")
        for name in tests:
            print(f"  - {name}")
        if not args.test_name and not args.list:
            print("\nPass a test name to execute: python scripts/run_test.py <test_name>")
            return 1
        return 0

    client_id = args.user_id if args.user_id is not None else 1
    headers = {
        "X-Test-Api-Key": args.api_key,
        "Authorization": f"Bearer {client_id}",
    }

    use_batch = args.concurrency is not None or args.total_requests is not None

    with httpx.Client(timeout=300.0) as client:
        if use_batch:
            selected_cases = None if args.test_name.lower() == "all" else [args.test_name]
            passed = execute_batch_job(
                client=client,
                test_cases=selected_cases,
                base_url=args.url,
                headers=headers,
                version=args.version,
                concurrency=args.concurrency or 1,
                total_requests=args.total_requests,
            )
            return 0 if passed else 1

        if args.test_name.lower() == "all":
            test_paths = [AGENT_CASES_DIR / f"{name}.json" for name in list_available_tests()]
        else:
            try:
                test_paths = [resolve_test_path(args.test_name)]
            except FileNotFoundError as exc:
                print(f"[ERROR] {exc}")
                return 1

        all_passed = True
        for path in test_paths:
            if not execute_single_test_file(client, path, args.url, headers, args.version):
                all_passed = False

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
