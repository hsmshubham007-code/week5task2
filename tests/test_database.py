import sqlite3

import pytest

from src.database import DatabaseQueryError, run_query


def test_runs_select_query():
    result = run_query("SELECT COUNT(*) AS total FROM Customer")

    assert result["columns"] == ["total"]
    assert result["rows"] == [[59]]
    assert result["row_count"] == 1
    assert "LIMIT 100" in result["executed_sql"].upper()


def test_runs_join_query():
    result = run_query(
        """
        SELECT c.FirstName, c.LastName, COUNT(i.InvoiceId) AS invoice_count
        FROM Customer AS c
        JOIN Invoice AS i ON i.CustomerId = c.CustomerId
        GROUP BY c.CustomerId, c.FirstName, c.LastName
        ORDER BY invoice_count DESC
        LIMIT 3
        """
    )

    assert len(result["rows"]) == 3
    assert "invoice_count" in result["columns"]


def test_rejects_drop_before_execution():
    with pytest.raises(ValueError):
        run_query("DROP TABLE Customer")


def test_rejects_multiple_statements():
    with pytest.raises(ValueError):
        run_query("SELECT * FROM Customer; DROP TABLE Customer")


def test_rejects_writes_even_at_sqlite_level(tmp_path):
    database_path = tmp_path / "test.db"

    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE Customer (id INTEGER)")
        connection.execute("INSERT INTO Customer VALUES (1)")

    with pytest.raises(ValueError):
        run_query("DELETE FROM Customer", db_path=database_path)

    with sqlite3.connect(
        f"{database_path.as_uri()}?mode=ro", uri=True
    ) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM Customer"
        ).fetchone() == (1,)


def test_rejects_missing_database(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_query(
            "SELECT * FROM Customer",
            db_path=tmp_path / "missing.db",
        )


def test_rejects_zero_timeout():
    with pytest.raises(ValueError):
        run_query("SELECT * FROM Customer", timeout_seconds=0)
