"""Repository for category and contractor data."""
from backend.db.connection import get_db_connection


def get_all_categories():
    """
    Fetches all major categories.
    Returns a list of categories.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            id, 
            name, 
            description
        FROM dbo.major_category
        ORDER BY name
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    categories = []
    for row in rows:
        categories.append({
            "id": row.id,
            "name": row.name,
            "description": row.description
        })

    cursor.close()
    conn.close()
    return categories


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


def search_categories(search_query: str):
    """
    Search for major categories matching the search term.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    term = f"%{search_query}%"
    query = """
        SELECT id, name, description
        FROM dbo.major_category
        WHERE name LIKE ?
    """

    cursor.execute(query, (term,))
    rows = cursor.fetchall()

    results = []
    for row in rows:
        results.append({
            "id": row.id,
            "name": row.name,
            "description": row.description
        })

    cursor.close()
    conn.close()
    return results
