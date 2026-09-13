"""Database compatibility layer.

This module re-exports functions from domain-specific repositories to maintain
backward compatibility with existing imports while the database layer is
refactored into single-responsibility modules.

For new code, prefer importing directly from the specific repository modules:
  - backend.db.connection
  - backend.db.categories_repository
  - backend.db.clients_repository
  - backend.db.conversations_repository
  - backend.db.projects_repository
  - backend.db.subtasks_repository
  - backend.db.tests_repository
"""

from backend.db.connection import get_db_connection, DB_CONN_STR
from backend.db.categories_repository import (
    get_all_categories,
    search_categories,
)
from backend.db.contractors_repository import (
    get_all_contractors
)
from backend.db.clients_repository import (
    get_client_by_phone,
    get_client_by_id,
    create_client,
    update_client,
    get_main_address_by_client_id,
)
from backend.db.projects_repository import (
    create_project,
    get_projects_by_client_id,
)
from backend.db.conversations_repository import (
    save_conversation,
    get_conversation,
    get_conversations_by_client_id,
)
from backend.db.tests_repository import (
    insert_test_run,
    insert_test_result,
    get_test_runs,
    get_test_results_by_run,
)
from backend.db.prompts_repository import (
    create_project_prompt,
)

__all__ = [
    "get_db_connection",
    "DB_CONN_STR",
    "get_all_categories",
    "get_all_contractors",
    "search_categories",
    "get_client_by_phone",
    "get_client_by_id",
    "create_client",
    "update_client",
    "get_main_address_by_client_id",
    "create_project",
    "get_projects_by_client_id",
    "save_conversation",
    "get_conversation",
    "get_conversations_by_client_id",
    "insert_test_run",
    "insert_test_result",
    "get_test_runs",
    "get_test_results_by_run",
    "create_project_prompt",
]

