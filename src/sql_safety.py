
from __future__ import annotations

import sqlglot
from sqlglot import exp


DEFAULT_MAX_ROWS = 100

# These statement types must never be executable by the agent.
FORBIDDEN_NODE_NAMES = {
    "Alter",
    "Command",
    "Commit",
    "Copy",
    "Create",
    "Delete",
    "Drop",
    "Insert",
    "Merge",
    "Pragma",
    "Rollback",
    "Set",
    "Transaction",
    "TruncateTable",
    "Update",
    "Use",
}


def validate_sql(sql: str, max_rows: int = DEFAULT_MAX_ROWS) -> str:
    """Validate one read-only SELECT query and enforce a maximum result size.

    Returns normalized SQLite SQL. Raises ValueError for unsafe or invalid SQL.
    This function validates SQL; it does not execute it.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("SQL query must be a non-empty string.")

    if max_rows < 1:
        raise ValueError("max_rows must be at least 1.")

    try:
        statements = sqlglot.parse(sql, read="sqlite")
    except sqlglot.errors.ParseError as exc:
        raise ValueError(f"SQL syntax is invalid: {exc}") from exc

    # Reject multiple statements, including a valid SELECT followed by DROP.
    statements = [statement for statement in statements if statement is not None]
    if len(statements) != 1:
        raise ValueError("Exactly one SQL statement is allowed.")

    query = statements[0]

    # Only SELECT queries are allowed. WITH ... SELECT is also supported
    # because SQLGlot represents it as a Select expression with a WITH clause.
    if not isinstance(query, exp.Select):
        raise ValueError("Only read-only SELECT queries are allowed.")

    # Reject write or administrative operations anywhere in the parsed tree.
    for node in query.walk():
        if type(node).__name__ in FORBIDDEN_NODE_NAMES:
            raise ValueError(
                f"Unsafe SQL operation is not allowed: {type(node).__name__}."
            )

    # Apply the row cap to the outer query.
    current_limit = query.args.get("limit")

    if current_limit is None:
        query.set(
            "limit",
            exp.Limit(expression=exp.Literal.number(max_rows)),
        )
    else:
        limit_expression = current_limit.expression

        # Only preserve a simple integer limit when it is within the cap.
        if (
            isinstance(limit_expression, exp.Literal)
            and not limit_expression.is_string
            and limit_expression.this.isdigit()
        ):
            requested_limit = int(limit_expression.this)
            if requested_limit > max_rows:
                current_limit.set(
                    "expression",
                    exp.Literal.number(max_rows),
                )
        else:
            # Avoid accepting a dynamic or otherwise non-literal outer limit.
            current_limit.set(
                "expression",
                exp.Literal.number(max_rows),
            )

    return query.sql(dialect="sqlite")