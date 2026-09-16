"""Repository for managing prompts data."""
from backend.db.connection import get_db_connection
import json
from typing import List, Optional

def create_project_prompt(project_id: int, category_id: int, prompt_text: str = None, embedding: Optional[List[float]] = None) -> int:
    """
    Create a new prompt linked to a project and return its ID.
    Supports inserting an optional embedding vector.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if embedding:
            embedding_str = json.dumps(embedding)
            cursor.execute("""
                INSERT INTO dbo.ProjectPrompts (project_id, category_id, prompt_text, embedding)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, CAST(CAST(? AS VARCHAR(MAX)) AS VECTOR(384)))
            """, (project_id, category_id, prompt_text, embedding_str))
        else:
            cursor.execute("""
                INSERT INTO dbo.ProjectPrompts (project_id, category_id, prompt_text)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?)
            """, (project_id, category_id, prompt_text))

        prompt_id = cursor.fetchone()[0]

        conn.commit()
        cursor.close()
        conn.close()
        return prompt_id
    except Exception as e:
        print(f"Error creating prompt: {e}")
        return None

def get_similar_prompts_comments(category_id: int, embedding: List[float], limit: int = 3) -> List[str]:
    """
    Search for similar past tenders in the same category using VECTOR_DISTANCE and return their comments.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        embedding_str = json.dumps(embedding)
        
        cursor.execute("""
            SELECT TOP (?) comments
            FROM dbo.ProjectPrompts
            WHERE category_id = ? 
              AND comments IS NOT NULL 
              AND LEN(LTRIM(RTRIM(comments))) > 0
              AND embedding IS NOT NULL
            ORDER BY VECTOR_DISTANCE('cosine', embedding, CAST(CAST(? AS VARCHAR(MAX)) AS VECTOR(384)))
        """, (limit, category_id, embedding_str))
        
        rows = cursor.fetchall()
        comments = [row[0] for row in rows if row[0]]
        
        cursor.close()
        conn.close()
        return comments
    except Exception as e:
        print(f"Error finding similar prompts: {e}")
        return []
