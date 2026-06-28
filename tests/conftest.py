import sys
from pathlib import Path

# conftest.py is automatically loaded by pytest before running tests.
# Add project root once for all tests
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))