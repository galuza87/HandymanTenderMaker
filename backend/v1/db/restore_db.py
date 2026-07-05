import pyodbc
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
MASTER_CONN_STR = os.getenv('MASTER_CONN_STR')

def restore_database():
    print("Connecting to SQL Server master database...")
    try:
        conn = pyodbc.connect(MASTER_CONN_STR, autocommit=True)
        cursor = conn.cursor()
        
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        backup_dir = os.path.join(project_root, 'backup')
        backup_file = os.path.join(backup_dir, 'HandymanDB.bak')
        
        # We can't rely on python os.path.exists if the SQL server is on another machine, 
        # but since DB_SERVER="localhost", we'll check just to provide a clear error message locally.
        if not os.path.exists(backup_file):
            print(f"Warning: Backup file not found locally at {backup_file}. If SQL Server is remote, it might still find it, but it's likely missing.")
            
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_db_name = f"HandymanDB_{date_str}"
        
        print(f"Restoring backup from {backup_file} to new database '{new_db_name}'...")
        
        # Get logical file names from backup to relocate them, otherwise SQL Server will try 
        # to overwrite the existing HandymanDB's physical files
        try:
            cursor.execute(f"RESTORE FILELISTONLY FROM DISK = '{backup_file}'")
            files = cursor.fetchall()
            
            restore_cmd = f"RESTORE DATABASE [{new_db_name}] FROM DISK = '{backup_file}' WITH "
            
            move_clauses = []
            for file_info in files:
                logical_name = file_info[0]
                physical_name = file_info[1]
                
                dir_name = os.path.dirname(physical_name)
                base_name, ext = os.path.splitext(os.path.basename(physical_name))
                new_physical_name = os.path.join(dir_name, f"{base_name}_{date_str}{ext}")
                
                move_clauses.append(f"MOVE '{logical_name}' TO '{new_physical_name}'")
                
            restore_cmd += ", ".join(move_clauses)
            
            cursor.execute(restore_cmd)
            print(f"Database restored successfully as '{new_db_name}'.")
            
        except pyodbc.Error as e:
            print(f"SQL Error: {e}", file=sys.stderr)
            sys.exit(1)
            
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error restoring database: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    restore_database()
