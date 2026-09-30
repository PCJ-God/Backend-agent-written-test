"""search 工具：演示用，返回 mock 结果。"""

from typing import Any, Dict

NAME = "search"
DESCRIPTION = "搜索信息（演示用 mock，返回本地固定结果）。"
PARAMETERS = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "搜索关键词"},
        "top_k": {"type": "integer", "description": "返回条数，默认 3"},
    },
    "required": ["query"],
}

_MOCK_DB = [
    {"title": "Python 官方文档", "snippet": "Python 编程语言的官方教程与标准库参考。", "url": "https://docs.python.org/"},
    {"title": "OpenAI API 文档", "snippet": "OpenAI 兼容接口的模型调用说明。", "url": "https://platform.openai.com/docs"},
    {"title": "天气示例", "snippet": "示例：北京今日晴，15~24℃。", "url": "https://example.com/weather"},
]


def execute(args: Dict[str, Any], session=None) -> Dict[str, Any]:
    query = str(args.get("query", "")).strip()
    if not query:
        return {"ok": False, "error": "缺少 query 参数"}
    try:
        top_k = int(args.get("top_k", 3))
    except (TypeError, ValueError):
        top_k = 3
    top_k = max(1, min(top_k, 10))

    hits = [r for r in _MOCK_DB if query.lower() in r["title"].lower() or query.lower() in r["snippet"].lower()]
    if not hits:
        hits = [{"title": f"关于「{query}」的演示结果", "snippet": f"这是「{query}」的 mock 搜索摘要。", "url": "https://example.com/search"}]
    return {"ok": True, "results": hits[:top_k]}


TOOL = {"name": NAME, "description": DESCRIPTION, "parameters": PARAMETERS, "execute": execute}
