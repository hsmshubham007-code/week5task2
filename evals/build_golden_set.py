import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evals.questions import QUESTIONS, UNANSWERABLE_QUESTIONS

DB_PATH = ROOT / "data" / "chinook.db"
OUTPUT_PATH = ROOT / "evals" / "golden_set.json"


def execute_reference_query(db, sql):
    """Execute trusted, read-only reference SQL and return its results."""
    statement = sql.strip().rstrip(";").strip()

    if not statement.upper().startswith(("SELECT ", "WITH ")):
        raise ValueError("Reference query must be a SELECT or WITH query.")

    cursor = db.execute(statement)
    columns = [item[0] for item in cursor.description]
    rows = [list(row) for row in cursor.fetchall()]

    return columns, rows


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    results = []

    # Open the database in read-only mode.
    uri = DB_PATH.as_uri() + "?mode=ro"

    with sqlite3.connect(uri, uri=True) as db:
        db.execute("PRAGMA query_only = ON")

        for question in QUESTIONS:
            columns, rows = execute_reference_query(
                db, question["sql"]
            )

            results.append({
                **question,
                "answerable": True,
                "expected_columns": columns,
                "expected_rows": rows,
            })

            print(
                f'{question["id"]}: verified '
                f"({len(rows)} result rows)"
            )

    # Unanswerable questions must not have invented SQL answers.
    for question in UNANSWERABLE_QUESTIONS:
        results.append({
            **question,
            "answerable": False,
            "expected_columns": [],
            "expected_rows": [],
        })

    OUTPUT_PATH.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    answerable = sum(item["answerable"] for item in results)
    unanswerable = len(results) - answerable

    print("\nGOLDEN SET CREATED")
    print(f"Answerable questions: {answerable}")
    print(f"Unanswerable questions: {unanswerable}")
    print(f"Total questions: {len(results)}")
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()