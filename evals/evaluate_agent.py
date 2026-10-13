"""Evaluate the SQL agent against the pre-created golden set.

Scores actual SQL result data, not generated SQL text.
Supports resumable evaluations, pending-only runs, smoke tests,
and provider-limit safeguards.
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
    "daily_quota_exhausted",
    "agent_exception",
    "no_sql_generated",
    "sql_execution_error",
    "no_sql_result",
    "malformed_sql_result",
}


def normalize_columns(columns: Any) -> list[str]:
    """Normalize column labels for reporting."""
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

    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start:end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    return None


def is_rate_limit_error(message: str) -> bool:
    """Identify common provider rate-limit exceptions."""
    text = message.lower()
    indicators = (
        "ratelimiterror",
        "rate_limit_exceeded",
        "rate limit reached",
        "tokens per minute",
        "tokens per day",
        "tpm): limit",
        "tpd): limit",
        "rate limit",
    )
    return any(indicator in text for indicator in indicators)


def is_daily_quota_error(message: str) -> bool:
    """Identify errors indicating that the daily token quota is exhausted."""
    text = message.lower()
    indicators = (
        "tokens per day",
        "tpd): limit",
        "daily token quota",
        "daily quota",
        "per-day token limit",
        "per day token limit",
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
        elif parsed.get("error"):
            errors.append(str(parsed["error"])[:500])
        elif "columns" in parsed and "rows" in parsed:
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
    """Compare rows with numeric tolerance and tied-ranking order support."""
    import math

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

    def values_equal(expected: Any, actual: Any) -> bool:
        if is_number(expected) and is_number(actual):
            return math.isclose(
                float(expected), float(actual), rel_tol=0.0, abs_tol=0.01
            )
        return expected == actual

    def rows_equal(expected: list[Any], actual: list[Any]) -> bool:
        return all(
            values_equal(left, right)
            for left, right in zip(expected, actual)
        )

    if all(
        rows_equal(expected, actual)
        for expected, actual in zip(expected_rows, actual_rows)
    ):
        return True

    expected_keys = [row[-1] for row in expected_rows]
    actual_keys = [row[-1] for row in actual_rows]

    if not all(is_number(value) for value in expected_keys + actual_keys):
        return False

    def is_monotonic(values: list[Any]) -> bool:
        return (
            all(a >= b for a, b in zip(values, values[1:]))
            or all(a <= b for a, b in zip(values, values[1:]))
        )

    if not is_monotonic(expected_keys) or not is_monotonic(actual_keys):
        return False
    if not all(
        values_equal(expected, actual)
        for expected, actual in zip(expected_keys, actual_keys)
    ):
        return False

    start = 0
    while start < len(expected_rows):
        end = start + 1
        while (
            end < len(expected_rows)
            and values_equal(expected_rows[end][-1], expected_rows[start][-1])
        ):
            end += 1

        unmatched = list(actual_rows[start:end])
        for expected_row in expected_rows[start:end]:
            match_index = next(
                (
                    index
                    for index, actual_row in enumerate(unmatched)
                    if rows_equal(expected_row, actual_row)
                ),
                None,
            )
            if match_index is None:
                return False
            unmatched.pop(match_index)

        start = end

    return True


def classify_result(
    result: dict[str, Any] | None,
    expected_columns: list[str],
    expected_rows: list[list[Any]],
    sql_queries: list[str],
    errors: list[str],
) -> tuple[bool, str, list[str], list[list[Any]] | None]:
    """Score returned SQL data; column aliases are not used for scoring."""
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
    """Persist merged progress, including pending questions."""
    passed = sum(1 for record in records if record["passed"])
    failed = len(records) - passed
    counts = Counter(
        record["failure_category"]
        for record in records
        if not record["passed"] and record["failure_category"]
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
        "pass_rate_percent": round(passed / completed * 100, 2)
        if completed else 0.0,
        "failure_counts": dict(sorted(counts.items())),
        "results": records,
    }

    with RESULTS_JSON_PATH.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, ensure_ascii=False)

    fields = [
        "id", "question", "passed", "failure_category",
        "expected_columns", "expected_rows", "actual_columns",
        "actual_rows", "generated_sql", "sql_errors", "agent_answer",
        "exception", "reused_previous_result",
    ]

    with RESULTS_CSV_PATH.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()

        for record in records:
            row = dict(record)
            for field in (
                "expected_columns", "expected_rows", "actual_columns",
                "actual_rows", "generated_sql", "sql_errors",
            ):
                row[field] = json.dumps(row.get(field), ensure_ascii=False)
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
    """Create a consistently shaped evaluation record."""
    return {
        "id": str(item.get("id", "")),
        "question": str(item.get("question", "")),
        "answerable": item.get("answerable"),
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


def matches_evaluation_target(
    item: dict[str, Any],
    old: dict[str, Any],
) -> bool:
    """Check whether a saved record matches the current evaluation target."""
    required_fields = (
        "id",
        "question",
        "expected_columns",
        "expected_rows",
    )

    if not all(old.get(field) == item.get(field) for field in required_fields):
        return False

    # Older reports may not contain this field.
    if "answerable" in old and old["answerable"] != item.get("answerable"):
        return False

    return True


def rescore_saved_record(
    item: dict[str, Any],
    old: dict[str, Any],
) -> dict[str, Any] | None:
    """Reuse saved results only when the result and target are reusable."""
    if old.get("failure_category") in RETRY_CATEGORIES:
        return None

    if not matches_evaluation_target(item, old):
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


def load_previous_records() -> dict[str, dict[str, Any]]:
    """Load prior records without failing if a report is unreadable."""
    if not RESULTS_JSON_PATH.exists():
        return {}

    try:
        with RESULTS_JSON_PATH.open("r", encoding="utf-8") as file:
            previous = json.load(file)

        if not isinstance(previous, dict):
            return {}

        return {
            str(record.get("id")): record
            for record in previous.get("results", [])
            if isinstance(record, dict) and record.get("id") is not None
        }
    except (json.JSONDecodeError, OSError, AttributeError, TypeError):
        print("WARNING: Previous results could not be loaded.")
        return {}


def ordered_records(
    records_by_id: dict[str, dict[str, Any]],
    questions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return available records in golden-set order, without duplicates."""
    result = []
    seen = set()

    for index, item in enumerate(questions, start=1):
        question_id = str(item.get("id", f"Q{index:03d}"))
        record = records_by_id.get(question_id)
        if record is not None and question_id not in seen:
            result.append(record)
            seen.add(question_id)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the SQL agent against the golden set."
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse valid saved results and retry transient failures.",
    )
    parser.add_argument(
        "--pending-only",
        action="store_true",
        help=(
            "Reuse saved results and process only missing results or "
            "retryable transient failures. Implies --resume."
        ),
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run only the first few questions (default: 3).",
    )
    parser.add_argument(
        "--smoke-count",
        type=int,
        default=3,
        help="Number of questions for --smoke-test (default: 3).",
    )
    args = parser.parse_args()

    if args.smoke_count < 1:
        parser.error("--smoke-count must be at least 1")

    resume = args.resume or args.pending_only

    if not GOLDEN_SET_PATH.exists():
        print(f"ERROR: Golden set not found: {GOLDEN_SET_PATH}")
        return 1

    try:
        with GOLDEN_SET_PATH.open("r", encoding="utf-8") as file:
            golden_set = json.load(file)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: Could not load golden set: {exc}")
        return 1

    if not isinstance(golden_set, list):
        print("ERROR: Golden set must contain a JSON list.")
        return 1

    questions = [
        item for item in golden_set
        if isinstance(item, dict) and item.get("answerable") is True
    ]
    if not questions:
        print("ERROR: No answerable questions found.")
        return 1

    if RESULTS_JSON_PATH.exists() and not BASELINE_JSON_PATH.exists():
        shutil.copy2(RESULTS_JSON_PATH, BASELINE_JSON_PATH)
        print("Preserved original results at evals/results_baseline.json")

    if RESULTS_CSV_PATH.exists() and not BASELINE_CSV_PATH.exists():
        shutil.copy2(RESULTS_CSV_PATH, BASELINE_CSV_PATH)
        print("Preserved original CSV at evals/results_baseline.csv")

    old_records = load_previous_records() if resume else {}

    total = len(questions)
    run_questions = (
        questions[:min(args.smoke_count, total)]
        if args.smoke_test else questions
    )
    target = len(run_questions)

    # Start with prior records that still match the current golden set.
    # Keep transient failures until a new attempt replaces them.
    records_by_id: dict[str, dict[str, Any]] = {}

    if resume:
        for index, original_item in enumerate(questions, start=1):
            question_id = str(original_item.get("id", f"Q{index:03d}"))
            item = {**original_item, "id": question_id}
            old = old_records.get(question_id)

            if not old or not matches_evaluation_target(item, old):
                continue

            saved = rescore_saved_record(item, old)
            if saved is not None:
                records_by_id[question_id] = saved
            else:
                # Preserve matching transient/incomplete attempts unless a
                # new attempt replaces them.
                retained = make_record(item)
                retained.update(old)
                retained["id"] = question_id
                retained["reused_previous_result"] = False
                records_by_id[question_id] = retained

    print("=" * 68)
    print("SQL AGENT EVALUATION")
    print("=" * 68)
    print(f"Golden set: {GOLDEN_SET_PATH}")
    print(f"Answerable questions: {total}")
    print(f"Questions in this run: {target}")
    print("Scoring: returned row data, not generated SQL text")
    print(f"Resume mode: {resume}")
    print(f"Pending-only mode: {args.pending_only}")
    print(f"Smoke test: {args.smoke_test}")
    print("-" * 68)

    provider_limit_hit = False

    for index, original_item in enumerate(run_questions, start=1):
        question_id = str(original_item.get("id", f"Q{index:03d}"))
        item = {**original_item, "id": question_id}
        old = old_records.get(question_id)

        if resume and old:
            saved = rescore_saved_record(item, old)
            if saved is not None:
                records_by_id[question_id] = saved
                print(
                    f"[{index:02d}/{target:02d}] {question_id} "
                    f"{'PASS' if saved['passed'] else 'FAIL'} "
                    "(reused saved result)"
                )
                current_records = ordered_records(records_by_id, questions)
                write_reports(
                    current_records,
                    total,
                    len(current_records) == total,
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

            if is_daily_quota_error(error_text):
                record["failure_category"] = "daily_quota_exhausted"
                provider_limit_hit = True
            elif is_rate_limit_error(error_text):
                record["failure_category"] = "rate_limit"
                provider_limit_hit = True
            else:
                record["failure_category"] = "agent_exception"

        records_by_id[question_id] = record

        print(
            f"[{index:02d}/{target:02d}] {question_id} "
            f"{'PASS' if record['passed'] else 'FAIL'}"
            + (
                f" ({record['failure_category']})"
                if not record["passed"] else ""
            )
        )

        # Always persist the merged records, not only this run's records.
        current_records = ordered_records(records_by_id, questions)
        complete = len(current_records) == total and not provider_limit_hit
        write_reports(current_records, total, complete)

        if provider_limit_hit:
            print("\nStopping evaluation after provider rate limit.")
            if record["failure_category"] == "daily_quota_exhausted":
                print("Daily token quota exhaustion detected.")
            print(f"{max(0, total - len(current_records))} question(s) pending.")
            break

    records = ordered_records(records_by_id, questions)
    passed_count = sum(1 for record in records if record["passed"])
    failure_counts = Counter(
        record["failure_category"]
        for record in records
        if record["failure_category"] and not record["passed"]
    )
    pending = max(0, total - len(records))
    complete = pending == 0 and not provider_limit_hit

    write_reports(records, total, complete)

    print("-" * 68)
    print("EVALUATION SUMMARY")
    print(f"Completed: {len(records)}/{total}")
    print(f"Passed: {passed_count}/{len(records)} attempted")
    print(f"Failed attempts: {len(records) - passed_count}")
    print(f"Pending: {pending}")
    print(f"Complete: {complete}")
    print(
        "Pass rate (completed attempts): "
        f"{(passed_count / len(records) * 100) if records else 0.0:.2f}%"
    )
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

    if provider_limit_hit:
        print(
            "\nNOTE: Provider rate limits are infrastructure interruptions, "
            "not evidence of incorrect SQL."
        )

    if args.smoke_test and not provider_limit_hit:
        print("\nSmoke test only; run the full evaluation after it passes.")

    if provider_limit_hit:
        return 1
    if any(not record["passed"] for record in records):
        return 1
    return 0 if args.smoke_test or complete else 1


if __name__ == "__main__":
    raise SystemExit(main())