"""Repository for category and contractor data."""
from backend.v1.db.connection import get_db_connection


def get_all_categories_with_subs():
    """
    Fetches all major categories with their child subcategories.
    Returns a dictionary grouped by major category.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            mc.id AS mc_id, 
            mc.name AS mc_name, 
            mc.description AS mc_desc,
            sc.id AS sc_id, 
            sc.name AS sc_name, 
            sc.brand AS sc_brand
        FROM dbo.major_category mc
        LEFT JOIN dbo.sub_category sc ON mc.id = sc.major_category_id
        ORDER BY mc.name, sc.name, sc.brand
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    categories = {}
    for row in rows:
        mc_id = row.mc_id
        mc_name = row.mc_name
        mc_desc = row.mc_desc
        sc_id = row.sc_id
        sc_name = row.sc_name
        sc_brand = row.sc_brand

        if mc_id not in categories:
            categories[mc_id] = {
                "id": mc_id,
                "name": mc_name,
                "description": mc_desc,
                "subcategories": []
            }

        if sc_id is not None:
            categories[mc_id]["subcategories"].append({
                "id": sc_id,
                "name": sc_name,
                "brand": sc_brand
            })

    cursor.close()
    conn.close()
    return list(categories.values())


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


def search_categories_and_subs(search_query: str):
    """
    Search for major categories or subcategories matching the search term.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    term = f"%{search_query}%"
    query = """
        SELECT DISTINCT mc.id, mc.name, mc.description
        FROM dbo.major_category mc
        LEFT JOIN dbo.sub_category sc ON mc.id = sc.major_category_id
        WHERE mc.name LIKE ? OR sc.name LIKE ? OR sc.brand LIKE ?
    """

    cursor.execute(query, (term, term, term))
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
