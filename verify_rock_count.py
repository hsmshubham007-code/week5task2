import sqlite3

connection = sqlite3.connect("file:data/chinook.db?mode=ro", uri=True)

try:
    query = """
        SELECT COUNT(*)
        FROM Track AS t
        JOIN Genre AS g ON t.GenreId = g.GenreId
        WHERE g.Name = ?
    """

    result = connection.execute(query, ("Rock",)).fetchone()[0]
    print(f"Rock tracks: {result}")
finally:
    connection.close()