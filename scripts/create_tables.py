import pyodbc
import sys
import os
from dotenv import load_dotenv

# Search for and load the .env file in parent directories
load_dotenv()

DB_CONN_STR = os.getenv('DB_CONN_STR')
MASTER_CONN_STR = os.getenv('MASTER_CONN_STR')

def create_database():
    print("Connecting to SQL Server master database to check/create HandymanDB...")
    try:
        # Autocommit=True is required to execute CREATE DATABASE statement
        conn = pyodbc.connect(MASTER_CONN_STR, autocommit=True)
        cursor = conn.cursor()
        
        # Check if HandymanDB exists
        cursor.execute("SELECT database_id FROM sys.databases WHERE name = 'HandymanDB'")
        row = cursor.fetchone()
        if row:
            print("Database 'HandymanDB' already exists.")
        else:
            print("Creating database 'HandymanDB'...")
            cursor.execute("CREATE DATABASE HandymanDB")
            print("Database 'HandymanDB' created successfully.")
            
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error checking or creating database: {e}", file=sys.stderr)
        sys.exit(1)

def build_schema():
    print("Connecting to HandymanDB to initialize tables...")
    try:
        conn = pyodbc.connect(DB_CONN_STR, autocommit=True)
        cursor = conn.cursor()
        
        # 1. Create major_category table
        print("Creating 'major_category' table...")
        cursor.execute("""
            IF OBJECT_ID('dbo.major_category', 'U') IS NULL
            BEGIN
                CREATE TABLE dbo.major_category (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    name NVARCHAR(100) NOT NULL UNIQUE,
                    description NVARCHAR(255) NULL
                );
                PRINT 'major_category table created.';
            END
            ELSE
            BEGIN
                PRINT 'major_category table already exists.';
            END
        """)

        # 2. Create contractor table
        print("Creating 'contractor' table...")
        cursor.execute("""
            IF OBJECT_ID('dbo.contractor', 'U') IS NULL
            BEGIN
                CREATE TABLE dbo.contractor (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    first_name NVARCHAR(50) NOT NULL,
                    last_name NVARCHAR(50) NOT NULL,
                    email NVARCHAR(100) NOT NULL UNIQUE,
                    photo NVARCHAR(500) NULL,
                    description NVARCHAR(MAX) NULL,
                    created_at DATETIME DEFAULT GETDATE()
                );
                PRINT 'contractor table created.';
            END
            ELSE
            BEGIN
                PRINT 'contractor table already exists.';
            END
        """)

        # 3. Create Clients table
        print("Creating 'Clients' table...")
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Clients' AND xtype='U')
            BEGIN
                CREATE TABLE Clients (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    name NVARCHAR(150),
                    phone NVARCHAR(50),
                    email NVARCHAR(150),
                    address NVARCHAR(250),
                    created_at DATETIME DEFAULT GETDATE()
                );
                PRINT 'Clients table created.';
            END
            ELSE
            BEGIN
                PRINT 'Clients table already exists.';
            END
        """)

        # 4. Create PROJECTS table
        print("Creating 'PROJECTS' table...")
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='PROJECTS' AND xtype='U')
            BEGIN
                CREATE TABLE dbo.PROJECTS (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    CLIENT_ID INT FOREIGN KEY REFERENCES dbo.Clients(id),
                    general_description NVARCHAR(MAX) NULL,
                    STATUS_ID INT NULL,
                    ADDRESS_ID INT NULL,
                    comments NVARCHAR(MAX) NULL,
                    created_date DATETIME DEFAULT GETDATE()
                );
                PRINT 'PROJECTS table created.';
            END
            ELSE
            BEGIN
                PRINT 'PROJECTS table already exists.';
            END
        """)

        # 5. Create ProjectPrompts table
        print("Creating 'ProjectPrompts' table...")
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='ProjectPrompts' AND xtype='U')
            BEGIN
                CREATE TABLE dbo.ProjectPrompts (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    project_id INT FOREIGN KEY REFERENCES dbo.PROJECTS(id),
                    category_id INT FOREIGN KEY REFERENCES dbo.major_category(id),
                    contractor_id INT FOREIGN KEY REFERENCES dbo.contractor(id) NULL,
                    prompt_text NVARCHAR(MAX) NOT NULL,
                    created_at DATETIME DEFAULT GETDATE()
                );
                PRINT 'ProjectPrompts table created.';
            END
            ELSE
            BEGIN
                PRINT 'ProjectPrompts table already exists.';
            END
        """)

        # 6. Create Conversations table
        print("Creating 'Conversations' table...")
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Conversations' AND xtype='U')
            BEGIN
                CREATE TABLE dbo.Conversations (
                    SESSION_ID NVARCHAR(100) PRIMARY KEY,
                    CLIENT_ID INT NULL,
                    STATE_JSON NVARCHAR(MAX),
                    IS_FINISHED BIT DEFAULT 0,
                    CREATED_AT DATETIME DEFAULT GETDATE(),
                    UPDATED_AT DATETIME DEFAULT GETDATE()
                );
                PRINT 'Conversations table created.';
            END
            ELSE
            BEGIN
                PRINT 'Conversations table already exists.';
            END
        """)
        
        print("Database structure created successfully!")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error creating tables: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    create_database()
    build_schema()
