"""Repository for managing prompts data."""
from backend.db.connection import get_db_connection

def create_project_prompt(project_id: int, category_id: int, contractor_id: int = None, prompt_text: str = None) -> int:
    """
    Create a new prompt linked to a project and return its ID.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO dbo.ProjectPrompts (project_id, category_id, contractor_id, prompt_text)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?)
        """, (project_id, category_id, contractor_id, prompt_text))

        prompt_id = cursor.fetchone()[0]

        conn.commit()
        cursor.close()
        conn.close()
        return prompt_id
    except Exception as e:
        print(f"Error creating prompt: {e}")
        return None
