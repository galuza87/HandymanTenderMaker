"""Repository for test run and result data."""
from backend.v1.db.connection import get_db_connection


def insert_test_run(test_type: str, accuracy: float, avg_time: float) -> int:
    """
    Insert a test run record and return its ID.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dbo.TestRuns (TestType, OverallAccuracy, AverageExecutionTime)
            OUTPUT INSERTED.RunID
            VALUES (?, ?, ?)
        """, (test_type, accuracy, avg_time))
        run_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        return run_id
    except Exception as e:
        print(f"Error inserting test run: {e}")
        return None


def insert_test_result(run_id: int, input_text: str, expected: str, actual: str, exec_time: float, is_correct: bool):
    """
    Insert a test result record for a given test run.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dbo.TestResults (RunID, InputText, ExpectedOutcome, ActualOutcome, ExecutionTimeMs, IsCorrect)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (run_id, input_text, expected, actual, exec_time, is_correct))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error inserting test result: {e}")


def get_test_runs():
    """
    Fetch all test runs, ordered by most recent first.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT RunID, Timestamp, TestType, OverallAccuracy, AverageExecutionTime FROM dbo.TestRuns ORDER BY Timestamp DESC")
        rows = cursor.fetchall()
        runs = []
        for row in rows:
            runs.append({
                "RunID": row.RunID,
                "Timestamp": row.Timestamp.isoformat() if row.Timestamp else None,
                "TestType": row.TestType,
                "OverallAccuracy": row.OverallAccuracy,
                "AverageExecutionTime": row.AverageExecutionTime
            })
        cursor.close()
        conn.close()
        return runs
    except Exception as e:
        print(f"Error fetching test runs: {e}")
        return []


def get_test_results_by_run(run_id: int):
    """
    Fetch all test results for a specific test run.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ResultID, InputText, ExpectedOutcome, ActualOutcome, ExecutionTimeMs, IsCorrect FROM dbo.TestResults WHERE RunID = ?", (run_id,))
        rows = cursor.fetchall()
        results = []
        for row in rows:
            results.append({
                "ResultID": row.ResultID,
                "InputText": row.InputText,
                "ExpectedOutcome": row.ExpectedOutcome,
                "ActualOutcome": row.ActualOutcome,
                "ExecutionTimeMs": row.ExecutionTimeMs,
                "IsCorrect": bool(row.IsCorrect)
            })
        cursor.close()
        conn.close()
        return results
    except Exception as e:
        print(f"Error fetching test results: {e}")
        return []
