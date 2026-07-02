import pyodbc
from dotenv import load_dotenv
import os

load_dotenv()

# Build connection string dynamically from individual variables if they exist,
# otherwise fallback to DB_CONN_STR.
db_driver = os.getenv('DB_DRIVER')
db_server = os.getenv('DB_SERVER')
db_name = os.getenv('DB_NAME')
db_trusted = os.getenv('DB_TRUSTED_CONNECTION', 'yes')
db_trust_cert = os.getenv('DB_TRUST_SERVER_CERTIFICATE', 'yes')

if db_driver and db_server and db_name:
    DB_CONN_STR = f"DRIVER={db_driver};SERVER={db_server};DATABASE={db_name};Trusted_Connection={db_trusted};TrustServerCertificate={db_trust_cert};"
else:
    DB_CONN_STR = os.getenv('DB_CONN_STR')

def get_db_connection():
    """
    Establishes and returns a connection to the HandymanDB.
    """
    return pyodbc.connect(DB_CONN_STR)

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
    Fetches all contractors from the database.
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
    Searches for major categories or subcategories matching the search term.
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

def insert_prompt_log(ip: str, prompt: str):
    """
    Saves the prompt sent to the LLM into the Prompts table for debugging.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO dbo.Prompts (ip, prompt) VALUES (?, ?)", (ip, prompt))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error logging prompt to DB: {e}")

def save_client_and_offer(client_info: dict, offer_details: dict, prompt_text: str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insert client
        cursor.execute("""
            INSERT INTO dbo.Clients (name, phone, email, address)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?)
        """, (
            client_info.get('name', ''),
            client_info.get('phone', ''),
            client_info.get('email', ''),
            client_info.get('address', '')
        ))
        client_id = cursor.fetchone()[0]
        
        # Process deadline: if 'asap' or similar, use today
        deadline_raw = offer_details.get('timeframe', offer_details.get('deadline', ''))
        deadline_date = None
        if 'asap' in deadline_raw.lower() or 'soon' in deadline_raw.lower() or 'today' in deadline_raw.lower():
            from datetime import date
            deadline_date = date.today().isoformat()
            
        category = offer_details.get('major_category', offer_details.get('project_type', ''))
        subcategory = ""
        
        cursor.execute("""
            INSERT INTO dbo.Offer_requests (client_id, category, subcategory, deadline, prompt_text)
            VALUES (?, ?, ?, ?, ?)
        """, (client_id, category, subcategory, deadline_date, prompt_text))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving client and offer request: {e}")
        return False
