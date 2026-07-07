import pyodbc
import sys
import os
from dotenv import load_dotenv

load_dotenv()
MASTER_CONN_STR = os.getenv('MASTER_CONN_STR')

def backup_database():
    print("Connecting to SQL Server master database...")
    try:
        conn = pyodbc.connect(MASTER_CONN_STR, autocommit=True)
        cursor = conn.cursor()
        
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        backup_dir = os.path.join(project_root, 'backup')
        backup_file = os.path.join(backup_dir, 'HandymanDB.bak')
        
        print(f"Backing up HandymanDB to {backup_file}...")
        
        # Make sure directory exists (it should, since it's the project root)
        os.makedirs(backup_dir, exist_ok=True)
        
        cursor.execute(f"BACKUP DATABASE HandymanDB TO DISK = '{backup_file}' WITH FORMAT, MEDIANAME = 'SQLServerBackups', NAME = 'Full Backup of HandymanDB'")
        print("Backup completed successfully.")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error backing up database: {e}\nNote: The SQL Server service account needs write permissions to the destination folder.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    backup_database()
