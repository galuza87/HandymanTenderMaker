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

def init_db():
    """
    Initializes the required database tables if they do not exist.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create CLIENTS table
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Clients' and xtype='U')
        CREATE TABLE dbo.Clients (
            id INT IDENTITY(1,1) PRIMARY KEY,
            name NVARCHAR(150),
            last_name NVARCHAR(150),
            phone NVARCHAR(50),
            additional_phone NVARCHAR(50),
            email NVARCHAR(150),
            created_at DATETIME DEFAULT GETDATE()
        )
    """)
    
    # Ensure new columns exist if the table was created previously without them
    cursor.execute("""
        IF COL_LENGTH('dbo.Clients', 'last_name') IS NULL
        BEGIN
            ALTER TABLE dbo.Clients ADD last_name NVARCHAR(150)
        END
        
        IF COL_LENGTH('dbo.Clients', 'additional_phone') IS NULL
        BEGIN
            ALTER TABLE dbo.Clients ADD additional_phone NVARCHAR(50)
        END
        
        IF COL_LENGTH('dbo.Clients', 'address') IS NOT NULL
        BEGIN
            ALTER TABLE dbo.Clients DROP COLUMN address
        END
    """)

    # Create Addresses table
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Addresses' and xtype='U')
        CREATE TABLE dbo.Addresses (
            ID INT IDENTITY(1,1) PRIMARY KEY,
            address_text NVARCHAR(250),
            IS_MAIN_ADDRESS BIT DEFAULT 0,
            Project_id INT
        )
    """)
    
    # Create Client_Address table
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Client_Address' and xtype='U')
        CREATE TABLE dbo.Client_Address (
            CLIENT_ID INT,
            ADDRESS_ID INT,
            PRIMARY KEY (CLIENT_ID, ADDRESS_ID),
            FOREIGN KEY (CLIENT_ID) REFERENCES dbo.Clients(id),
            FOREIGN KEY (ADDRESS_ID) REFERENCES dbo.Addresses(ID)
        )
    """)
    
    # Create PROJECTS table
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='PROJECTS' and xtype='U')
        CREATE TABLE dbo.PROJECTS (
            ID INT IDENTITY(1,1) PRIMARY KEY,
            CLIENT_ID INT,
            created_date DATETIME DEFAULT GETDATE(),
            general_description NVARCHAR(MAX),
            STATUS_ID INT,
            ADDRESS_ID INT,
            comments NVARCHAR(MAX)
        )
    """)
    
    # Create SUB_TASKS table
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='SUB_TASKS' and xtype='U')
        CREATE TABLE dbo.SUB_TASKS (
            ID INT IDENTITY(1,1) PRIMARY KEY,
            PROJECT_ID INT,
            CATEGORY_ID INT,
            SUBTASK_STATUS_ID INT,
            CONTRACTOR_ID INT,
            TENDER_ID INT,
            comments NVARCHAR(MAX),
            FOREIGN KEY (PROJECT_ID) REFERENCES dbo.PROJECTS(ID),
            FOREIGN KEY (CATEGORY_ID) REFERENCES dbo.major_category(id)
        )
    """)
    # Create TEST_SUB_TASKS table for AI logging
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='TEST_SUB_TASKS' and xtype='U')
        CREATE TABLE dbo.TEST_SUB_TASKS (
            ID INT IDENTITY(1,1) PRIMARY KEY,
            SESSION_ID NVARCHAR(255),
            PROJECT_ID INT,
            CATEGORY_ID INT,
            CONFIDENCE_SCORE FLOAT,
            SUBTASK_STATUS_ID INT,
            CONTRACTOR_ID INT,
            TENDER_ID INT,
            comments NVARCHAR(MAX),
            created_at DATETIME DEFAULT GETDATE()
        )
    """)
    
    # Create TestRuns table
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='TestRuns' and xtype='U')
        CREATE TABLE dbo.TestRuns (
            RunID INT IDENTITY(1,1) PRIMARY KEY,
            Timestamp DATETIME DEFAULT GETDATE(),
            TestType NVARCHAR(100),
            OverallAccuracy FLOAT,
            AverageExecutionTime FLOAT
        )
    """)
    
    # Create TestResults table
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='TestResults' and xtype='U')
        CREATE TABLE dbo.TestResults (
            ResultID INT IDENTITY(1,1) PRIMARY KEY,
            RunID INT,
            InputText NVARCHAR(MAX),
            ExpectedOutcome NVARCHAR(100),
            ActualOutcome NVARCHAR(100),
            ExecutionTimeMs FLOAT,
            IsCorrect BIT,
            FOREIGN KEY (RunID) REFERENCES dbo.TestRuns(RunID)
        )
    """)
    
    # Ensure ConfidenceScore column exists
    cursor.execute("""
        IF COL_LENGTH('dbo.TestResults', 'ConfidenceScore') IS NULL
        BEGIN
            ALTER TABLE dbo.TestResults ADD ConfidenceScore FLOAT DEFAULT 0.0
        END
    """)
    
    conn.commit()
    cursor.close()
    conn.close()

def create_project(client_id: int, description: str, status_id: int = None, address_id: int = None, comments: str = None) -> int:
    """
    Creates a new project and returns its ID.
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

