import sqlite3

db = sqlite3.connect("data/chinook.db")

tables = db.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
      AND name NOT LIKE 'sqlite_%'
    ORDER BY name
""").fetchall()

print("TABLES:", len(tables))

total = 0
for (name,) in tables:
    count = db.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
    total += count
    print(f"{name}: {count} rows")

print("TOTAL ROWS:", total)
db.close()
