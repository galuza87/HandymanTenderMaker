import pyodbc
import os

from dotenv import load_dotenv

load_dotenv()
DB_CONN_STR = os.getenv('DB_CONN_STR')

connection_string = DB_CONN_STR

def setup_clients_table():
    print("Connecting to SQL Server to create Clients and Offer_requests tables...")
    try:
        conn = pyodbc.connect(connection_string, autocommit=True)
        cursor = conn.cursor()

        # Create Clients table
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
            )
            PRINT 'Clients table created successfully.'
        END
        ELSE
        BEGIN
            PRINT 'Clients table already exists.'
        END
        """)

        # Create Offer_requests table
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Offer_requests' AND xtype='U')
        BEGIN
            CREATE TABLE Offer_requests (
                id INT IDENTITY(1,1) PRIMARY KEY,
                client_id INT FOREIGN KEY REFERENCES Clients(id),
                category NVARCHAR(100),
                subcategory NVARCHAR(100),
                deadline DATE,
                prompt_text NVARCHAR(MAX),
                created_at DATETIME DEFAULT GETDATE()
            )
            PRINT 'Offer_requests table created successfully.'
        END
        ELSE
        BEGIN
            PRINT 'Offer_requests table already exists.'
        END
        """)

        print("Database schema update completed!")
        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Error creating tables: {e}")

if __name__ == "__main__":
    setup_clients_table()
