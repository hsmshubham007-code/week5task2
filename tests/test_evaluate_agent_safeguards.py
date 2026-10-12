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