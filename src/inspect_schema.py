import sqlite3

DB_PATH = "data/chinook.db"


def main():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("PRAGMA foreign_keys = ON")

        tables = db.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """).fetchall()

        for (table,) in tables:
            print(f"\n## {table}")
            for col in db.execute(f'PRAGMA table_info("{table}")'):
                print(f"  {col[1]}: {col[2]}")

            for fk in db.execute(f'PRAGMA foreign_key_list("{table}")'):
                print(f"  FK: {fk[3]} -> {fk[2]}.{fk[4]}")

        print("\n## JOIN VERIFICATION")
        query = """
            SELECT c.FirstName, c.LastName, i.InvoiceId, i.Total
            FROM Customer AS c
            JOIN Invoice AS i ON c.CustomerId = i.CustomerId
            ORDER BY i.InvoiceId
            LIMIT 5
        """
        for row in db.execute(query):
            print(row)

        print("\nJOIN SUCCEEDED")


if __name__ == "__main__":
    main()
