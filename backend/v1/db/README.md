# Database Scripts

This directory contains utility scripts to manage the `HandymanDB` database in a Windows environment.

## Prerequisites

1. **Python & ODBC Driver**: Ensure you have Python installed, along with the required `pyodbc` package, and the Microsoft ODBC Driver for SQL Server installed on your Windows machine.
2. **Environment Variables**: Ensure your `.env` file at the root of the project contains the correct connection strings, particularly `MASTER_CONN_STR`, which is required to execute `BACKUP` and `RESTORE` commands.
3. **Permissions**: The SQL Server service account (e.g., `NT Service\MSSQLSERVER`, `NT Service\MSSQL$SQLEXPRESS`, or `NT AUTHORITY\NETWORK SERVICE`) must have **Read/Write** permissions to the project's root folder where the backup file (`HandymanDB.bak`) will be saved.

## Scripts

### 1. Initializing the Database (`init_db.py`)
Used to create the `HandymanDB` database, build its schema, and seed it with initial data.

**Usage (Run from project root):**
```powershell
python backend/v1/db/init_db.py
```

### 2. Backing up the Database (`backup_db.py`)
Creates a full backup of the existing `HandymanDB` and saves it as `HandymanDB.bak` in the root of the project.

**Usage (Run from project root):**
```powershell
python backend/v1/db/backup_db.py
```

### 3. Restoring the Database (`restore_db.py`)
Reads the `HandymanDB.bak` file from the project root and restores it as a brand-new database with the name format `HandymanDB_YYYYMMDD_HHMMSS`. The physical `.mdf` and `.ldf` files are automatically relocated/renamed to prevent conflicts with the original database.

**Usage (Run from project root):**
```powershell
python backend/v1/db/restore_db.py
```

## Troubleshooting Backup/Restore Errors

If you encounter an error like `Operating system error 5 (Access is denied.)` during backup or restore, it means the SQL Server engine does not have permission to write to or read from your project folder. 

**To fix this locally on Windows:**
1. Right-click your project folder in Windows Explorer and select **Properties**.
2. Go to the **Security** tab.
3. Click **Edit...** then **Add...**.
4. Type `Everyone` (or your specific SQL service account name) and click **Check Names**, then **OK**.
5. Grant **Full control** (or at least Read & Write) permissions.
6. Click **Apply** and **OK**, then run the script again.
