import pytest

from src.sql_safety import validate_sql


def test_allows_simple_select():
    sql = validate_sql("SELECT Name FROM Artist")
    assert sql.upper().startswith("SELECT")
    assert "LIMIT 100" in sql.upper()


def test_allows_with_query():
    sql = validate_sql(
        "WITH artist_counts AS "
        "(SELECT ArtistId, COUNT(*) AS total FROM Album GROUP BY ArtistId) "
        "SELECT * FROM artist_counts"
    )
    assert sql.upper().startswith("WITH")
    assert "LIMIT 100" in sql.upper()


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE Artist",
        "DELETE FROM Artist",
        "UPDATE Artist SET Name = 'Changed'",
        "INSERT INTO Artist (Name) VALUES ('Changed')",
        "CREATE TABLE test_table (id INTEGER)",
        "SELECT * FROM Artist; DROP TABLE Artist",
        "PRAGMA table_info('Artist')",
    ],
)
def test_rejects_unsafe_sql(sql):
    with pytest.raises(ValueError):
        validate_sql(sql)


def test_caps_large_limit():
    sql = validate_sql("SELECT * FROM Artist LIMIT 10000", max_rows=25)
    assert "LIMIT 25" in sql.upper()


def test_keeps_smaller_limit():
    sql = validate_sql("SELECT * FROM Artist LIMIT 10", max_rows=25)
    assert "LIMIT 10" in sql.upper()


def test_rejects_empty_sql():
    with pytest.raises(ValueError):
        validate_sql("")


def test_rejects_invalid_sql():
    with pytest.raises(ValueError):
        validate_sql("SELECT * FROM (")


def test_rejects_zero_row_limit():
    with pytest.raises(ValueError):
        validate_sql("SELECT * FROM Artist", max_rows=0)