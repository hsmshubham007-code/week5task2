"""Rescore saved SQL-agent results without making new LLM calls.

Reads evals/results.json and evals/golden_set.json, then writes separate
results_rescored.json and results_rescored.csv files. Original results are
never overwritten.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# This script is run directly from the evals directory, so importing the sibling
# module by its filename works in both direct-script and project-root contexts.
from evaluate_agent import RETRY_CATEGORIES, classify_result, normalize_rows

EVAL_DIR = PROJECT_ROOT / "evals"
SAVED_RESULTS = EVAL_DIR / "results.json"
GOLDEN_SET = EVAL_DIR / "golden_set.json"
OUTPUT_JSON = EVAL_DIR / "results_rescored.json"
OUTPUT_CSV = EVAL_DIR / "results_rescored.csv"

CSV_FIELDS = [
    "id",
    "question",
    "passed",
    "failure_category",
    "rescore_status",
    "generated_sql",
    "expected_rows",
    "actual_rows",
]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main() -> int:
    for path in (SAVED_RESULTS, GOLDEN_SET):
        if not path.is_file():
            print(f"ERROR: Required file not found: {path}")
            return 1

    try:
        saved = load_json(SAVED_RESULTS)
        golden = load_json(GOLDEN_SET)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: Could not read input JSON: {exc}")
        return 1

    if not isinstance(saved, dict) or not isinstance(saved.get("results"), list):
        print("ERROR: results.json must contain a 'results' list.")
        return 1
    if not isinstance(golden, list):
        print("ERROR: golden_set.json must contain a JSON list.")
        return 1

    old_results = {
        str(record.get("id")): record
        for record in saved["results"]
        if isinstance(record, dict)
    }
    questions = [
        item for item in golden
        if isinstance(item, dict) and item.get("answerable") is True
    ]
    if not questions:
        print("ERROR: No answerable questions found in the golden set.")
        return 1

    records: list[dict[str, Any]] = []
    for item in questions:
        question_id = str(item.get("id", ""))
        old = old_results.get(question_id, {})
        old_category = str(old.get("failure_category", ""))
        record: dict[str, Any] = {
            "id": question_id,
            "question": item.get("question", ""),
            "expected_columns": item.get("expected_columns", []),
            "expected_rows": item.get("expected_rows", []),
            "generated_sql": old.get("generated_sql", []),
            "sql_errors": old.get("sql_errors", []),
            "actual_columns": old.get("actual_columns", []),
            "actual_rows": old.get("actual_rows"),
            "passed": False,
            "failure_category": "",
            "rescore_status": "",
        }

        # A rate limit or agent exception without a valid SQL result cannot be
        # rescored offline. Keep its category visible rather than treating it as
        # a SQL-answer failure.
        if old_category in RETRY_CATEGORIES:
            record["failure_category"] = old_category
            record["rescore_status"] = "not_rescored_no_result"
            records.append(record)
            continue

        actual_rows = normalize_rows(old.get("actual_rows"))
        actual_columns = old.get("actual_columns")
        if actual_rows is None or not isinstance(actual_columns, list):
            record["failure_category"] = old_category or "no_saved_result"
            record["rescore_status"] = "not_rescored_no_result"
            records.append(record)
            continue

        passed, category, columns, rows = classify_result(
            result={"columns": actual_columns, "rows": actual_rows},
            expected_columns=item.get("expected_columns", []),
            expected_rows=item.get("expected_rows", []),
            sql_queries=record["generated_sql"] if isinstance(record["generated_sql"], list) else [],
            errors=record["sql_errors"] if isinstance(record["sql_errors"], list) else [],
        )
        record.update({
            "passed": passed,
            "failure_category": category,
            "actual_columns": columns,
            "actual_rows": rows,
            "rescore_status": "rescored",
        })
        records.append(record)

    rescored_count = sum(r["rescore_status"] == "rescored" for r in records)
    passed_count = sum(bool(r["passed"]) for r in records)
    failed_count = len(records) - passed_count
    failure_counts = Counter(
        r["failure_category"] for r in records if not r["passed"]
    )
    not_rescored = len(records) - rescored_count

    report = {
        "evaluation": "offline_rescore_of_saved_results",
        "note": (
            "Uses saved results only; no LLM calls. Records without saved result "
            "data are not rescored. Numeric tolerance and tie handling are defined "
            "by evals.evaluate_agent."
        ),
        "total_questions": len(questions),
        "rescored_questions": rescored_count,
        "not_rescored_questions": not_rescored,
        "passed": passed_count,
        "failed": failed_count,
        "pass_rate_of_all_questions_percent": round(
            passed_count / len(records) * 100, 2
        ) if records else 0.0,
        "pass_rate_of_rescored_questions_percent": round(
            passed_count / rescored_count * 100, 2
        ) if rescored_count else 0.0,
        "failure_counts": dict(sorted(failure_counts.items())),
        "results": records,
    }

    try:
        with OUTPUT_JSON.open("w", encoding="utf-8") as file:
            json.dump(report, file, indent=2, ensure_ascii=False)

        with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for record in records:
                writer.writerow({
                    "id": record["id"],
                    "question": record["question"],
                    "passed": record["passed"],
                    "failure_category": record["failure_category"],
                    "rescore_status": record["rescore_status"],
                    "generated_sql": json.dumps(record["generated_sql"], ensure_ascii=False),
                    "expected_rows": json.dumps(record["expected_rows"], ensure_ascii=False),
                    "actual_rows": json.dumps(record["actual_rows"], ensure_ascii=False),
                })
    except OSError as exc:
        print(f"ERROR: Could not write rescore reports: {exc}")
        return 1

    print("OFFLINE RESCORE SUMMARY")
    print(f"Questions: {len(records)}")
    print(f"Rescored: {rescored_count}")
    print(f"Not rescored: {not_rescored}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {failed_count}")
    print(f"Pass rate (all questions): {report['pass_rate_of_all_questions_percent']:.2f}%")
    print(f"Pass rate (rescored only): {report['pass_rate_of_rescored_questions_percent']:.2f}%")
    print("Failure categories:", dict(sorted(failure_counts.items())))
    print(f"Saved: {OUTPUT_JSON}")
    print(f"Saved: {OUTPUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
