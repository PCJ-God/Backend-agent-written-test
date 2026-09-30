"""真实 LLM 冒烟测试（可选）：需配置 API Key 才执行，默认跳过。

运行方式（二选一）：
    python -m pytest tests/test_llm_smoke.py -v
    python tests/test_llm_smoke.py
"""

import importlib.util
import os
import sys

import pytest

# 支持直接 `python tests/test_llm_smoke.py` 运行：把项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_HAS_OPENAI = importlib.util.find_spec("openai") is not None
_HAS_KEY = bool(
    os.getenv("OPENAI_API_KEY")
    or os.getenv("LLM_API_KEY")
    or os.getenv("DEEPSEEK_API_KEY")
    or os.getenv("API_KEY")
)

pytestmark = pytest.mark.skipif(
    not (_HAS_OPENAI and _HAS_KEY),
    reason="缺少 openai 库或 API Key，跳过真实 LLM 冒烟测试（可选）",
)

from agent.context_manager import ContextManager
from agent.llm_client import LLMClient
from agent.output_parser import OutputParser
from agent.runtime import AgentRuntime
from agent.session_manager import SessionManager
from agent.tool_registry import ToolRegistry


def test_real_llm_calculator_roundtrip():
    runtime = AgentRuntime(
        llm=LLMClient(),
        registry=ToolRegistry(),
        parser=OutputParser(),
        context=ContextManager(),
        sessions=SessionManager(),
    )
    answer = runtime.run("请用 calculator 工具计算 12*34 等于多少")
    assert isinstance(answer, str) and answer
    assert any(
        e.get("event") == "tool" and e.get("tool") == "calculator"
        for e in runtime.trace.entries
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
