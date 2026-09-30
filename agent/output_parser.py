"""LLM 输出解析：提取 思考 / 工具调用 / 最终答案。"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Parsed:
    kind: str                                # "reply" | "tool_call"
    thinking: str = ""
    answer: str = ""
    tool_name: str = ""
    tool_args: Dict[str, Any] = field(default_factory=dict)
    malformed: bool = False                  # 疑似结构化输出但解析失败，需提示重试


class OutputParser:
    def parse(self, raw: str, registry=None) -> Parsed:
        text = (raw or "").strip()

        data = self._extract_json(text)
        if data is None:
            # 看起来想输出 JSON / 工具调用但没解析出来 → 标记后由 Runtime 提示重试
            malformed = ("{" in text and "}" in text) or "tool_call" in text
            return Parsed(kind="reply", answer=text or "（空回复）", malformed=malformed)

        thinking = str(data.get("thinking") or "")
        action = data.get("action")

        if action == "tool_call":
            name = str(data.get("tool_name") or "")
            args = data.get("tool_args")
            if not isinstance(args, dict):
                args = {}
            if not name:
                return Parsed(kind="reply", thinking=thinking,
                              answer=data.get("final_answer") or text, malformed=True)
            if registry is not None and not registry.has(name):
                # 工具未注册 → 降级为直接回复
                return Parsed(kind="reply", thinking=thinking, answer=data.get("final_answer") or text)
            return Parsed(kind="tool_call", thinking=thinking, tool_name=name, tool_args=args)

        # 其余情况一律视为最终答案
        answer = str(data.get("final_answer") or "") or text
        return Parsed(kind="reply", thinking=thinking, answer=answer)

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
        # 模型常在 JSON 前后夹带说明文字：截取首个 { 到最后一个 }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                obj = json.loads(text[start:end + 1])
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass
        return None
