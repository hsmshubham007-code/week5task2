from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from src.database import DEFAULT_DB_PATH


DEFAULT_VALUE_LIMIT = 20


def _connect_read_only(db_path: Path | str = DEFAULT_DB_PATH):
    """Open an existing SQLite database in read-only mode."""
    database_path = Path(db_path).resolve()

    if not database_path.is_file():
        raise FileNotFoundError(f"Database not found: {database_path}")

    uri = database_path.as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5)
    connection.execute("PRAGMA query_only = ON")
    return connection


def _quote_identifier(identifier: str) -> str:
    """Safely quote a SQLite table or column identifier."""
    return '"' + identifier.replace('"', '""') + '"'


def inspect_schema(
    db_path: Path | str = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """Return table names, columns, and foreign-key relationships."""
    with _connect_read_only(db_path) as connection:
        table_rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        tables = []

        for (table_name,) in table_rows:
            quoted_table = _quote_identifier(table_name)

            column_rows = connection.execute(
                f"PRAGMA table_info({quoted_table})"
            ).fetchall()

            foreign_key_rows = connection.execute(
                f"PRAGMA foreign_key_list({quoted_table})"
            ).fetchall()

            tables.append(
                {
                    "table": table_name,
                    "columns": [
                        {
                            "name": row[1],
                            "type": row[2],
                            "not_null": bool(row[3]),
                            "primary_key": bool(row[5]),
                        }
                        for row in column_rows
                    ],
                    "foreign_keys": [
                        {
                            "column": row[3],
                            "referenced_table": row[2],
                            "referenced_column": row[4],
                        }
                        for row in foreign_key_rows
                    ],
                }
            )

        return {
            "table_count": len(tables),
            "tables": tables,
        }


def get_distinct_values(
    table: str,
    column: str,
    search: str | None = None,
    limit: int = DEFAULT_VALUE_LIMIT,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """Return distinct values for a real table and column.

    An optional case-insensitive substring search helps find values when
    the user's wording differs slightly from the stored database value.
    """
    if not isinstance(table, str) or not table.strip():
        raise ValueError("table must be a non-empty string.")

    if not isinstance(column, str) or not column.strip():
        raise ValueError("column must be a non-empty string.")

    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer.")

    # Keep output bounded regardless of the requested limit.
    limit = min(limit, DEFAULT_VALUE_LIMIT)

    with _connect_read_only(db_path) as connection:
        table_rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            """
        ).fetchall()

        actual_tables = {row[0] for row in table_rows}

        if table not in actual_tables:
            raise ValueError(f"Unknown table: {table}")

        quoted_table = _quote_identifier(table)

        column_rows = connection.execute(
            f"PRAGMA table_info({quoted_table})"
        ).fetchall()

        actual_columns = {row[1] for row in column_rows}

        if column not in actual_columns:
            raise ValueError(f"Unknown column '{column}' in table '{table}'.")

        quoted_column = _quote_identifier(column)

        sql = (
            f"SELECT DISTINCT {quoted_column} "
            f"FROM {quoted_table} "
            f"WHERE {quoted_column} IS NOT NULL"
        )
        parameters: list[Any] = []

        if search is not None and search.strip():
            sql += f" AND CAST({quoted_column} AS TEXT) LIKE ? COLLATE NOCASE"
            parameters.append(f"%{search.strip()}%")

        sql += f" ORDER BY {quoted_column} LIMIT ?"
        parameters.append(limit)

        rows = connection.execute(sql, parameters).fetchall()
        values = [row[0] for row in rows]

        return {
            "table": table,
            "column": column,
            "search": search,
            "values": values,
            "count": len(values),
            "limit": limit,
        }