def create_sub_task(project_id: int, category_id: int, status_id: int = None, contractor_id: int = None, tender_id: int = None, comments: str = None) -> int:
    """
    Creates a new sub task under a project and returns its ID.
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

def log_test_sub_task(session_id: str, category_id: int, confidence_score: float, comments: str = None):
    """
    Logs the AI node evaluation into the TEST_SUB_TASKS table.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO dbo.TEST_SUB_TASKS (SESSION_ID, CATEGORY_ID, CONFIDENCE_SCORE, comments)
            VALUES (?, ?, ?, ?)
        """, (session_id, category_id, confidence_score, comments))
        
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error logging to TEST_SUB_TASKS: {e}")

def get_client_by_phone(phone: str):
    """
    Fetches a client by their primary phone number.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, c.name, c.last_name, c.phone, c.additional_phone, c.email,
                   (SELECT TOP 1 a.address_text FROM dbo.Addresses a 
                    JOIN dbo.Client_Address ca ON a.ID = ca.ADDRESS_ID 
                    WHERE ca.CLIENT_ID = c.id ORDER BY a.IS_MAIN_ADDRESS DESC, a.ID ASC) as address
            FROM dbo.Clients c 
            WHERE c.phone = ?
        """, (phone,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            return {
                "id": row.id,
                "name": row.name,
                "last_name": row.last_name,
                "phone": row.phone,
                "additional_phone": row.additional_phone,
                "email": row.email,
                "address": row.address
            }
        return None
    except Exception as e:
        print(f"Error fetching client by phone: {e}")
        return None

def get_client_by_id(client_id: int):
    """
    Fetches a client by their ID.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, c.name, c.last_name, c.phone, c.additional_phone, c.email,
                   (SELECT TOP 1 a.address_text FROM dbo.Addresses a 
                    JOIN dbo.Client_Address ca ON a.ID = ca.ADDRESS_ID 
                    WHERE ca.CLIENT_ID = c.id ORDER BY a.IS_MAIN_ADDRESS DESC, a.ID ASC) as address
            FROM dbo.Clients c 
            WHERE c.id = ?
        """, (client_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            return {
                "id": row.id,
                "name": row.name,
                "last_name": row.last_name,
                "phone": row.phone,
                "additional_phone": row.additional_phone,
                "email": row.email,
                "address": row.address
            }
        return None
    except Exception as e:
        print(f"Error fetching client by ID: {e}")
        return None

def create_client(name: str, last_name: str, phone: str, additional_phone: str, email: str, address: str = None):
    """
    Creates a new client and returns their ID.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dbo.Clients (name, last_name, phone, additional_phone, email)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?)
        """, (name, last_name, phone, additional_phone, email))
        client_id = cursor.fetchone()[0]
        
        if address:
            cursor.execute("""
                INSERT INTO dbo.Addresses (address_text, IS_MAIN_ADDRESS)
                OUTPUT INSERTED.ID
                VALUES (?, 1)
            """, (address,))
            address_id = cursor.fetchone()[0]
            
            cursor.execute("""
                INSERT INTO dbo.Client_Address (CLIENT_ID, ADDRESS_ID)
                VALUES (?, ?)
            """, (client_id, address_id))

        conn.commit()
        cursor.close()
        conn.close()
        return client_id
    except Exception as e:
        print(f"Error creating client: {e}")
        return None

def update_client(client_id: int, name: str, last_name: str, additional_phone: str, email: str, address: str = None):
    """
    Updates an existing client's details.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE dbo.Clients
            SET name = ?, last_name = ?, additional_phone = ?, email = ?
            WHERE id = ?
        """, (name, last_name, additional_phone, email, client_id))
        
        if address:
            cursor.execute("""
                SELECT a.ID FROM dbo.Addresses a
                JOIN dbo.Client_Address ca ON a.ID = ca.ADDRESS_ID
                WHERE ca.CLIENT_ID = ? AND a.address_text = ?
            """, (client_id, address))
            existing_address = cursor.fetchone()
            
            if not existing_address:
                cursor.execute("""
                    INSERT INTO dbo.Addresses (address_text, IS_MAIN_ADDRESS)
                    OUTPUT INSERTED.ID
                    VALUES (?, 0)
                """, (address,))
                address_id = cursor.fetchone()[0]
                
                cursor.execute("""
                    INSERT INTO dbo.Client_Address (CLIENT_ID, ADDRESS_ID)
                    VALUES (?, ?)
                """, (client_id, address_id))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating client: {e}")
        return False

def get_projects_by_client_id(client_id: int):
    """
    Fetches all projects and their subtasks for a specific client.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.ID as project_id, p.created_date, p.general_description,
                   s.ID as subtask_id, s.CATEGORY_ID, s.comments, mc.name as category_name
            FROM dbo.PROJECTS p
            LEFT JOIN dbo.SUB_TASKS s ON p.ID = s.PROJECT_ID
            LEFT JOIN dbo.major_category mc ON s.CATEGORY_ID = mc.id
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
                    "subtasks": []
                }
            if row.subtask_id:
                projects[pid]["subtasks"].append({
                    "id": row.subtask_id,
                    "category": row.category_name,
                    "comments": row.comments
                })
                
        return list(projects.values())
    except Exception as e:
        print(f"Error fetching projects for client: {e}")
        return []

