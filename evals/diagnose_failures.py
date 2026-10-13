
"""Run targeted SQL-agent diagnostics without overwriting official results."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent import ask_agent
from evals.evaluate_agent import classify_result, extract_sql_results


GOLDEN_SET = PROJECT_ROOT / "evals" / "golden_set.json"
REPORT_PATH = PROJECT_ROOT / "evals" / "diagnostic_results.json"

TARGET_IDS = {
    "Q003", "Q009", "Q016", "Q017", "Q018", "Q019",
    "Q020", "Q021", "Q022", "Q023", "Q024", "Q029", "Q030",
}


def main() -> int:
    questions = json.loads(GOLDEN_SET.read_text(encoding="utf-8"))
    targets = [item for item in questions if item["id"] in TARGET_IDS]
    records = []

    print(f"Targeted questions: {len(targets)}")
    print("Official evaluation reports will not be modified.\n")

    for index, item in enumerate(targets, start=1):
        record = {
            "id": item["id"],
            "question": item["question"],
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
        }

        print(f"[{index}/{len(targets)}] {item['id']}: {item['question']}")

        try:
            result = ask_agent(item["question"])
            sql_queries = result.get("generated_sql", [])
            if not isinstance(sql_queries, list):
                sql_queries = []

            record["generated_sql"] = sql_queries
            record["agent_answer"] = str(result.get("answer", ""))

            sql_result, errors = extract_sql_results(result)
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
            record["failure_category"] = "agent_exception"
            record["exception"] = f"{type(exc).__name__}: {exc}"

        records.append(record)
        status = "PASS" if record["passed"] else "FAIL"
        print(f"  {status}: {record['failure_category']}")

        for sql in record["generated_sql"]:
            print(f"  SQL: {sql}")

        if record["exception"]:
            print(f"  Exception: {record['exception']}")
        print()

    passed_count = sum(record["passed"] for record in records)
    report = {
        "total": len(records),
        "passed": passed_count,
        "failed": len(records) - passed_count,
        "results": records,
    }

    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("=" * 60)
    print(f"Targeted pass rate: {passed_count}/{len(records)}")
    print(f"Diagnostic report: {REPORT_PATH.relative_to(PROJECT_ROOT)}")
    print("Official evaluation reports were not modified.")

    return 0 if passed_count == len(records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
