"""AgentRuntime 主循环集成测试（用假 LLM 驱动，不依赖网络）。"""

import json

from agent.context_manager import ContextManager
from agent.output_parser import OutputParser
from agent.runtime import AgentRuntime
from agent.session_manager import SessionManager
from agent.tool_registry import ToolRegistry
from agent.tools.todo import create_todo_system


class FakeLLM:
    """按脚本逐次返回；脚本项可以是字符串(返回)或异常实例(抛出)。"""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0
        self.messages_seen = []

    def chat(self, messages, temperature=0.0):
        self.calls += 1
        self.messages_seen.append(messages)
        if not self.script:
            return _reply("done")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _tool_call(name, args, thinking=""):
    return json.dumps({"thinking": thinking, "action": "tool_call", "tool_name": name, "tool_args": args})


def _reply(text):
    return json.dumps({"thinking": "", "action": "reply", "final_answer": text})


def _runtime_with_session(llm, max_turns=10):
    sm = SessionManager()
    session = sm.create("u1")
    runtime = AgentRuntime(
        llm=llm,
        registry=ToolRegistry(),
        parser=OutputParser(),
        context=ContextManager(max_turns=max_turns),
        sessions=sm,
        max_turns=max_turns,
    )
    return runtime, session


def test_direct_reply():
    llm = FakeLLM([_reply("你好！")])
    runtime, session = _runtime_with_session(llm)
    ans = runtime.run("你好", session_id=session.session_id)
    assert ans == "你好！"
    assert llm.calls == 1


def test_tool_call_then_reply():
    llm = FakeLLM([_tool_call("calculator", {"expression": "1+2*3"}), _reply("结果是 7")])
    runtime, session = _runtime_with_session(llm)
    ans = runtime.run("1+2*3 等于多少", session_id=session.session_id)
    assert ans == "结果是 7"
    assert llm.calls == 2


def test_tool_failure_degrades_and_continues():
    llm = FakeLLM([_tool_call("calculator", {"expression": "1/0"}), _reply("无法计算")])
    runtime, session = _runtime_with_session(llm)
    ans = runtime.run("1/0", session_id=session.session_id)
    assert ans == "无法计算"
    assert [m["role"] for m in session.history] == ["user", "tool", "assistant"]


def test_max_turns_capped():
    llm = FakeLLM([_tool_call("calculator", {"expression": "1+1"})] * 20)
    runtime, session = _runtime_with_session(llm, max_turns=3)
    ans = runtime.run("算", session_id=session.session_id)
    assert "最大轮次" in ans
    assert llm.calls == 3


def test_consecutive_failures_force_answer():
    llm = FakeLLM([_tool_call("calculator", {"expression": "1/0"})] * 3 + [_reply("抱歉，算不了")])
    runtime, session = _runtime_with_session(llm)
    ans = runtime.run("算", session_id=session.session_id)
    assert ans == "抱歉，算不了"


def test_force_answer_fallback_when_llm_raises():
    llm = FakeLLM([_tool_call("calculator", {"expression": "1/0"})] * 3 + [RuntimeError("boom")])
    runtime, session = _runtime_with_session(llm)
    ans = runtime.run("算", session_id=session.session_id)
    assert "暂时无法完成" in ans


def test_llm_call_failure_returns_friendly():
    llm = FakeLLM([RuntimeError("network down")])
    runtime, session = _runtime_with_session(llm)
    ans = runtime.run("你好", session_id=session.session_id)
    assert "模型调用失败" in ans


def test_parse_retry_once_then_reply():
    llm = FakeLLM(['{"action": "tool_call", "tool_name": }', _reply("好的")])
    runtime, session = _runtime_with_session(llm)
    ans = runtime.run("算", session_id=session.session_id)
    assert ans == "好的"
    assert llm.calls == 2
    # 解析失败后追加了格式纠正提示
    assert any("系统提示" in m["content"] for m in session.history)


def test_todo_middleware_injects_reminder_in_runtime():
    todo_tool, todo_mw = create_todo_system()
    registry = ToolRegistry()
    registry.register(todo_tool)

    llm = FakeLLM([
        _tool_call("todo_write", {"name": "p", "merge": False, "todos": [{"id": "1", "content": "A", "status": "pending"}]}),
        _tool_call("calculator", {"expression": "1+1"}),
        _tool_call("calculator", {"expression": "1+1"}),
        _tool_call("calculator", {"expression": "1+1"}),
        _tool_call("calculator", {"expression": "1+1"}),
        _tool_call("calculator", {"expression": "1+1"}),
        _reply("完成"),
    ])

    sm = SessionManager()
    session = sm.create("u1")
    runtime = AgentRuntime(
        llm=llm,
        registry=registry,
        parser=OutputParser(),
        context=ContextManager(),
        sessions=sm,
        middlewares=[todo_mw],
    )
    ans = runtime.run("开始", session_id=session.session_id)
    assert ans == "完成"
    # 距上次写入 5 步后，middleware 向 prompt 注入了软提醒
    assert any(
        "todo_reminder" in m.get("content", "")
        for msgs in llm.messages_seen
        for m in msgs
    )
