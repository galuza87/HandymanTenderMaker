import pyodbc
import sys
import os
from dotenv import load_dotenv

load_dotenv()
DB_CONN_STR = os.getenv('DB_CONN_STR')

def drop_obsolete_tables():
    print("Connecting to HandymanDB to clean up obsolete tables...")
    try:
        conn = pyodbc.connect(DB_CONN_STR, autocommit=True)
        cursor = conn.cursor()
        
        tables_to_drop = [
            "SUB_TASKS",
            "test_SUB_TASKS",
            "SUB_category",
            "Offer_requests",
            "Prompts"  # The old Prompts table, since we use ProjectPrompts now
        ]
        
        for table in tables_to_drop:
            print(f"Checking if '{table}' exists...")
            cursor.execute(f"IF OBJECT_ID('dbo.{table}', 'U') IS NOT NULL DROP TABLE dbo.{table};")
            print(f"Dropped '{table}' if it existed.")
            
        print("Cleanup completed successfully!")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error dropping tables: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    drop_obsolete_tables()
