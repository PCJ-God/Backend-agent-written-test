"""Agent 行为测试：聊天、工具调用、多工具、上下文追问。"""

from __future__ import annotations

import json
from typing import Any

from agent.runtime import AgentRuntime


def answer(content: str) -> str:
    return json.dumps({"type": "answer", "content": content}, ensure_ascii=False)


def tool_call(tool: str, arguments: dict[str, Any]) -> str:
    return json.dumps(
        {"type": "tool_call", "tool": tool, "arguments": arguments},
        ensure_ascii=False,
    )


def tool_messages(rt: AgentRuntime, session_id: str) -> list[dict[str, Any]]:
    return [
        m for m in rt.sessions.get(session_id).messages() if m.get("role") == "tool"
    ]


def test_normal_chat(make_runtime) -> None:
    """Test Case 1：普通聊天，Agent 直接回答。"""
    rt = make_runtime(script=[answer("你好！有什么可以帮你？")])
    out = rt.run("你好", session_id="t1")
    assert out == "你好！有什么可以帮你？"


def test_calculator_tool_call(make_runtime) -> None:
    """Test Case 2：计算工具调用。"""
    rt = make_runtime(
        script=[
            tool_call("calculator", {"expression": "100+200"}),
            answer("结果是300"),
        ]
    )
    out = rt.run("计算100+200", session_id="t2")
    assert out == "结果是300"

    tools = tool_messages(rt, "t2")
    assert tools, "calculator 未被调用"
    assert tools[-1]["name"] == "calculator"
    assert json.loads(tools[-1]["content"])["result"] == 300


def test_multi_tool_call(make_runtime) -> None:
    """Test Case 3：多工具调用 search -> todo -> answer。"""
    rt = make_runtime(
        script=[
            tool_call("search", {"query": "东京天气"}),
            tool_call("todo", {"action": "add", "task": "查询东京天气"}),
            answer("已查询天气并添加待办"),
        ]
    )
    out = rt.run("查询天气并添加待办", session_id="t3")
    assert out == "已查询天气并添加待办"

    tools = tool_messages(rt, "t3")
    assert [t["name"] for t in tools] == ["search", "todo"]
    assert rt.sessions.get("t3").messages()[-1]["role"] == "assistant"


def test_context_followup(make_runtime) -> None:
    """Test Case 5：上下文追问——第二轮利用历史信息调用 todo。"""

    def handler(
        messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> str:
        last = messages[-1]
        content = last.get("content", "")
        if last.get("role") == "user" and "天气" in content:
            return tool_call("search", {"query": "东京天气"})
        if last.get("role") == "user" and "记" in content:
            weather = ""
            for m in messages:
                if m.get("role") == "tool" and m.get("name") == "search":
                    weather = json.loads(m["content"]).get("result", "")
            return tool_call("todo", {"action": "add", "task": f"东京天气：{weather}"})
        return answer("好的，已完成")

    rt = make_runtime(handler=handler)
    rt.run("东京天气", session_id="t5")
    out = rt.run("帮我记下来", session_id="t5")
    assert "已完成" in out

    todo_msgs = [
        m for m in rt.sessions.get("t5").messages()
        if m.get("role") == "tool" and m.get("name") == "todo"
    ]
    assert todo_msgs, "第二轮应调用 todo"
    last_todo = json.loads(todo_msgs[-1]["content"])
    assert "25" in last_todo["todos"][-1]


def test_max_step_limit(make_runtime) -> None:
    """超过 MAX_STEP 后必须停止，防止死循环。"""
    rt = make_runtime(
        handler=lambda messages, tools: tool_call("calculator", {"expression": "1+1"}),
        max_step=3,
    )
    out = rt.run("一直算", session_id="t6")
    assert "最大循环次数" in out
    # 循环次数受 max_step 限制
    assert len(rt.llm.calls) == 3
