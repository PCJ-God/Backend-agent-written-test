"""计算器工具：安全地计算数学表达式。"""

from __future__ import annotations

import ast
import json
import operator
from typing import Any

from tools.base import Tool, ToolContext

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def safe_eval(expression: str) -> float | int:
    """基于 AST 的安全表达式求值，杜绝 eval 注入。"""

    def _eval(node: ast.AST) -> float | int:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp):
            op = _BIN_OPS.get(type(node.op))
            if op is None:
                raise ValueError(f"不支持的运算符: {type(node.op).__name__}")
            return op(_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp):
            op = _UNARY_OPS.get(type(node.op))
            if op is None:
                raise ValueError(f"不支持的一元运算符: {type(node.op).__name__}")
            return op(_eval(node.operand))
        raise ValueError(f"不支持的表达式: {type(node).__name__}")

    tree = ast.parse(expression, mode="eval")
    return _eval(tree)


class CalculatorTool(Tool):
    name = "calculator"
    description = "计算数学表达式，支持 + - * / // % ** 和括号"
    parameters = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "数学表达式，例如 1+1 或 (100+200)*3",
            }
        },
        "required": ["expression"],
    }

    def run(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> str:
        expression = str(arguments.get("expression", "")).strip()
        if not expression:
            raise ValueError("expression 参数不能为空")
        result = safe_eval(expression)
        return json.dumps(
            {"expression": expression, "result": result}, ensure_ascii=False
        )
