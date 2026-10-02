"""pytest 共享 fixtures。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.llm import FakeLLM
from agent.runtime import AgentRuntime
from agent.trace import TraceLogger
from tools.calculator import CalculatorTool
from tools.registry import ToolRegistry
from tools.search import SearchTool
from tools.todo import TodoTool


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(SearchTool())
    registry.register(TodoTool())
    return registry


@pytest.fixture
def registry() -> ToolRegistry:
    return build_registry()


@pytest.fixture
def make_runtime(registry: ToolRegistry) -> Callable[..., AgentRuntime]:
    """构造带 FakeLLM 的 AgentRuntime，可注入 script 或 handler。"""

    def _make(
        script: list[str] | None = None,
        handler: Callable[
            [list[dict[str, Any]], list[dict[str, Any]] | None], str
        ]
        | None = None,
        max_step: int = 5,
        max_messages: int = 40,
        keep_recent: int = 10,
    ) -> AgentRuntime:
        llm = FakeLLM(script=script, handler=handler)
        return AgentRuntime(
            llm=llm,
            tools=registry,
            max_step=max_step,
            tracer=TraceLogger(enabled=False),
            max_messages=max_messages,
            keep_recent=keep_recent,
        )

    return _make
