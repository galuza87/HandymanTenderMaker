import pyodbc

from config import DB_CONN_STR


def create_table():
    conn = pyodbc.connect(DB_CONN_STR)
    cursor = conn.cursor()
    
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Prompts' AND xtype='U')
        CREATE TABLE dbo.Prompts (
            id INT IDENTITY(1,1) PRIMARY KEY,
            date DATETIME DEFAULT GETDATE(),
            ip NVARCHAR(50),
            prompt NVARCHAR(MAX)
        )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    print("Prompts table created successfully.")

if __name__ == "__main__":
    create_table()
