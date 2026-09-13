"""Repository for contractor data."""
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
