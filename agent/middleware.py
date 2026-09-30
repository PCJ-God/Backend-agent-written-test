"""Agent middleware：主循环在每个 step 的前/中/后调用的横切钩子。"""

from typing import Any, Dict, List, Optional


class Middleware:
    """横切关注点基类。所有钩子默认空实现，返回 None 表示不改动。"""

    def before_step(self, session, turn: int) -> None:
        """每个 step（主循环迭代）开头调用一次。"""

    def before_model(self, session, messages: List[Dict[str, str]]) -> Optional[List[Dict[str, str]]]:
        """每次调用 LLM 前调用，可返回修改后的 messages；返回 None 表示不改动。"""
        return None

    def after_tool_use(self, session, tool_name: str, args: Dict[str, Any], result: Dict[str, Any]) -> None:
        """每次工具执行后调用。"""
