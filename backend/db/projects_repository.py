"""Repository for project data."""
from backend.db.connection import get_db_connection


def create_project(client_id: int, description: str, status_id: int = None, address_id: int = None, comments: str = None) -> int:
    """
    Create a new project and return its ID.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO dbo.PROJECTS (CLIENT_ID, general_description, STATUS_ID, ADDRESS_ID, comments)
            OUTPUT INSERTED.ID
            VALUES (?, ?, ?, ?, ?)
        """, (client_id, description, status_id, address_id, comments))

        project_id = cursor.fetchone()[0]

        conn.commit()
        cursor.close()
        conn.close()
        return project_id
    except Exception as e:
        print(f"Error creating project: {e}")
        return None


def get_projects_by_client_id(client_id: int):
    """
    Fetches all projects and their subtasks for a specific client.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.ID as project_id, p.created_date, p.general_description,
                   pr.id as prompt_id, pr.category_id, pr.prompt_text, mc.name as category_name
            FROM dbo.PROJECTS p
            LEFT JOIN dbo.ProjectPrompts pr ON p.ID = pr.project_id
            LEFT JOIN dbo.major_category mc ON pr.category_id = mc.id
            WHERE p.CLIENT_ID = ?
            ORDER BY p.created_date DESC
        """, (client_id,))

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        projects = {}
        for row in rows:
            pid = row.project_id
            if pid not in projects:
                projects[pid] = {
                    "id": pid,
                    "created_date": row.created_date.isoformat() if row.created_date else None,
                    "description": row.general_description,
                    "prompts": []
                }
            if row.prompt_id:
                projects[pid]["prompts"].append({
                    "id": row.prompt_id,
                    "category": row.category_name,
                    "prompt_text": row.prompt_text
                })

        return list(projects.values())
    except Exception as e:
        print(f"Error fetching projects for client: {e}")
        return []
