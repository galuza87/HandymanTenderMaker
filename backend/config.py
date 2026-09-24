import os
from dotenv import load_dotenv, find_dotenv

# Search for and load the .env file in parent directories
load_dotenv(find_dotenv())


def build_db_conn_str() -> str:
    """Build the SQL Server connection string from environment variables.

    This keeps the dynamic assembly in one place and allows the app to
    prefer an explicit DB_CONN_STR when the environment provides one.
    """
    db_conn_str = os.getenv("DB_CONN_STR")
    if db_conn_str:
        return db_conn_str

    db_driver = os.getenv("DB_DRIVER", "{ODBC Driver 18 for SQL Server}")
    db_server = os.getenv("DB_SERVER", "localhost")
    db_name = os.getenv("DB_NAME", "HandymanDB")
    db_trusted = os.getenv("DB_TRUSTED_CONNECTION", "yes")
    db_trust_cert = os.getenv("DB_TRUST_SERVER_CERTIFICATE", "yes")

    return (
        f"DRIVER={db_driver};"
        f"SERVER={db_server};"
        f"DATABASE={db_name};"
        f"Trusted_Connection={db_trusted};"
        f"TrustServerCertificate={db_trust_cert};"
    )


# Database Config
DB_DRIVER = os.getenv("DB_DRIVER", "{ODBC Driver 18 for SQL Server}")
DB_SERVER = os.getenv("DB_SERVER", "localhost")
DB_NAME = os.getenv("DB_NAME", "HandymanDB")
DB_TRUSTED_CONNECTION = os.getenv("DB_TRUSTED_CONNECTION", "yes")
DB_TRUST_SERVER_CERTIFICATE = os.getenv("DB_TRUST_SERVER_CERTIFICATE", "yes")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Database Connection Strings
DB_CONN_STR = build_db_conn_str()
MASTER_CONN_STR = os.getenv("MASTER_CONN_STR")

# LM Studio Config
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
LM_STUDIO_API_KEY = os.getenv("LM_STUDIO_API_KEY", "lm-studio")

# LangSmith / LangChain tracing config
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT") or os.getenv("LANGCHAIN_ENDPOINT")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT") or os.getenv("LANGCHAIN_PROJECT")
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", str(LANGCHAIN_TRACING_V2)).lower() == "true"

# Backward-compatible aliases for LangChain SDKs
LANGCHAIN_API_KEY = LANGSMITH_API_KEY
LANGCHAIN_PROJECT = LANGSMITH_PROJECT
LANGCHAIN_ENDPOINT = LANGSMITH_ENDPOINT

# --- Langsmith - Online eval: sample rates and annotation queue IDs ---
DATA_VALIDATOR_SAMPLE_RATE=1.0
DATA_VALIDATOR_GOOD_QUEUE_ID=os.getenv("DATA_VALIDATOR_GOOD_QUEUE_ID")
DATA_VALIDATOR_CORRECTION_QUEUE_ID=os.getenv("DATA_VALIDATOR_CORRECTION_QUEUE_ID")

CATEGORIZER_SAMPLE_RATE=1.0
CATEGORIZER_GOOD_QUEUE_ID=os.getenv("CATEGORIZER_GOOD_QUEUE_ID")
CATEGORIZER_CORRECTION_QUEUE_ID=os.getenv("CATEGORIZER_CORRECTION_QUEUE_ID")

CONTRACTOR_CATEGORIZER_SAMPLE_RATE=1.0
CONTRACTOR_CATEGORIZER_GOOD_QUEUE_ID=os.getenv("CONTRACTOR_CATEGORIZER_GOOD_QUEUE_ID")
CONTRACTOR_CATEGORIZER_CORRECTION_QUEUE_ID=os.getenv("CONTRACTOR_CATEGORIZER_CORRECTION_QUEUE_ID")

MULTI_TASK_ARCHITECT_SAMPLE_RATE=1.0
MULTI_TASK_ARCHITECT_GOOD_QUEUE_ID=os.getenv("MULTI_TASK_ARCHITECT_GOOD_QUEUE_ID")
MULTI_TASK_ARCHITECT_CORRECTION_QUEUE_ID=os.getenv("MULTI_TASK_ARCHITECT_CORRECTION_QUEUE_ID")

INFORMATION_GATHERER_SAMPLE_RATE=1.0
INFORMATION_GATHERER_GOOD_QUEUE_ID=os.getenv("INFORMATION_GATHERER_GOOD_QUEUE_ID")
INFORMATION_GATHERER_CORRECTION_QUEUE_ID=os.getenv("INFORMATION_GATHERER_CORRECTION_QUEUE_ID")

TENDER_CREATOR_SAMPLE_RATE=1.0
TENDER_CREATOR_GOOD_QUEUE_ID=os.getenv("TENDER_CREATOR_GOOD_QUEUE_ID")
TENDER_CREATOR_CORRECTION_QUEUE_ID=os.getenv("TENDER_CREATOR_CORRECTION_QUEUE_ID")

# --- Groq
GROQ_API_KEY=os.getenv("GROQ_API_KEY")
