import json

import evals.evaluate_agent as evaluator


def make_question(index):
    return {
        "id": f"Q{index:03d}",
        "question": f"Test question {index}",
        "answerable": True,
        "expected_columns": ["value"],
        "expected_rows": [[1]],
    }


def successful_agent_result():
    return {
        "answer": "One row returned.",
        "generated_sql": ["SELECT 1 AS value"],
        "tool_logs": [
            {
                "tool": "execute_readonly_sql",
                "output": json.dumps({
                    "columns": ["value"],
                    "rows": [[1]],
                }),
            }
        ],
    }


def saved_record(item, actual_columns=None, actual_rows=None):
    """Build a legacy saved record without the newer answerable field."""
    actual_columns = (
        ["value"] if actual_columns is None else actual_columns
    )
    actual_rows = [[1]] if actual_rows is None else actual_rows

    passed = (
        actual_columns == item["expected_columns"]
        and actual_rows == item["expected_rows"]
    )

    return {
        "id": item["id"],
        "question": item["question"],
        "expected_columns": item["expected_columns"],
        "expected_rows": item["expected_rows"],
        "passed": passed,
        "failure_category": (
            "pass" if passed else "column_count_mismatch"
        ),
        "actual_columns": actual_columns,
        "actual_rows": actual_rows,
        "generated_sql": ["SELECT 1 AS value"],
        "sql_errors": [],
        "agent_answer": "Previously saved answer.",
    }


def configure_temp_paths(tmp_path, monkeypatch, question_count=5):
    paths = {
        "GOLDEN_SET_PATH": tmp_path / "golden_set.json",
        "RESULTS_JSON_PATH": tmp_path / "results.json",
        "RESULTS_CSV_PATH": tmp_path / "results.csv",
        "FAILURE_TAXONOMY_PATH": tmp_path / "failure_taxonomy.json",
        "BASELINE_JSON_PATH": tmp_path / "results_baseline.json",
        "BASELINE_CSV_PATH": tmp_path / "results_baseline.csv",
    }

    for name, path in paths.items():
        monkeypatch.setattr(evaluator, name, path)

    paths["GOLDEN_SET_PATH"].write_text(
        json.dumps([
            make_question(i)
            for i in range(1, question_count + 1)
        ]),
        encoding="utf-8",
    )

    return paths


def write_saved_results(path, records):
    """Write the existing evaluator report shape with saved result rows."""
    path.write_text(
        json.dumps({"results": records}, indent=2),
        encoding="utf-8",
    )


def test_daily_quota_error_is_detected():
    message = (
        "RateLimitError: tokens per day (TPD): limit 200000, "
        "used 199500, requested 1000"
    )

    assert evaluator.is_daily_quota_error(message)
    assert evaluator.is_rate_limit_error(message)


def test_daily_quota_stops_run_and_leaves_questions_pending(
    tmp_path, monkeypatch
):
    paths = configure_temp_paths(tmp_path, monkeypatch)
    calls = []

    def fake_agent(question):
        calls.append(question)

        if len(calls) == 1:
            return successful_agent_result()

        raise RuntimeError(
            "RateLimitError: tokens per day (TPD): limit 200000"
        )

    monkeypatch.setattr(evaluator, "ask_agent", fake_agent)
    monkeypatch.setattr("sys.argv", ["evaluate_agent.py"])

    exit_code = evaluator.main()

    report = json.loads(
        paths["RESULTS_JSON_PATH"].read_text(encoding="utf-8")
    )

    assert exit_code == 1
    assert len(calls) == 2
    assert report["completed"] == 2
    assert report["pending"] == 3
    assert report["complete"] is False
    assert report["passed"] == 1
    assert report["failure_counts"]["daily_quota_exhausted"] == 1


def test_smoke_test_runs_only_three_questions(tmp_path, monkeypatch):
    paths = configure_temp_paths(tmp_path, monkeypatch)
    calls = []

    def fake_agent(question):
        calls.append(question)
        return successful_agent_result()

    monkeypatch.setattr(evaluator, "ask_agent", fake_agent)
    monkeypatch.setattr(
        "sys.argv",
        ["evaluate_agent.py", "--smoke-test"],
    )

    exit_code = evaluator.main()

    report = json.loads(
        paths["RESULTS_JSON_PATH"].read_text(encoding="utf-8")
    )

    assert exit_code == 0
    assert len(calls) == 3
    assert report["completed"] == 3
    assert report["pending"] == 2
    assert report["complete"] is False
    assert report["passed"] == 3
    assert "pass" not in report["failure_counts"]


