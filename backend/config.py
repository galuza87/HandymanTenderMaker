import os
from dotenv import load_dotenv, find_dotenv

# Search for and load the .env file in parent directories
load_dotenv(find_dotenv())

# Database Config
DB_DRIVER = os.getenv("DB_DRIVER", "{ODBC Driver 18 for SQL Server}")
DB_SERVER = os.getenv("DB_SERVER", "localhost")
DB_NAME = os.getenv("DB_NAME", "HandymanDB")
DB_TRUSTED_CONNECTION = os.getenv("DB_TRUSTED_CONNECTION", "yes")
DB_TRUST_SERVER_CERTIFICATE = os.getenv("DB_TRUST_SERVER_CERTIFICATE", "yes")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Build Database Connection Strings
if DB_USER and DB_PASSWORD:
    # SQL Server Authentication
    DB_CONN_STR = (
        f"DRIVER={DB_DRIVER};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_NAME};"
        f"UID={DB_USER};"
        f"PWD={DB_PASSWORD};"
        f"TrustServerCertificate={DB_TRUST_SERVER_CERTIFICATE};"
    )
    MASTER_CONN_STR = (
        f"DRIVER={DB_DRIVER};"
        f"SERVER={DB_SERVER};"
        f"DATABASE=master;"
        f"UID={DB_USER};"
        f"PWD={DB_PASSWORD};"
        f"TrustServerCertificate={DB_TRUST_SERVER_CERTIFICATE};"
    )
else:
    # Windows Authentication (Trusted Connection)
    DB_CONN_STR = (
        f"DRIVER={DB_DRIVER};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_NAME};"
        f"Trusted_Connection={DB_TRUSTED_CONNECTION};"
        f"TrustServerCertificate={DB_TRUST_SERVER_CERTIFICATE};"
    )
    MASTER_CONN_STR = (
        f"DRIVER={DB_DRIVER};"
        f"SERVER={DB_SERVER};"
        f"DATABASE=master;"
        f"Trusted_Connection={DB_TRUSTED_CONNECTION};"
        f"TrustServerCertificate={DB_TRUST_SERVER_CERTIFICATE};"
    )

# LM Studio Config
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
LM_STUDIO_API_KEY = os.getenv("LM_STUDIO_API_KEY", "lm-studio")