def get_main_address_by_client_id(client_id: int):
    """
    Fetches the main address for a given client ID.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT TOP 1 a.address_text 
            FROM dbo.Addresses a 
            JOIN dbo.Client_Address ca ON a.ID = ca.ADDRESS_ID 
            WHERE ca.CLIENT_ID = ? 
            ORDER BY a.IS_MAIN_ADDRESS DESC, a.ID ASC
        """, (client_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        print(f"Error fetching main address for client: {e}")
        return None
def insert_test_run(test_type: str, accuracy: float, avg_time: float) -> int:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dbo.TestRuns (TestType, OverallAccuracy, AverageExecutionTime)
            OUTPUT INSERTED.RunID
            VALUES (?, ?, ?)
        """, (test_type, accuracy, avg_time))
        run_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        return run_id
    except Exception as e:
        print(f"Error inserting test run: {e}")
        return None

def insert_test_result(run_id: int, input_text: str, expected: str, actual: str, exec_time: float, is_correct: bool, confidence_score: float = 0.0):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dbo.TestResults (RunID, InputText, ExpectedOutcome, ActualOutcome, ExecutionTimeMs, IsCorrect, ConfidenceScore)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (run_id, input_text, expected, actual, exec_time, is_correct, confidence_score))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error inserting test result: {e}")

def get_test_runs():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT RunID, Timestamp, TestType, OverallAccuracy, AverageExecutionTime FROM dbo.TestRuns ORDER BY Timestamp DESC")
        rows = cursor.fetchall()
        runs = []
        for row in rows:
            runs.append({
                "RunID": row.RunID,
                "Timestamp": row.Timestamp.isoformat() if row.Timestamp else None,
                "TestType": row.TestType,
                "OverallAccuracy": row.OverallAccuracy,
                "AverageExecutionTime": row.AverageExecutionTime
            })
        cursor.close()
        conn.close()
        return runs
    except Exception as e:
        print(f"Error fetching test runs: {e}")
        return []

def get_test_results_by_run(run_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ResultID, InputText, ExpectedOutcome, ActualOutcome, ExecutionTimeMs, IsCorrect, ConfidenceScore FROM dbo.TestResults WHERE RunID = ?", (run_id,))
        rows = cursor.fetchall()
        results = []
        for row in rows:
            results.append({
                "ResultID": row.ResultID,
                "InputText": row.InputText,
                "ExpectedOutcome": row.ExpectedOutcome,
                "ActualOutcome": row.ActualOutcome,
                "ExecutionTimeMs": row.ExecutionTimeMs,
                "IsCorrect": bool(row.IsCorrect),
                "ConfidenceScore": row.ConfidenceScore if hasattr(row, 'ConfidenceScore') else 0.0
            })
        cursor.close()
        conn.close()
        return results
    except Exception as e:
        print(f"Error fetching test results: {e}")
        return []
