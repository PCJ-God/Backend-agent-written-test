"""context 组装：system 提示 + 历史 + 基础压缩。"""

import json
from typing import Any, Dict, List

_SYSTEM_TEMPLATE = (
    "你是一个能调用工具的助手。根据用户输入决定「直接回复」还是「调用工具」。\n\n"
    "可用工具（JSON Schema）：\n{tools_json}\n\n"
    "请严格按如下 JSON 输出，不要输出多余文字或 markdown 代码块：\n"
    '{{"thinking": "思考过程", "action": "reply 或 tool_call", '
    '"tool_name": "工具名（仅 tool_call）", "tool_args": {{}}, '
    '"final_answer": "最终答案（仅 reply）"}}\n\n'
    "规则：\n"
    "1. 需要计算 / 搜索 / 记待办时用 tool_call，其余用 reply；\n"
    "2. 每轮只调用一个工具，工具结果会在下一轮交给你；\n"
    "3. 拿到工具结果后，最终必须用 reply 输出自然语言答案。"
)


class ContextManager:
    def __init__(self, max_turns: int = 10, compress_threshold: int = 4000, keep_recent: int = 8) -> None:
        self.max_turns = max_turns
        self.compress_threshold = compress_threshold
        self.keep_recent = keep_recent

    def system(self, tool_schemas: List[Dict[str, Any]]) -> str:
        tools_json = json.dumps(tool_schemas, ensure_ascii=False, indent=2)
        return _SYSTEM_TEMPLATE.format(tools_json=tools_json)

    def build(self, session, tool_schemas: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        history = list(session.history)
        truncated = False
        if self._estimate_chars(history) > self.compress_threshold:
            history = history[-self.keep_recent:]
            truncated = True

        system = self.system(tool_schemas)
        if truncated:
            system += "\n\n（注意：更早的对话历史因长度限制已被省略，请基于最近上下文继续。）"

        messages: List[Dict[str, str]] = [{"role": "system", "content": system}]
        for msg in history:
            messages.append(self._to_llm(msg))
        return messages

    @staticmethod
    def _to_llm(msg: Dict[str, str]) -> Dict[str, str]:
        # 内部 role=“tool” 转成 user 角色消息，保证 OpenAI 兼容接口可读
        if msg.get("role") == "tool":
            return {"role": "user", "content": f"[工具执行结果]\n{msg['content']}"}
        return {"role": msg["role"], "content": msg["content"]}

    @staticmethod
    def _estimate_chars(history: List[Dict[str, str]]) -> int:
        return sum(len(m.get("content", "")) for m in history)
