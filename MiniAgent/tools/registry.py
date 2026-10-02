"""工具注册机制：注册、查询、按名称执行。"""

from __future__ import annotations

import json
from typing import Any

from tools.base import Tool, ToolContext, ToolResult


class ToolRegistry:
    """管理全部工具，负责注册、获取 schema 与执行。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """注册一个工具。"""
        if not tool.name:
            raise ValueError("工具缺少 name")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def schema(self) -> list[dict[str, Any]]:
        """返回所有工具的 schema，供 LLM 决策。"""
        return [tool.schema() for tool in self._tools.values()]

    def execute(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        context: ToolContext | None = None,
    ) -> ToolResult:
        """按名称执行工具，异常统一转为 {"error": ...} 结果。"""
        arguments = arguments or {}
        tool = self.get(name)
        if tool is None:
            return ToolResult(
                name=name,
                content=json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False),
                error=True,
            )
        try:
            content = tool.run(arguments, context)
            return ToolResult(name=name, content=content)
        except Exception as exc:  # 工具异常 -> 统一错误格式
            return ToolResult(
                name=name,
                content=json.dumps({"error": str(exc)}, ensure_ascii=False),
                error=True,
            )
