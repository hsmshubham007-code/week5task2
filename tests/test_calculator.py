import pytest

from src.calculator import calculate


def test_addition():
    assert calculate("12 + 8")["result"] == 20


def test_revenue_calculation():
    assert calculate("19.99 * 3")["result"] == pytest.approx(59.97)


def test_division():
    assert calculate("100 / 4")["result"] == 25


def test_parentheses():
    assert calculate("(10 + 5) * 2")["result"] == 30


def test_rejects_division_by_zero():
    with pytest.raises(ValueError, match="zero"):
        calculate("10 / 0")


def test_rejects_function_calls():
    with pytest.raises(ValueError):
        calculate("__import__('os').system('whoami')")


def test_rejects_non_numeric_values():
    with pytest.raises(ValueError):
        calculate("'hello' + 'world'")


def test_rejects_excessive_expression():
    with pytest.raises(ValueError, match="long"):
        calculate("1" * 201)
