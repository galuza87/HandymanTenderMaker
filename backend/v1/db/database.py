"""Database compatibility layer.

This module re-exports functions from domain-specific repositories to maintain
backward compatibility with existing imports while the database layer is
refactored into single-responsibility modules.

For new code, prefer importing directly from the specific repository modules:
  - backend.v1.db.connection
  - backend.v1.db.categories_repository
  - backend.v1.db.clients_repository
  - backend.v1.db.conversations_repository
  - backend.v1.db.projects_repository
  - backend.v1.db.subtasks_repository
  - backend.v1.db.tests_repository
"""

from backend.v1.db.connection import get_db_connection, DB_CONN_STR
from backend.v1.db.categories_repository import (
    get_all_categories_with_subs,
    get_all_contractors,
    search_categories_and_subs,
)
from backend.v1.db.clients_repository import (
    get_client_by_phone,
    get_client_by_id,
    create_client,
    update_client,
    get_main_address_by_client_id,
)
from backend.v1.db.projects_repository import (
    create_project,
    get_projects_by_client_id,
)
from backend.v1.db.conversations_repository import (
    save_conversation,
    get_conversation,
    get_conversations_by_client_id,
)
from backend.v1.db.tests_repository import (
    insert_test_run,
    insert_test_result,
    get_test_runs,
    get_test_results_by_run,
)
from backend.v1.db.subtasks_repository import (
    create_sub_task,
    log_test_sub_task,
)
from backend.v1.db.init_db import init_db

__all__ = [
    "get_db_connection",
    "DB_CONN_STR",
    "get_all_categories_with_subs",
    "get_all_contractors",
    "search_categories_and_subs",
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
    "create_sub_task",
    "log_test_sub_task",
    "init_db",
]

