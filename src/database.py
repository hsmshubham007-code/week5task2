from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from src.sql_safety import DEFAULT_MAX_ROWS, validate_sql


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "chinook.db"
DEFAULT_TIMEOUT_SECONDS = 5


class DatabaseQueryError(RuntimeError):
    """Raised when a read-only database query cannot be completed."""


def _read_only_authorizer(
    action: int,
    arg1: str | None,
    arg2: str | None,
    database_name: str | None,
    trigger_name: str | None,
) -> int:
    """Add a SQLite-level defense against writes and administrative actions."""
    denied_actions = {
        sqlite3.SQLITE_INSERT,
        sqlite3.SQLITE_UPDATE,
        sqlite3.SQLITE_DELETE,
        sqlite3.SQLITE_CREATE_INDEX,
        sqlite3.SQLITE_CREATE_TABLE,
        sqlite3.SQLITE_CREATE_TEMP_INDEX,
        sqlite3.SQLITE_CREATE_TEMP_TABLE,
        sqlite3.SQLITE_CREATE_TEMP_TRIGGER,
        sqlite3.SQLITE_CREATE_TEMP_VIEW,
        sqlite3.SQLITE_CREATE_TRIGGER,
        sqlite3.SQLITE_CREATE_VIEW,
        sqlite3.SQLITE_DROP_INDEX,
        sqlite3.SQLITE_DROP_TABLE,
        sqlite3.SQLITE_DROP_TEMP_INDEX,
        sqlite3.SQLITE_DROP_TEMP_TABLE,
        sqlite3.SQLITE_DROP_TEMP_TRIGGER,
        sqlite3.SQLITE_DROP_TEMP_VIEW,
        sqlite3.SQLITE_DROP_TRIGGER,
        sqlite3.SQLITE_DROP_VIEW,
        sqlite3.SQLITE_ALTER_TABLE,
        sqlite3.SQLITE_ATTACH,
        sqlite3.SQLITE_DETACH,
        sqlite3.SQLITE_PRAGMA,
        sqlite3.SQLITE_TRANSACTION,
        sqlite3.SQLITE_SAVEPOINT,
        sqlite3.SQLITE_REINDEX,
        sqlite3.SQLITE_ANALYZE,
    }

    if action in denied_actions:
        return sqlite3.SQLITE_DENY

    # Prevent attempts to enable SQLite extension loading through SQL.
    if (
        action == sqlite3.SQLITE_FUNCTION
        and (arg2 or arg1 or "").lower() == "load_extension"
    ):
        return sqlite3.SQLITE_DENY

    return sqlite3.SQLITE_OK


def run_query(
    sql: str,
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    max_rows: int = DEFAULT_MAX_ROWS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Validate and execute a query against SQLite in read-only mode.

    Returns:
        A dictionary containing columns, rows, row_count, and executed_sql.

    Raises:
        ValueError: If the SQL or settings are invalid.
        DatabaseQueryError: If SQLite rejects the query or execution fails.
    """
    if timeout_seconds < 1:
        raise ValueError("timeout_seconds must be at least 1.")

    database_path = Path(db_path).resolve()

    if not database_path.is_file():
        raise FileNotFoundError(f"Database not found: {database_path}")

    # Validate and normalize SQL before opening a database connection.
    safe_sql = validate_sql(sql, max_rows=max_rows)

    database_uri = database_path.as_uri() + "?mode=ro"
    deadline = time.monotonic() + timeout_seconds

    try:
        with sqlite3.connect(
            database_uri,
            uri=True,
            timeout=timeout_seconds,
        ) as connection:
            connection.row_factory = None

            # Defense in depth: deny database modifications at SQLite level.
            connection.set_authorizer(_read_only_authorizer)

            # Interrupt expensive queries when the deadline is exceeded.
            def query_deadline_reached() -> int:
                return int(time.monotonic() >= deadline)

            connection.set_progress_handler(query_deadline_reached, 1000)

            cursor = connection.execute(safe_sql)
            columns = (
                [description[0] for description in cursor.description]
                if cursor.description
                else []
            )
            rows = [list(row) for row in cursor.fetchall()]

            if time.monotonic() >= deadline:
                raise DatabaseQueryError(
                    f"Query exceeded the {timeout_seconds}-second timeout."
                )

            return {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "executed_sql": safe_sql,
            }

    except (ValueError, FileNotFoundError, DatabaseQueryError):
        raise
    except sqlite3.Error as exc:
        message = str(exc)

        if "interrupted" in message.lower():
            message = (
                f"Query was interrupted; it may have exceeded the "
                f"{timeout_seconds}-second timeout."
            )

        raise DatabaseQueryError(message) from exc