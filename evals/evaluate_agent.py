"""Evaluate the SQL agent against the pre-created golden set.

Scores actual SQL result data, not generated SQL text.
Supports resumable evaluations and classifies provider rate limits separately.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent import ask_agent


EVAL_DIR = PROJECT_ROOT / "evals"
GOLDEN_SET_PATH = EVAL_DIR / "golden_set.json"
RESULTS_JSON_PATH = EVAL_DIR / "results.json"
RESULTS_CSV_PATH = EVAL_DIR / "results.csv"
FAILURE_TAXONOMY_PATH = EVAL_DIR / "failure_taxonomy.json"
BASELINE_JSON_PATH = EVAL_DIR / "results_baseline.json"
BASELINE_CSV_PATH = EVAL_DIR / "results_baseline.csv"

RETRY_CATEGORIES = {
    "rate_limit",
    "agent_exception",
    "no_sql_generated",
    "sql_execution_error",
    "no_sql_result",
    "malformed_sql_result",
}


def normalize_columns(columns: Any) -> list[str]:
    """Normalize labels for reporting; aliases are not used to score SQL data."""
    if not isinstance(columns, list):
        return []
    return [str(column).strip().lower() for column in columns]


def normalize_rows(rows: Any) -> list[list[Any]] | None:
    """Validate and normalize returned rows."""
    if not isinstance(rows, list):
        return None

    normalized = []
    for row in rows:
        if not isinstance(row, (list, tuple)):
            return None
        normalized.append(list(row))

    return normalized


def parse_tool_output(output: Any) -> dict[str, Any] | None:
    """Parse a tool result when its content is JSON."""
    if isinstance(output, dict):
        return output

    if not isinstance(output, str) or not output.strip():
        return None

    text = output.strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    return None


def is_rate_limit_error(message: str) -> bool:
    """Identify common Groq/provider rate-limit exceptions."""
    text = message.lower()
    indicators = (
        "ratelimiterror",
        "rate_limit_exceeded",
        "rate limit reached",
        "tokens per minute",
        "tokens per day",
        "tpm): limit",
        "tpd): limit",
    )
    return any(indicator in text for indicator in indicators)


def extract_sql_results(
    agent_result: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    """Find the latest successful SQL result and collect execution errors."""
    tool_logs = agent_result.get("tool_logs", [])
    if not isinstance(tool_logs, list):
        return None, ["Tool logs were missing or malformed."]

    sql_results = []
    errors = []

    for log in tool_logs:
        if not isinstance(log, dict):
            continue

        if log.get("tool") != "execute_readonly_sql":
            continue

        output = log.get("output", "")
        parsed = parse_tool_output(output)

        if parsed is None:
            errors.append(str(output)[:500])
            continue

        if parsed.get("error"):
            errors.append(str(parsed["error"])[:500])
            continue

        if "columns" in parsed and "rows" in parsed:
            sql_results.append(parsed)
        else:
            errors.append(str(output)[:500])

    if sql_results:
        return sql_results[-1], errors

    return None, errors


def rows_match_with_ties(
    expected_rows: list[list[Any]],
    actual_rows: list[list[Any]],
) -> bool:
    """Compare row data while allowing arbitrary order within tied rankings.

    Overall ranking order remains significant. When rows are ranked by their
    final numeric column, rows with equal values may appear in either order.
    """
    if expected_rows == actual_rows:
        return True

    if len(expected_rows) != len(actual_rows):
        return False

    if not expected_rows:
        return not actual_rows

    if any(not row for row in expected_rows + actual_rows):
        return False

    if any(
        len(row) != len(expected_rows[0])
        for row in expected_rows + actual_rows
    ):
        return False

    def is_number(value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    if not all(
        is_number(row[-1]) for row in expected_rows + actual_rows
    ):
        return False

    expected_keys = [row[-1] for row in expected_rows]
    actual_keys = [row[-1] for row in actual_rows]

    # Only allow tied-row reordering when both result sets follow the same
    # monotonic ranking direction.
    def is_monotonic(values: list[Any]) -> bool:
        return (
            all(a >= b for a, b in zip(values, values[1:]))
            or all(a <= b for a, b in zip(values, values[1:]))
        )

    if not is_monotonic(expected_keys) or not is_monotonic(actual_keys):
        return False

    if expected_keys != actual_keys:
        return False

    def row_key(row: list[Any]) -> str:
        return json.dumps(row, ensure_ascii=False, sort_keys=True)

    # Sort only within groups sharing the same final-column ranking value.
    start = 0
    while start < len(expected_rows):
        end = start + 1
        while (
            end < len(expected_rows)
            and expected_rows[end][-1] == expected_rows[start][-1]
        ):
            end += 1

        expected_group = sorted(
            (row_key(row) for row in expected_rows[start:end])
        )
        actual_group = sorted(
            (row_key(row) for row in actual_rows[start:end])
        )

        if expected_group != actual_group:
            return False

        start = end

    return True


def classify_result(
    result: dict[str, Any] | None,
    expected_columns: list[str],
    expected_rows: list[list[Any]],
    sql_queries: list[str],
    errors: list[str],
) -> tuple[bool, str, list[str], list[list[Any]] | None]:
    """Score returned data; SQL text and alias spelling do not affect the score."""
    if result is None:
        if errors:
            return False, "sql_execution_error", [], None
        if not sql_queries:
            return False, "no_sql_generated", [], None
        return False, "no_sql_result", [], None

    actual_columns = normalize_columns(result.get("columns"))
    actual_rows = normalize_rows(result.get("rows"))

    if actual_rows is None:
        return False, "malformed_sql_result", actual_columns, None

    expected_normalized = normalize_columns(expected_columns)

    if len(actual_columns) != len(expected_normalized):
        return False, "column_count_mismatch", actual_columns, actual_rows

    # Compare actual result values and their column positions. Alias names can
    # differ without changing the underlying SQL result data.
    if any(len(row) != len(expected_normalized) for row in actual_rows):
        return False, "malformed_sql_result", actual_columns, actual_rows

    if not rows_match_with_ties(expected_rows, actual_rows):
        return False, "row_mismatch", actual_columns, actual_rows

    return True, "pass", actual_columns, actual_rows


def write_reports(
    records: list[dict[str, Any]],
    total: int,
    complete: bool,
) -> None:
    """Persist current progress and the failure taxonomy."""
    passed = sum(1 for record in records if record["passed"])
    failed = sum(1 for record in records if not record["passed"])
    counts = Counter(
        record["failure_category"]
        for record in records
        if not record["passed"]
    )
    completed = len(records)

    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "golden_set": "evals/golden_set.json",
        "scoring_method": (
            "Actual returned row data; column aliases ignored; "
            "ties in monotonic numeric rankings may appear in either order"
        ),
        "total_answerable": total,
        "completed": completed,
        "pending": max(0, total - completed),
        "complete": complete,
        "passed": passed,
        "failed": failed,
        "pass_rate_percent": round((passed / completed) * 100, 2)
        if completed
        else 0.0,
        "failure_counts": dict(sorted(counts.items())),
        "results": records,
    }

    with RESULTS_JSON_PATH.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, ensure_ascii=False)

    fields = [
        "id",
        "question",
        "passed",
        "failure_category",
        "expected_columns",
        "expected_rows",
        "actual_columns",
        "actual_rows",
        "generated_sql",
        "sql_errors",
        "agent_answer",
        "exception",
        "reused_previous_result",
    ]

    with RESULTS_CSV_PATH.open(
        "w", encoding="utf-8-sig", newline=""
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for record in records:
            row = dict(record)
            for field in (
                "expected_columns",
                "expected_rows",
                "actual_columns",
                "actual_rows",
                "generated_sql",
                "sql_errors",
            ):
                row[field] = json.dumps(
                    row.get(field), ensure_ascii=False
                )
            writer.writerow(row)

    taxonomy = {
        "total_questions": total,
        "completed": completed,
        "pending": max(0, total - completed),
        "complete": complete,
        "passed": passed,
        "failed": failed,
        "failure_counts": dict(sorted(counts.items())),
    }

    with FAILURE_TAXONOMY_PATH.open("w", encoding="utf-8") as file:
        json.dump(taxonomy, file, indent=2, ensure_ascii=False)


def make_record(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("id", "")),
        "question": str(item.get("question", "")),
        "passed": False,
        "failure_category": "",
        "expected_columns": item.get("expected_columns", []),
        "expected_rows": item.get("expected_rows", []),
        "actual_columns": [],
        "actual_rows": None,
        "generated_sql": [],
        "sql_errors": [],
        "agent_answer": "",
        "exception": "",
        "reused_previous_result": False,
    }


def rescore_saved_record(
    item: dict[str, Any],
    old: dict[str, Any],
) -> dict[str, Any] | None:
    """Reuse saved result data without calling the LLM again."""
    if old.get("failure_category") in RETRY_CATEGORIES:
        return None

    actual_rows = normalize_rows(old.get("actual_rows"))
    actual_columns = old.get("actual_columns")

    if actual_rows is None or not isinstance(actual_columns, list):
        return None

    record = make_record(item)
    record.update({
        "actual_columns": actual_columns,
        "actual_rows": actual_rows,
        "generated_sql": old.get("generated_sql", []),
        "sql_errors": old.get("sql_errors", []),
        "agent_answer": old.get("agent_answer", ""),
        "exception": old.get("exception", ""),
        "reused_previous_result": True,
    })

    passed, category, columns, rows = classify_result(
        result={"columns": actual_columns, "rows": actual_rows},
        expected_columns=item.get("expected_columns", []),
        expected_rows=item.get("expected_rows", []),
        sql_queries=record["generated_sql"],
        errors=record["sql_errors"],
    )

    record.update({
        "passed": passed,
        "failure_category": category,
        "actual_columns": columns,
        "actual_rows": rows,
    })
    return record


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the SQL agent against the golden set."
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Reuse saved result data when possible; retry rate limits and "
            "incomplete agent attempts."
        ),
    )
    args = parser.parse_args()

    if not GOLDEN_SET_PATH.exists():
        print(f"ERROR: Golden set not found: {GOLDEN_SET_PATH}")
        return 1

    with GOLDEN_SET_PATH.open("r", encoding="utf-8") as file:
        golden_set = json.load(file)

    if not isinstance(golden_set, list):
        print("ERROR: Golden set must contain a JSON list.")
        return 1

    questions = [
        item
        for item in golden_set
        if isinstance(item, dict) and item.get("answerable") is True
    ]

    if not questions:
        print("ERROR: No answerable questions found.")
        return 1

    # Preserve the first historical results before overwriting them.
    if RESULTS_JSON_PATH.exists() and not BASELINE_JSON_PATH.exists():
        shutil.copy2(RESULTS_JSON_PATH, BASELINE_JSON_PATH)
        print("Preserved original results at evals/results_baseline.json")

    if RESULTS_CSV_PATH.exists() and not BASELINE_CSV_PATH.exists():
        shutil.copy2(RESULTS_CSV_PATH, BASELINE_CSV_PATH)
        print("Preserved original CSV at evals/results_baseline.csv")

    old_records: dict[str, dict[str, Any]] = {}
    if args.resume and RESULTS_JSON_PATH.exists():
        try:
            with RESULTS_JSON_PATH.open("r", encoding="utf-8") as file:
                previous = json.load(file)
            old_records = {
                str(record.get("id")): record
                for record in previous.get("results", [])
                if isinstance(record, dict)
            }
        except (json.JSONDecodeError, OSError, AttributeError):
            print("WARNING: Previous results could not be loaded; starting fresh.")

    print("=" * 68)
    print("SQL AGENT EVALUATION")
    print("=" * 68)
    print(f"Golden set: {GOLDEN_SET_PATH}")
    print(f"Answerable questions: {len(questions)}")
    print("Scoring: returned row data, not generated SQL text")
    print(f"Resume mode: {args.resume}")
    print("-" * 68)

    records: list[dict[str, Any]] = []

    for index, item in enumerate(questions, start=1):
        question_id = str(item.get("id", f"Q{index:03d}"))
        item = {**item, "id": question_id}
        old = old_records.get(question_id)

        if args.resume and old:
            saved = rescore_saved_record(item, old)
            if saved is not None:
                records.append(saved)
                status = "PASS" if saved["passed"] else "FAIL"
                print(
                    f"[{index:02d}/{len(questions):02d}] "
                    f"{question_id} {status} (reused saved result)"
                )
                write_reports(
                    records,
                    len(questions),
                    complete=(index == len(questions)),
                )
                continue

        record = make_record(item)

        try:
            agent_result = ask_agent(str(item.get("question", "")))
            sql_queries = agent_result.get("generated_sql", [])
            if not isinstance(sql_queries, list):
                sql_queries = []

            record["generated_sql"] = sql_queries
            record["agent_answer"] = str(agent_result.get("answer", ""))

            sql_result, errors = extract_sql_results(agent_result)
            record["sql_errors"] = errors

            passed, category, columns, rows = classify_result(
                result=sql_result,
                expected_columns=item.get("expected_columns", []),
                expected_rows=item.get("expected_rows", []),
                sql_queries=sql_queries,
                errors=errors,
            )

            record.update({
                "passed": passed,
                "failure_category": category,
                "actual_columns": columns,
                "actual_rows": rows,
            })

        except Exception as exc:
            error_text = f"{type(exc).__name__}: {exc}"
            record["exception"] = error_text
            record["failure_category"] = (
                "rate_limit"
                if is_rate_limit_error(error_text)
                else "agent_exception"
            )

        records.append(record)
        status = "PASS" if record["passed"] else "FAIL"
        print(
            f"[{index:02d}/{len(questions):02d}] "
            f"{question_id} {status}"
            + (
                f" ({record['failure_category']})"
                if not record["passed"]
                else ""
            )
        )

        # Save after every question so interrupted runs retain their progress.
        write_reports(
            records,
            len(questions),
            complete=(index == len(questions)),
        )

    passed_count = sum(1 for record in records if record["passed"])
    failure_counts = Counter(
        record["failure_category"]
        for record in records
        if not record["passed"]
    )
    total = len(questions)
    pass_rate = round((passed_count / total) * 100, 2) if total else 0.0

    print("-" * 68)
    print("EVALUATION SUMMARY")
    print(f"Completed: {len(records)}/{total}")
    print(f"Passed: {passed_count}/{total}")
    print(f"Failed: {total - passed_count}/{total}")
    print(f"Pass rate: {pass_rate:.2f}%")
    print("\nFailure taxonomy:")

    if failure_counts:
        for category, count in sorted(failure_counts.items()):
            print(f"  {category}: {count}")
    else:
        print("  No failures")

    print("\nSaved results:")
    print("  evals/results.json")
    print("  evals/results.csv")
    print("  evals/failure_taxonomy.json")

    if any(count for category, count in failure_counts.items()
           if category == "rate_limit"):
        print(
            "\nNOTE: Rate-limited questions are infrastructure failures, "
            "not evidence of incorrect SQL."
        )

    return 0 if passed_count == total else 1


if __name__ == "__main__":
    raise SystemExit(main())