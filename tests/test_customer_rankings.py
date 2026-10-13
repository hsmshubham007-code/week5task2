import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parents[1] / "data" / "chinook.db"


def run_query(sql):
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.execute(sql)
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()

    return columns, rows


def test_q010_customer_invoice_count_ranking():
    sql = """
        SELECT
            c.CustomerId,
            c.FirstName,
            c.LastName,
            COUNT(i.InvoiceId) AS invoice_count
        FROM Customer AS c
        JOIN Invoice AS i ON i.CustomerId = c.CustomerId
        GROUP BY c.CustomerId, c.FirstName, c.LastName
        ORDER BY invoice_count DESC, c.CustomerId ASC
        LIMIT 5
    """

    columns, rows = run_query(sql)

    assert columns == [
        "CustomerId",
        "FirstName",
        "LastName",
        "invoice_count",
    ]
    assert rows == [
        (1, "Luís", "Gonçalves", 7),
        (2, "Leonie", "Köhler", 7),
        (3, "François", "Tremblay", 7),
        (4, "Bjørn", "Hansen", 7),
        (5, "František", "Wichterlová", 7),
    ]


def test_q011_customer_spending_ranking():
    sql = """
        SELECT
            c.CustomerId,
            c.FirstName,
            c.LastName,
            ROUND(SUM(i.Total), 2) AS total_spent
        FROM Customer AS c
        JOIN Invoice AS i ON i.CustomerId = c.CustomerId
        GROUP BY c.CustomerId, c.FirstName, c.LastName
        ORDER BY total_spent DESC, c.CustomerId ASC
        LIMIT 5
    """

    columns, rows = run_query(sql)

    assert columns == [
        "CustomerId",
        "FirstName",
        "LastName",
        "total_spent",
    ]
    assert rows == [
        (6, "Helena", "Holý", 49.62),
        (26, "Richard", "Cunningham", 47.62),
        (57, "Luis", "Rojas", 46.62),
        (45, "Ladislav", "Kovács", 45.62),
        (46, "Hugh", "O'Reilly", 45.62),
    ]