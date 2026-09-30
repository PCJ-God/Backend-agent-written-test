"""calculator 工具：安全计算数学表达式。"""

import ast
import operator
from typing import Any, Dict

NAME = "calculator"
DESCRIPTION = "安全计算数学表达式，支持四则运算、幂、取模与括号，例如 '1+2*3'。"
PARAMETERS = {
    "type": "object",
    "properties": {
        "expression": {"type": "string", "description": "数学表达式"},
    },
    "required": ["expression"],
}

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


def _eval(node: ast.AST) -> Any:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval(node.operand))
    raise ValueError(f"不支持的表达式元素: {type(node).__name__}")


def execute(args: Dict[str, Any], session=None) -> Dict[str, Any]:
    """执行计算；非法表达式 / 除零返回错误对象，不抛异常。"""
    expression = str(args.get("expression", "")).strip()
    if not expression:
        return {"ok": False, "error": "缺少 expression 参数"}
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval(tree)
    except ZeroDivisionError:
        return {"ok": False, "error": "除零错误"}
    except Exception as exc:
        return {"ok": False, "error": f"表达式非法: {exc}"}
    return {"ok": True, "expression": expression, "result": result}


TOOL = {"name": NAME, "description": DESCRIPTION, "parameters": PARAMETERS, "execute": execute}
