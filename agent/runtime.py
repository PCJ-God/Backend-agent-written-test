"""Agent Runtime：主循环（自行实现，不依赖任何 Agent 框架）。"""

import json
from typing import List, Optional

from .context_manager import ContextManager
from .llm_client import LLMClient
from .logger import Trace
from .middleware import Middleware
from .output_parser import OutputParser
from .session_manager import Session, SessionManager
from .tool_registry import ToolRegistry

MAX_CONSECUTIVE_FAILURES = 3


class AgentRuntime:
    def __init__(
        self,
        llm: LLMClient,
        registry: Optional[ToolRegistry] = None,
        parser: Optional[OutputParser] = None,
        context: Optional[ContextManager] = None,
        sessions: Optional[SessionManager] = None,
        middlewares: Optional[List[Middleware]] = None,
        max_turns: int = 10,
        trace: Optional[Trace] = None,
    ) -> None:
        self.llm = llm
        self.registry = registry or ToolRegistry()
        self.parser = parser or OutputParser()
        self.context = context or ContextManager(max_turns=max_turns)
        self.sessions = sessions or SessionManager()
        self.middlewares = middlewares or []
        self.max_turns = max_turns
        self.trace = trace or Trace()

    def run(self, user_input: str, user_id: str = "default", session_id: Optional[str] = None) -> str:
        """处理一次用户输入，返回最终答案。

        Step one 接收输入 → Step two 决策 → Step three 调工具 → Step four 继续或返回。
        """
        session = self.sessions.get_or_create(user_id, session_id)
        session.append("user", user_input)

        parse_retry_used = False
        consecutive_failures = 0

        for turn in range(1, self.max_turns + 1):
            for mw in self.middlewares:
                mw.before_step(session, turn)

            messages = self.context.build(session, self.registry.schemas())
            for mw in self.middlewares:
                updated = mw.before_model(session, messages)
                if updated is not None:
                    messages = updated

            self.trace.log(turn=turn, event="llm_call")

            try:
                raw = self.llm.chat(messages)
            except Exception as exc:
                return self._finish(session, f"抱歉，模型调用失败：{exc}")

            parsed = self.parser.parse(raw, registry=self.registry)
            self.trace.log(turn=turn, event="parsed", kind=parsed.kind, thinking=parsed.thinking[:200])

            if parsed.malformed and not parse_retry_used:
                parse_retry_used = True
                session.append("user", "（系统提示）请严格按给定 JSON 格式输出，不要输出多余文字。")
                self.trace.log(turn=turn, event="parse_retry")
                continue

            if parsed.kind == "reply":
                return self._finish(session, parsed.answer)

            # tool_call 分支
            result = self.registry.execute(parsed.tool_name, parsed.tool_args, session=session)
            for mw in self.middlewares:
                mw.after_tool_use(session, parsed.tool_name, parsed.tool_args, result)
            self.trace.log(turn=turn, event="tool", tool=parsed.tool_name, args=parsed.tool_args, result=result)
            session.append("tool", json.dumps(result, ensure_ascii=False))

            if result.get("ok"):
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    return self._force_answer(session)

        return self._finish(session, "已达最大轮次，本轮结束。")

    def _force_answer(self, session: Session) -> str:
        """工具连续失败时，强制让 LLM 基于已有信息直接回答。"""
        self.trace.log(event="force_answer")
        messages = self.context.build(session, self.registry.schemas())
        messages.append({"role": "user", "content": "工具连续调用失败，请直接基于已有信息给出最终答案，不要再调用工具。"})
        try:
            raw = self.llm.chat(messages)
            parsed = self.parser.parse(raw, registry=self.registry)
            if parsed.kind == "reply":
                return self._finish(session, parsed.answer)
        except Exception:
            pass
        return self._finish(session, "抱歉，工具连续调用失败，暂时无法完成该请求。")

    def _finish(self, session: Session, answer: str) -> str:
        session.append("assistant", answer)
        self.trace.log(event="finish", answer=answer[:200])
        return answer
