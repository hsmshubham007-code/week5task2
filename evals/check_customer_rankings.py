
"""Fresh, isolated checks for golden-set questions Q010 and Q011."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agent import ask_agent
from evals.evaluate_agent import classify_result, extract_sql_results

GOLDEN_PATH = ROOT / "evals" / "golden_set.json"
TARGET_IDS = {"Q010", "Q011"}


def find_questions(data):
    """Find golden-set question records regardless of JSON container shape."""
    found = []

    def visit(value):
        if isinstance(value, dict):
            if (
                str(value.get("id", "")) in TARGET_IDS
                and "question" in value
                and "expected_columns" in value
                and "expected_rows" in value
            ):
                found.append(value)
            else:
                for child in value.values():
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(data)
    return {str(item["id"]): item for item in found}


def quota_exhausted(message):
    text = message.lower()
    return any(term in text for term in (
        "tokens per day",
        "tpd): limit",
        "daily token quota",
        "daily quota",
        "per-day token limit",
        "per day token limit",
    ))


def main():
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    questions = find_questions(golden)

    missing = TARGET_IDS - questions.keys()
    if missing:
        print(f"Missing questions in golden set: {sorted(missing)}")
        raise SystemExit(1)

    passed = 0
    completed = 0

    for question_id in sorted(TARGET_IDS):
        item = questions[question_id]
        print(f"\n{'=' * 65}\n{question_id}: {item['question']}\n")

        try:
            result = ask_agent(str(item["question"]))
        except Exception as exc:
            print(f"Agent exception: {exc}")
            if quota_exhausted(str(exc)):
                print("Daily quota detected. Stopping without further calls.")
                break
            completed += 1
            continue

        sql_queries = result.get("generated_sql", [])
        print("Generated SQL:")
        if sql_queries:
            for sql in sql_queries:
                print(sql)
                print()
        else:
            print("(No SQL generated.)")

        sql_result, errors = extract_sql_results(result)
        for error in errors:
            print(f"SQL/tool error: {error}")

        if any(quota_exhausted(error) for error in errors):
            print("Daily quota detected. Stopping without further calls.")
            break

        success, reason, columns, rows = classify_result(
            sql_result,
            item["expected_columns"],
            item["expected_rows"],
            sql_queries,
            errors,
        )

        completed += 1
        passed += int(success)

        print(f"Expected columns: {item['expected_columns']}")
        print(f"Actual columns:   {columns}")
        print(f"Actual rows:      {rows}")
        print(f"Result: {'PASS' if success else 'FAIL'} ({reason})")

    print(f"\nFresh checks completed: {completed}/2")
    print(f"Passed: {passed}/{completed}")
    if completed:
        print(f"Pass rate: {passed / completed * 100:.2f}%")
    print("\nExisting evaluation reports were not modified.")


if __name__ == "__main__":
    main()