def test_smoke_count_can_be_customized(tmp_path, monkeypatch):
    paths = configure_temp_paths(tmp_path, monkeypatch)
    calls = []

    def fake_agent(question):
        calls.append(question)
        return successful_agent_result()

    monkeypatch.setattr(evaluator, "ask_agent", fake_agent)
    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluate_agent.py",
            "--smoke-test",
            "--smoke-count",
            "2",
        ],
    )

    exit_code = evaluator.main()

    report = json.loads(
        paths["RESULTS_JSON_PATH"].read_text(encoding="utf-8")
    )

    assert exit_code == 0
    assert len(calls) == 2
    assert report["completed"] == 2
    assert report["pending"] == 3
    assert report["complete"] is False
    assert report["passed"] == 2


def test_saved_result_is_not_reused_for_different_question():
    item = make_question(1)
    old = {
        "id": "Q001",
        "question": "A different question",
        "passed": True,
        "failure_category": "pass",
        "expected_columns": ["value"],
        "expected_rows": [[1]],
        "actual_columns": ["value"],
        "actual_rows": [[1]],
        "generated_sql": ["SELECT 1 AS value"],
        "sql_errors": [],
        "agent_answer": "Old answer",
    }

    assert evaluator.rescore_saved_record(item, old) is None


def test_saved_result_is_not_reused_when_expected_answer_changed():
    item = make_question(1)
    item["expected_rows"] = [[2]]

    old = {
        "id": "Q001",
        "question": item["question"],
        "passed": True,
        "failure_category": "pass",
        "expected_columns": ["value"],
        "expected_rows": [[1]],
        "actual_columns": ["value"],
        "actual_rows": [[1]],
        "generated_sql": ["SELECT 1 AS value"],
        "sql_errors": [],
        "agent_answer": "Old answer",
    }

    assert evaluator.rescore_saved_record(item, old) is None


def test_quota_stop_preserves_previously_saved_records(
    tmp_path, monkeypatch
):
    paths = configure_temp_paths(tmp_path, monkeypatch)

    questions = [make_question(i) for i in range(1, 6)]
    write_saved_results(
        paths["RESULTS_JSON_PATH"],
        [saved_record(item) for item in questions[:3]],
    )

    calls = []

    def fake_agent(question):
        calls.append(question)
        raise RuntimeError(
            "RateLimitError: tokens per day (TPD): limit 200000"
        )

    monkeypatch.setattr(evaluator, "ask_agent", fake_agent)
    monkeypatch.setattr(
        "sys.argv",
        ["evaluate_agent.py", "--resume"],
    )

    exit_code = evaluator.main()

    report = json.loads(
        paths["RESULTS_JSON_PATH"].read_text(encoding="utf-8")
    )
    serialized_report = json.dumps(report)

    assert exit_code == 1
    assert len(calls) == 1
    assert calls[0] == "Test question 4"
    assert report["completed"] == 4
    assert report["pending"] == 1
    assert report["complete"] is False

    # The three previously saved records must remain in the report.
    for item in questions[:3]:
        assert item["id"] in serialized_report
        assert item["question"] in serialized_report


def test_pending_only_reuses_saved_results(
    tmp_path, monkeypatch
):
    paths = configure_temp_paths(tmp_path, monkeypatch)

    questions = [make_question(i) for i in range(1, 6)]

    # Q001 was a successful result. Q002 was a deterministic failure.
    # Both should be reused instead of triggering another model call.
    old_records = [
        saved_record(questions[0]),
        saved_record(
            questions[1],
            actual_columns=[],
            actual_rows=[[1]],
        ),
    ]
    write_saved_results(paths["RESULTS_JSON_PATH"], old_records)

    calls = []

    def fake_agent(question):
        calls.append(question)
        return successful_agent_result()

    monkeypatch.setattr(evaluator, "ask_agent", fake_agent)
    monkeypatch.setattr(
        "sys.argv",
        ["evaluate_agent.py", "--pending-only"],
    )

    exit_code = evaluator.main()

    report = json.loads(
        paths["RESULTS_JSON_PATH"].read_text(encoding="utf-8")
    )
    serialized_report = json.dumps(report)

    assert exit_code == 1
    assert calls == [
        "Test question 3",
        "Test question 4",
        "Test question 5",
    ]
    assert report["completed"] == 5
    assert report["pending"] == 0

    # Previously saved questions and their failure classification survive.
    assert "Q001" in serialized_report
    assert "Q002" in serialized_report
    assert "column_count_mismatch" in serialized_report