"""Tool 抽象接口：所有工具的统一契约。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

from agent.memory import Memory


@dataclass
class ToolContext:
    """执行工具时可用的上下文。"""

    session_id: str
    memory: Memory


@dataclass
class ToolResult:
    """工具执行结果。"""

    name: str
    content: str
    error: bool = False


class Tool(ABC):
    """所有工具必须提供 name / description / parameters 与 run。"""

    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    parameters: ClassVar[dict[str, Any]] = {}

    @abstractmethod
    def run(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> str:
        """执行工具并返回结果字符串（建议 JSON）。"""

    def schema(self) -> dict[str, Any]:
        """返回工具的 JSON Schema 描述。"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
