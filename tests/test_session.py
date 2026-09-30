"""session 管理单元测试。"""

from agent.session_manager import SessionManager


def test_create_generates_unique_ids():
    sm = SessionManager()
    s1 = sm.create("u1")
    s2 = sm.create("u1")
    assert s1.session_id != s2.session_id
    assert s1.user_id == "u1"


def test_get_or_create_returns_existing():
    sm = SessionManager()
    s = sm.create("u1", session_id="win1")
    assert sm.get_or_create("u1", "win1") is s


def test_get_or_create_creates_when_missing():
    sm = SessionManager()
    s = sm.get_or_create("u1", "win2")
    assert s is not None
    assert sm.get("win2") is s


def test_sessions_isolated_history():
    sm = SessionManager()
    s1 = sm.create("u1")
    s2 = sm.create("u1")
    s1.append("user", "窗口1的消息")
    s2.append("user", "窗口2的消息")
    assert [m["content"] for m in s1.history] == ["窗口1的消息"]
    assert [m["content"] for m in s2.history] == ["窗口2的消息"]


def test_resume_continues_history():
    sm = SessionManager()
    s = sm.create("u1", session_id="win1")
    s.append("user", "第一句")
    s.append("assistant", "第一答")
    resumed = sm.get_or_create("u1", "win1")
    assert len(resumed.history) == 2
    resumed.append("user", "追问")
    assert len(s.history) == 3
