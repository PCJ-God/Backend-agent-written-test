"""搜索工具：模拟搜索能力。"""

from __future__ import annotations

import json
from typing import Any

from tools.base import Tool, ToolContext

_KNOWLEDGE = {
    "东京": "东京今天25℃, 晴",
    "北京": "北京今天18℃, 多云",
    "上海": "上海今天22℃, 小雨",
    "深圳": "深圳今天28℃, 晴",
}


class SearchTool(Tool):
    name = "search"
    description = "模拟搜索：查询天气、城市信息等"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词，例如 东京天气"}
        },
        "required": ["query"],
    }

    def run(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> str:
        query = str(arguments.get("query", "")).strip()
        if not query:
            raise ValueError("query 参数不能为空")
        for key, value in _KNOWLEDGE.items():
            if key in query:
                return json.dumps({"query": query, "result": value}, ensure_ascii=False)
        return json.dumps(
            {"query": query, "result": f"未找到关于 '{query}' 的详细信息"},
            ensure_ascii=False,
        )
