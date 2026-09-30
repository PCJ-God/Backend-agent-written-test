"""calculator / search / todo 工具单元测试。"""

from agent.session_manager import Session
from agent.tools import calculator, search
from agent.tools.todo import create_todo_system


# ---------- calculator ----------

def test_calculator_valid():
    assert calculator.execute({"expression": "1+2*3"})["result"] == 7


def test_calculator_precedence():
    assert calculator.execute({"expression": "(1+2)*3"})["result"] == 9


def test_calculator_power():
    assert calculator.execute({"expression": "2**10"})["result"] == 1024


def test_calculator_division_by_zero():
    r = calculator.execute({"expression": "1/0"})
    assert r["ok"] is False
    assert "除零" in r["error"]


def test_calculator_invalid_expression():
    r = calculator.execute({"expression": "1 +"})
    assert r["ok"] is False


def test_calculator_blocks_injection():
    r = calculator.execute({"expression": "__import__('os').system('echo x')"})
    assert r["ok"] is False


def test_calculator_missing_expression():
    r = calculator.execute({})
    assert r["ok"] is False


# ---------- search ----------

def test_search_mock_returns_results():
    r = search.execute({"query": "Python"})
    assert r["ok"] is True
    assert len(r["results"]) >= 1


def test_search_missing_query():
    r = search.execute({})
    assert r["ok"] is False


def test_search_top_k():
    r = search.execute({"query": "Python", "top_k": 1})
    assert len(r["results"]) == 1


# ---------- todo_write 系统 ----------

def _session(sid="s1"):
    return Session(session_id=sid, user_id="u1")


def test_todo_replace_builds_list():
    tool, _ = create_todo_system()
    r = tool["execute"]({"name": "plan", "merge": False, "todos": [
        {"id": "1", "content": "任务A", "status": "pending"},
        {"id": "2", "content": "任务B", "status": "pending"},
    ]}, session=_session())
    assert r["ok"] is True
    assert [t["content"] for t in r["todos"]] == ["任务A", "任务B"]
    assert "0/2 completed" in r["summary"]


def test_todo_merge_updates_by_id():
    tool, mw = create_todo_system()
    s = _session()
    mw.before_step(s, 1)
    tool["execute"]({"name": "plan", "merge": False, "todos": [
        {"id": "1", "content": "任务A", "status": "pending"},
        {"id": "2", "content": "任务B", "status": "pending"},
    ]}, session=s)
    mw.before_step(s, 2)
    r = tool["execute"]({"name": "plan", "merge": True, "todos": [
        {"id": "1", "content": "任务A", "status": "completed"},
        {"id": "3", "content": "任务C", "status": "in_progress"},
    ]}, session=s)
    assert r["ok"] is True
    assert [t["status"] for t in r["todos"]] == ["completed", "pending", "in_progress"]
    assert "1/3 completed" in r["summary"]


def test_todo_concurrent_write_protected():
    tool, mw = create_todo_system()
    s = _session()
    mw.before_step(s, 1)
    r1 = tool["execute"]({"name": "p", "merge": False, "todos": [{"id": "1", "content": "A", "status": "pending"}]}, session=s)
    r2 = tool["execute"]({"name": "p", "merge": False, "todos": [{"id": "2", "content": "B", "status": "pending"}]}, session=s)
    assert r1["ok"] is True
    assert r2["ok"] is False
    assert "只有第一次生效" in r2["error"]
    # 新 step 计数器清零，可再次写入
    mw.before_step(s, 2)
    r3 = tool["execute"]({"name": "p", "merge": True, "todos": [{"id": "2", "content": "B", "status": "pending"}]}, session=s)
    assert r3["ok"] is True


def test_todo_invalid_status():
    tool, _ = create_todo_system()
    r = tool["execute"]({"name": "p", "merge": False, "todos": [{"id": "1", "content": "A", "status": "done"}]}, session=_session())
    assert r["ok"] is False


def test_todo_missing_merge():
    tool, _ = create_todo_system()
    r = tool["execute"]({"name": "p", "todos": [{"id": "1", "content": "A", "status": "pending"}]}, session=_session())
    assert r["ok"] is False


def test_todo_state_isolated_per_session():
    tool, mw = create_todo_system()
    s1 = _session("s1")
    s2 = _session("s2")
    mw.before_step(s1, 1)
    tool["execute"]({"name": "p", "merge": False, "todos": [{"id": "1", "content": "A", "status": "pending"}]}, session=s1)
    mw.before_step(s2, 1)
    tool["execute"]({"name": "p", "merge": False, "todos": [{"id": "2", "content": "B", "status": "pending"}]}, session=s2)
    mw.before_step(s1, 2)
    r1 = tool["execute"]({"name": "p", "merge": True, "todos": []}, session=s1)
    mw.before_step(s2, 2)
    r2 = tool["execute"]({"name": "p", "merge": True, "todos": []}, session=s2)
    assert [t["content"] for t in r1["todos"]] == ["A"]
    assert [t["content"] for t in r2["todos"]] == ["B"]


def test_reminder_injected_after_idle_steps():
    tool, mw = create_todo_system()
    s = _session()
    tool["execute"]({"name": "p", "merge": False, "todos": [{"id": "1", "content": "A", "status": "pending"}]}, session=s)
    messages = [{"role": "system", "content": "sys"}]
    for _ in range(4):
        assert mw.before_model(s, messages) is None
    out = mw.before_model(s, messages)
    assert out is not None
    assert "todo_reminder" in out[0]["content"]
    # 提醒后计数器归零，紧接着不再连环提醒
    assert mw.before_model(s, messages) is None


def test_after_tool_use_resets_write_counter():
    tool, mw = create_todo_system()
    s = _session()
    tool["execute"]({"name": "p", "merge": False, "todos": [{"id": "1", "content": "A", "status": "pending"}]}, session=s)
    for _ in range(4):
        mw.before_model(s, [{"role": "system", "content": "sys"}])
    mw.after_tool_use(s, "todo_write", {}, {})
    for _ in range(4):
        assert mw.before_model(s, [{"role": "system", "content": "sys"}]) is None
