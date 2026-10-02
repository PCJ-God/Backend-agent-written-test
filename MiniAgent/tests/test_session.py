"""Session 与 Context 测试：隔离、压缩。"""

from __future__ import annotations

import json
from typing import Any

from agent.runtime import AgentRuntime


def answer(content: str) -> str:
    return json.dumps({"type": "answer", "content": content}, ensure_ascii=False)


def test_session_isolation(make_runtime) -> None:
    """Test Case 4：两个 session 的历史互不影响。"""
    rt = make_runtime(script=[answer("天气25℃"), answer("周报已写")])
    rt.run("查询天气", session_id="s1")
    rt.run("写周报", session_id="s2")

    s1_text = json.dumps(rt.sessions.get("s1").messages(), ensure_ascii=False)
    s2_text = json.dumps(rt.sessions.get("s2").messages(), ensure_ascii=False)

    assert "查询天气" in s1_text and "写周报" not in s1_text
    assert "写周报" in s2_text and "查询天气" not in s2_text


def test_context_compression(make_runtime) -> None:
    """Test Case 6：30 轮聊天后 context 长度显著降低。"""
    rt = make_runtime(
        handler=lambda messages, tools: answer("ok"),
        max_messages=20,
        keep_recent=6,
    )
    for i in range(30):
        rt.run(f"第{i}轮", session_id="c")

    messages = rt.sessions.get("c").messages()
    assert len(messages) < 30 * 2  # 未压缩时会是 60 条
    assert messages[0]["role"] == "system"
    assert "历史摘要" in messages[0]["content"]
