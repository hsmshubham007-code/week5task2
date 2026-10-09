from __future__ import annotations

import ast
import math
import operator
from typing import Union


Number = Union[int, float]

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def calculate(expression: str) -> dict[str, Number | str]:
    """Safely evaluate a basic arithmetic expression without using eval()."""
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("Expression must be a non-empty string.")

    if len(expression) > 200:
        raise ValueError("Expression is too long.")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("Invalid arithmetic expression.") from exc

    def evaluate(node: ast.AST) -> Number:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)

        if isinstance(node, ast.Constant):
            if (
                isinstance(node.value, bool)
                or not isinstance(node.value, (int, float))
            ):
                raise ValueError("Only numeric values are allowed.")
            return node.value

        if isinstance(node, ast.BinOp):
            operation = _ALLOWED_OPERATORS.get(type(node.op))
            if operation is None:
                raise ValueError("Unsupported arithmetic operator.")

            left = evaluate(node.left)
            right = evaluate(node.right)

            if isinstance(node.op, ast.Pow) and abs(right) > 10:
                raise ValueError("Exponent magnitude must not exceed 10.")

            if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
                if right == 0:
                    raise ValueError("Division by zero is not allowed.")

            result = operation(left, right)

            if not isinstance(result, (int, float)):
                raise ValueError("Expression did not produce a number.")

            if not math.isfinite(result):
                raise ValueError("Result must be finite.")

            if abs(result) > 1e100:
                raise ValueError("Result magnitude is too large.")

            return result

        if isinstance(node, ast.UnaryOp):
            operation = _ALLOWED_OPERATORS.get(type(node.op))
            if operation is None:
                raise ValueError("Unsupported unary operator.")
            return operation(evaluate(node.operand))

        raise ValueError("Only basic arithmetic expressions are allowed.")

    result = evaluate(tree)

    return {
        "expression": expression,
        "result": result,
    }