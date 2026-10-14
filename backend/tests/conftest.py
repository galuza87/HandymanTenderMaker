import pytest
from fastapi.testclient import TestClient
import sys
import os

# Ensure the root project directory (containing 'backend') is in the python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.main import app

@pytest.fixture
def client():
    """
    Creates a FastAPI TestClient fixture for our tests.
    Since we are testing against the development database, this will 
    connect to the live Dev DB just like the normal app does.
    """
    with TestClient(app) as client:
        yield client
