import pytest

from src.schema_tools import get_distinct_values, inspect_schema


def test_inspect_schema_finds_related_tables():
    result = inspect_schema()

    assert result["table_count"] >= 5

    tables = {item["table"]: item for item in result["tables"]}
    assert "Customer" in tables
    assert "Invoice" in tables

    customer_columns = {
        column["name"] for column in tables["Customer"]["columns"]
    }
    assert "CustomerId" in customer_columns

    customer_foreign_keys = tables["Customer"]["foreign_keys"]
    assert any(
        key["referenced_table"] == "Employee"
        for key in customer_foreign_keys
    )


def test_get_distinct_genres():
    result = get_distinct_values("Genre", "Name")

    assert result["count"] > 0
    assert "Rock" in result["values"]


def test_fuzzy_search_finds_country():
    result = get_distinct_values(
        "Customer",
        "Country",
        search="canad",
    )

    assert result["values"] == ["Canada"]


def test_rejects_unknown_table():
    with pytest.raises(ValueError, match="Unknown table"):
        get_distinct_values("MissingTable", "Name")


def test_rejects_unknown_column():
    with pytest.raises(ValueError, match="Unknown column"):
        get_distinct_values("Customer", "MissingColumn")


def test_rejects_invalid_limit():
    with pytest.raises(ValueError, match="limit"):
        get_distinct_values("Genre", "Name", limit=0)


def test_value_search_is_parameterized():
    result = get_distinct_values(
        "Customer",
        "Country",
        search="' OR 1=1 --",
    )

    assert result["values"] == []
