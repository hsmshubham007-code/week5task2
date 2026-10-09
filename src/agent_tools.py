from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from src.calculator import calculate
from src.database import run_query
from src.schema_tools import get_distinct_values, inspect_schema


@tool
def inspect_database_schema() -> str:
    """Inspect database tables, columns, and foreign-key relationships."""
    try:
        return json.dumps(inspect_schema(), indent=2, default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


@tool
def search_database_values(
    table: str,
    column: str,
    search: str = "",
) -> str:
    """Find distinct values in a database column, including partial text matches."""
    try:
        result = get_distinct_values(
            table=table,
            column=column,
            search=search or None,
            limit=20,
        )
        return json.dumps(result, indent=2, default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


@tool
def execute_readonly_sql(sql: str) -> str:
    """Execute a read-only SQLite SELECT query and return columns and result rows."""
    try:
        result = run_query(sql)
        return json.dumps(result, indent=2, default=str)
    except Exception as exc:
        # Return the database error to the agent so it can correct its SQL.
        return json.dumps(
            {
                "error": str(exc),
                "executed_sql": sql,
                "hint": "Review the schema and database error, then retry with corrected SELECT SQL.",
            },
            indent=2,
            default=str,
        )


@tool
def arithmetic_calculator(expression: str) -> str:
    """Safely calculate a basic arithmetic expression."""
    try:
        return json.dumps(calculate(expression), indent=2, default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc)})