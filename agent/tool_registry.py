"""工具注册机制：名称 + 描述 + 参数 Schema。"""

from typing import Any, Dict, List, Optional

from .tools import calculator, search


class ToolRegistry:
    def __init__(self, tools=None) -> None:
        self._tools: Dict[str, Dict[str, Any]] = {}
        # 默认只注册无状态工具；todo 系统需由 create_todo_system() 显式挂载
        for tool in (tools if tools is not None else [calculator.TOOL, search.TOOL]):
            self.register(tool)

    def register(self, tool: Dict[str, Any]) -> None:
        self._tools[tool["name"]] = tool

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        return name in self._tools

    def schemas(self) -> List[Dict[str, Any]]:
        """返回注入到 system prompt 的工具清单。"""
        return [
            {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}
            for t in self._tools.values()
        ]

    def execute(self, name: str, args: Dict[str, Any], session=None) -> Dict[str, Any]:
        """执行工具；工具抛异常时降级为错误对象，不向上传播。"""
        tool = self._tools.get(name)
        if tool is None:
            return {"ok": False, "error": f"未注册的工具: {name}"}
        try:
            if not isinstance(args, dict):
                args = {}
            return tool["execute"](args, session=session)
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
