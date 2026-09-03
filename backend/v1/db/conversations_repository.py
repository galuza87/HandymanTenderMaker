"""Repository for conversation state data."""
import json
from backend.v1.db.connection import get_db_connection


def save_conversation(session_id: str, client_id: int, state_json: str, is_finished: bool):
    """
    Save or update a conversation state in the database.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if conversation exists
        cursor.execute("SELECT SESSION_ID FROM dbo.Conversations WHERE SESSION_ID = ?", (session_id,))
        if cursor.fetchone():
            cursor.execute("""
                UPDATE dbo.Conversations 
                SET CLIENT_ID = ?, STATE_JSON = ?, IS_FINISHED = ?, UPDATED_AT = GETDATE()
                WHERE SESSION_ID = ?
            """, (client_id, state_json, 1 if is_finished else 0, session_id))
        else:
            cursor.execute("""
                INSERT INTO dbo.Conversations (SESSION_ID, CLIENT_ID, STATE_JSON, IS_FINISHED)
                VALUES (?, ?, ?, ?)
            """, (session_id, client_id, state_json, 1 if is_finished else 0))

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error saving conversation: {e}")


def get_conversation(session_id: str):
    """
    Fetch a conversation state by session ID.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT STATE_JSON FROM dbo.Conversations WHERE SESSION_ID = ?", (session_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row and row.STATE_JSON:
            return json.loads(row.STATE_JSON)
        return None
    except Exception as e:
        print(f"Error getting conversation: {e}")
        return None


def get_conversations_by_client_id(client_id: int):
    """Fetch all conversations for a specific client."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT SESSION_ID, STATE_JSON, IS_FINISHED, CREATED_AT, UPDATED_AT
            FROM dbo.Conversations
            WHERE CLIENT_ID = ?
            ORDER BY UPDATED_AT DESC
        """, (client_id,))
        rows = cursor.fetchall()

        conversations = []
        for row in rows:
            state_data = json.loads(row.STATE_JSON) if row.STATE_JSON else {}
            # Extract a snippet from messages for the preview
            messages = state_data.get("messages", [])
            last_message = ""
            if messages:
                # find last human message or any message
                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        last_message = msg.get("content", "")[:100]
                        break
                if not last_message:
                    last_message = messages[-1].get("content", "")[:100]

            conversations.append({
                "session_id": row.SESSION_ID,
                "is_finished": bool(row.IS_FINISHED),
                "created_at": row.CREATED_AT.isoformat() if row.CREATED_AT else None,
                "updated_at": row.UPDATED_AT.isoformat() if row.UPDATED_AT else None,
                "last_message": last_message
            })

        cursor.close()
        conn.close()
        return conversations
    except Exception as e:
        print(f"Error fetching conversations for client: {e}")
        return []
