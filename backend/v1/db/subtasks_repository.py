"""Repository for subtask data."""
from backend.v1.db.connection import get_db_connection


def create_sub_task(project_id: int, category_id: int, status_id: int = None, contractor_id: int = None, tender_id: int = None, comments: str = None) -> int:
    """
    Create a new sub task under a project and return its ID.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO dbo.SUB_TASKS (PROJECT_ID, CATEGORY_ID, SUBTASK_STATUS_ID, CONTRACTOR_ID, TENDER_ID, comments)
            OUTPUT INSERTED.ID
            VALUES (?, ?, ?, ?, ?, ?)
        """, (project_id, category_id, status_id, contractor_id, tender_id, comments))

        sub_task_id = cursor.fetchone()[0]

        conn.commit()
        cursor.close()
        conn.close()
        return sub_task_id
    except Exception as e:
        print(f"Error creating sub task: {e}")
        return None


def log_test_sub_task(session_id: str, category_id: int, comments: str = None):
    """
    Log the AI node evaluation into the TEST_SUB_TASKS table.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO dbo.TEST_SUB_TASKS (SESSION_ID, CATEGORY_ID, comments)
            VALUES (?, ?, ?)
        """, (session_id, category_id, comments))

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error logging to TEST_SUB_TASKS: {e}")
