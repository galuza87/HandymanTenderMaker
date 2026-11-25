"""Backward-compatible re-export of the version-agnostic testing router."""

from backend.routes.testing import (  # noqa: F401
    ALGORITHM_VERSION,
    ENABLE_TEST_ENDPOINTS,
    TEST_JOBS_DIR,
    TestCase,
    TestRunRequest,
    get_batch_test_job,
    get_history,
    get_run_details,
    load_engine,
    process_state_endpoint,
    router,
    run_batch_test_job,
    run_tests,
    verify_test_access,
)
