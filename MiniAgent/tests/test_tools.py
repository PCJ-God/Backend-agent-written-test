"""工具单元测试。"""

from __future__ import annotations

import json

from agent.memory import Memory
from tools.base import ToolContext
from tools.registry import ToolRegistry


def test_calculator(registry: ToolRegistry) -> None:
    result = registry.execute("calculator", {"expression": "123*456"})
    assert not result.error
    assert json.loads(result.content)["result"] == 56088


def test_calculator_injection_blocked(registry: ToolRegistry) -> None:
    """非法表达式（如函数调用）应被拒绝。"""
    result = registry.execute("calculator", {"expression": "__import__('os')"})
    assert result.error
    assert "error" in json.loads(result.content)


def test_calculator_division_by_zero(registry: ToolRegistry) -> None:
    result = registry.execute("calculator", {"expression": "1/0"})
    assert result.error


def test_search(registry: ToolRegistry) -> None:
    result = registry.execute("search", {"query": "东京天气"})
    assert not result.error
    assert "25" in json.loads(result.content)["result"]


def test_todo_add_and_list(registry: ToolRegistry) -> None:
    ctx = ToolContext(session_id="s", memory=Memory())
    registry.execute("todo", {"action": "add", "task": "下午提交报告"}, context=ctx)
    result = registry.execute("todo", {"action": "list"}, context=ctx)
    assert "下午提交报告" in json.loads(result.content)["todos"]


def test_todo_missing_task(registry: ToolRegistry) -> None:
    ctx = ToolContext(session_id="s", memory=Memory())
    result = registry.execute("todo", {"action": "add"}, context=ctx)
    assert result.error


def test_unknown_tool(registry: ToolRegistry) -> None:
    result = registry.execute("nonexistent", {})
    assert result.error
    assert "未知工具" in result.content
