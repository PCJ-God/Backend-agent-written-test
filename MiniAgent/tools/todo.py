"""待办工具：任务管理（添加 / 查看）。"""

from __future__ import annotations

import json
from typing import Any

from tools.base import Tool, ToolContext


class TodoTool(Tool):
    name = "todo"
    description = "任务管理：添加待办（action=add, task=内容）或查看待办（action=list）"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "list"],
                "description": "add=添加任务, list=查看任务",
            },
            "task": {"type": "string", "description": "任务内容，action=add 时必填"},
        },
        "required": ["action"],
    }

    def run(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> str:
        action = str(arguments.get("action", "")).strip()
        sid = context.session_id if context else "default"
        memory = context.memory if context else None

        todos: list[str] = list(memory.recall(sid, "todos", []) if memory else [])

        if action == "add":
            task = str(arguments.get("task", "")).strip()
            if not task:
                raise ValueError("task 参数不能为空")
            todos.append(task)
            if memory:
                memory.remember(sid, "todos", todos)
            return json.dumps(
                {"result": f"已添加任务: {task}", "todos": todos}, ensure_ascii=False
            )

        if action == "list":
            return json.dumps({"todos": todos}, ensure_ascii=False)

        raise ValueError(f"未知 action: {action}（仅支持 add / list）")
