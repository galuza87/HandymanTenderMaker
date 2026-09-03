"""Database connection management."""
import pyodbc
import os
from dotenv import load_dotenv

load_dotenv()


def get_db_connection_string() -> str:
    """Build the SQL Server connection string from environment variables.

    Prefers explicit individual variables if available.
    """
    db_conn_str = os.getenv("DB_CONN_STR")

    db_driver = os.getenv("DB_DRIVER")
    db_server = os.getenv("DB_SERVER")
    db_name = os.getenv("DB_NAME")
    db_trusted = os.getenv("DB_TRUSTED_CONNECTION", "yes")
    db_trust_cert = os.getenv("DB_TRUST_SERVER_CERTIFICATE", "yes")

    if db_driver and db_server and db_name:
        print("Creating the DB string dynamically")
        db_conn_str = f"DRIVER={db_driver};SERVER={db_server};DATABASE={db_name};Trusted_Connection={db_trusted};TrustServerCertificate={db_trust_cert};"
    if db_conn_str:
        return db_conn_str
    else:
        raise ValueError("Cannot construct DB connection: missing DRIVER, SERVER, or NAME")

DB_CONN_STR = get_db_connection_string()

def get_db_connection():
    """Establish and return a connection to the HandymanDB."""
    print(DB_CONN_STR)
    return pyodbc.connect(DB_CONN_STR)
