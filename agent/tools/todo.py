"""todo 系统：todo_write 工具 + 反应式提醒 middleware（共享同一份状态）。

设计要点：
- 清单状态由工厂函数的闭包持有，按 session_id 隔离；
- 工具是写入端，middleware 是观察端，两者必须来自同一次 create_todo_system()；
- middleware 在 LLM「写完就忘」时向 prompt 注入软提醒，督促持续更新。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..middleware import Middleware

TOOL_NAME = "todo_write"

PENDING = "pending"
IN_PROGRESS = "in_progress"
COMPLETED = "completed"
_STATUSES = (PENDING, IN_PROGRESS, COMPLETED)

_MARKER = {PENDING: "[ ]", IN_PROGRESS: "[>]", COMPLETED: "[x]"}


def _marker(status: Any) -> str:
    return _MARKER.get(status, "[ ]")

# 距上次写入超过 5 步算「可能忘了」；两次提醒之间至少隔 5 步，避免连环轰炸
STEPS_SINCE_WRITE = 5
STEPS_BETWEEN_REMINDERS = 5

CONCURRENT_WRITE_ERROR = (
    "Error: todo_write 在本轮已经调用过了。多次并发调用会产生歧义状态，只有第一次生效。"
    "请把所有更新合并成下一轮的一次调用。"
)


@dataclass
class _TodoState:
    todo_list: List[Dict[str, Any]] = field(default_factory=list)
    steps_since_last_write: int = 0
    steps_since_last_reminder: int = 0
    invocations_this_step: int = 0


def _format_summary(name: str, todo_list: List[Dict[str, Any]]) -> str:
    completed = sum(1 for t in todo_list if t.get("status") == COMPLETED)
    lines = [f"{i + 1}. {_marker(t.get('status'))} {t.get('content', '')}" for i, t in enumerate(todo_list)]
    body = "\n".join(lines) if lines else "（空清单）"
    return f'Plan "{name}" updated, {completed}/{len(todo_list)} completed.\n{body}'


def _format_reminder(todo_list: List[Dict[str, Any]]) -> str:
    lines = [f"{i + 1}. {_marker(t.get('status'))} {t.get('content', '')}" for i, t in enumerate(todo_list)]
    body = "\n".join(lines) if lines else "（空清单）"
    return (
        "\n<todo_reminder>\n"
        "todo_write 工具有一阵没用了。如果你正在做的任务适合用清单跟踪，可以考虑更新一下。\n"
        "仅在与当前工作相关时才使用。当前清单：\n\n"
        f"{body}\n"
        "</todo_reminder>"
    )


def create_todo_system():
    """返回 (tool, middleware)。两者共享同一份状态，必须配对使用。"""
    states: Dict[str, _TodoState] = {}

    def _state(session) -> _TodoState:
        key = session.session_id if session is not None else "__default__"
        return states.setdefault(key, _TodoState())

    def execute(args: Dict[str, Any], session=None) -> Dict[str, Any]:
        st = _state(session)

        # 并发写防护：一个 step 内只认第一次
        st.invocations_this_step += 1
        if st.invocations_this_step > 1:
            return {"ok": False, "error": CONCURRENT_WRITE_ERROR}

        name = str(args.get("name") or "").strip() or "todo"
        merge = args.get("merge")
        if not isinstance(merge, bool):
            return {"ok": False, "error": "merge 必须为布尔值：true 按 id 增量合并，false 整表替换"}

        todos = args.get("todos")
        if not isinstance(todos, list):
            return {"ok": False, "error": "todos 必须是数组"}

        cleaned: List[Dict[str, Any]] = []
        for item in todos:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("id") or "").strip()
            content = str(item.get("content") or "").strip()
            status = item.get("status")
            if status not in _STATUSES:
                return {"ok": False, "error": f"非法 status: {status}（支持 pending/in_progress/completed）"}
            if not item_id or not content:
                return {"ok": False, "error": "每个 todo 项都需要 id 和 content"}
            cleaned.append({"id": item_id, "content": content, "status": status})

        if merge:
            # 按 id 打补丁：已存在的 id 原地更新，新 id 追加
            for item in cleaned:
                idx = next((i for i, t in enumerate(st.todo_list) if t["id"] == item["id"]), -1)
                if idx >= 0:
                    st.todo_list[idx] = item
                else:
                    st.todo_list.append(item)
        else:
            # 整表替换
            st.todo_list[:] = cleaned

        st.steps_since_last_write = 0
        return {
            "ok": True,
            "action": "merge" if merge else "replace",
            "todos": list(st.todo_list),
            "summary": _format_summary(name, st.todo_list),
        }

    class TodoMiddleware(Middleware):
        def before_step(self, session, turn: int) -> None:
            _state(session).invocations_this_step = 0

        def before_model(self, session, messages):
            st = _state(session)
            st.steps_since_last_write += 1
            st.steps_since_last_reminder += 1

            if (
                st.todo_list
                and st.steps_since_last_write >= STEPS_SINCE_WRITE
                and st.steps_since_last_reminder >= STEPS_BETWEEN_REMINDERS
            ):
                st.steps_since_last_reminder = 0
                new_messages = list(messages)
                reminder = _format_reminder(st.todo_list)
                if new_messages and new_messages[0].get("role") == "system":
                    new_messages[0] = {"role": "system", "content": new_messages[0]["content"] + reminder}
                else:
                    new_messages.insert(0, {"role": "system", "content": reminder})
                return new_messages
            return None

        def after_tool_use(self, session, tool_name, args, result):
            if tool_name == TOOL_NAME:
                _state(session).steps_since_last_write = 0

    tool = {
        "name": TOOL_NAME,
        "description": (
            "管理任务清单。参数：name（计划短标签，更新同一计划时复用同名）、"
            "todos（数组，每项含 id/content/status）、merge（true 按 id 增量合并，false 整表替换）。"
            "status 取 pending / in_progress / completed。首次建表用 merge=false，之后增量更新用 merge=true。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "这批 todo 所属计划的短标签，更新同一计划时复用同名"},
                "merge": {"type": "boolean", "description": "true 按 id 增量合并，false 整表替换"},
                "todos": {
                    "type": "array",
                    "description": "todo 项数组",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "todo 项唯一 id"},
                            "content": {"type": "string", "description": "任务描述"},
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                                "description": "任务状态",
                            },
                        },
                        "required": ["id", "content", "status"],
                    },
                },
            },
            "required": ["name", "todos", "merge"],
        },
        "execute": execute,
    }

    return tool, TodoMiddleware()
