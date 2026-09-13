"""Repository for contractor data."""
from backend.db.connection import get_db_connection

def get_all_contractors():
    """
    Fetch all contractors from the database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, first_name, last_name, email, photo, description, created_at
        FROM dbo.contractor
        ORDER BY first_name, last_name
    """)
    rows = cursor.fetchall()

    contractors = []
    for row in rows:
        contractors.append({
            "id": row.id,
            "first_name": row.first_name,
            "last_name": row.last_name,
            "email": row.email,
            "photo": row.photo,
            "description": row.description,
            "created_at": row.created_at.isoformat() if row.created_at else None
        })

    cursor.close()
    conn.close()
    return contractors