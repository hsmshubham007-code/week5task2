import pytest

from evals.evaluate_agent import classify_result, rows_match_with_ties


def score(expected_rows, actual_rows, expected_columns=None):
    columns = expected_columns or ["value"]
    return classify_result(
        result={
            "columns": columns,
            "rows": actual_rows,
        },
        expected_columns=columns,
        expected_rows=expected_rows,
        sql_queries=["SELECT ..."],
        errors=[],
    )


def test_exact_results_pass():
    passed, category, _, _ = score([[59]], [[59]])
    assert passed
    assert category == "pass"


def test_rounded_average_matches_expected_value():
    passed, category, _, _ = score(
        [[5.65]],
        [[5.651941747572815]],
    )
    assert passed
    assert category == "pass"


def test_materially_different_numeric_result_fails():
    passed, category, _, _ = score([[5.65]], [[6.25]])
    assert not passed
    assert category == "row_mismatch"


def test_tied_ranked_rows_can_change_order():
    expected = [["Paris", 77.24], ["Mountain View", 77.24]]
    actual = [["Mountain View", 77.24], ["Paris", 77.24]]
    assert rows_match_with_ties(expected, actual)


def test_different_ranking_values_do_not_pass_as_ties():
    expected = [["Paris", 77.24], ["London", 75.24]]
    actual = [["London", 75.24], ["Paris", 77.24]]
    assert not rows_match_with_ties(expected, actual)


def test_column_count_mismatch_fails():
    passed, category, _, _ = classify_result(
        result={"columns": ["id", "name"], "rows": [[1, "A"]]},
        expected_columns=["id"],
        expected_rows=[[1]],
        sql_queries=["SELECT ..."],
        errors=[],
    )
    assert not passed
    assert category == "column_count_mismatch"


def test_empty_expected_and_actual_rows_pass():
    passed, category, _, _ = score([], [])
    assert passed
    assert category == "pass"
