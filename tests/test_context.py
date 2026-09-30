"""context 组装与压缩单元测试。"""

from agent.context_manager import ContextManager
from agent.session_manager import Session
from agent.tool_registry import ToolRegistry
from agent.tools.todo import create_todo_system


def _schemas():
    registry = ToolRegistry()
    todo_tool, _ = create_todo_system()
    registry.register(todo_tool)
    return registry.schemas()


def test_build_starts_with_system_and_tools():
    cm = ContextManager()
    s = Session(session_id="s", user_id="u")
    s.append("user", "你好")
    msgs = cm.build(s, _schemas())
    assert msgs[0]["role"] == "system"
    assert "calculator" in msgs[0]["content"]
    assert "search" in msgs[0]["content"]
    assert "todo_write" in msgs[0]["content"]
    assert msgs[1] == {"role": "user", "content": "你好"}


def test_tool_result_converted_to_user_role():
    cm = ContextManager()
    s = Session(session_id="s", user_id="u")
    s.append("user", "算")
    s.append("tool", '{"ok": true, "result": 7}')
    msgs = cm.build(s, _schemas())
    tool_msg = msgs[2]
    assert tool_msg["role"] == "user"
    assert tool_msg["content"].startswith("[工具执行结果]")


def test_compression_truncates_history():
    cm = ContextManager(compress_threshold=50, keep_recent=2)
    s = Session(session_id="s", user_id="u")
    for i in range(6):
        s.append("user", f"消息{i}" * 20)  # 每条约 60 字符
    msgs = cm.build(s, _schemas())
    history = msgs[1:]
    assert len(history) == 2
    assert "消息4" in history[0]["content"]
    assert "省略" in msgs[0]["content"]


def test_no_compression_under_threshold():
    cm = ContextManager(compress_threshold=100000, keep_recent=2)
    s = Session(session_id="s", user_id="u")
    s.append("user", "短消息")
    msgs = cm.build(s, _schemas())
    assert len(msgs) == 2  # system + user
    assert "省略" not in msgs[0]["content"]
