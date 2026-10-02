"""Mini Agent Runtime 命令行演示入口。

用法：
    python main.py --offline      # 离线规则演示，不调用真实 LLM
    python main.py                # 使用 OpenAI（需设置 OPENAI_API_KEY）
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

from agent.llm import FakeLLM, OpenAILLM
from agent.runtime import AgentRuntime
from tools.calculator import CalculatorTool
from tools.registry import ToolRegistry
from tools.search import SearchTool
from tools.todo import TodoTool


def build_tools() -> ToolRegistry:
    """注册三个内置工具。"""
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(SearchTool())
    registry.register(TodoTool())
    return registry


def _tool_result_answer(last: dict[str, Any]) -> str:
    """工具结果到达后，离线 LLM 据此生成最终回答。"""
    name = last.get("name")
    try:
        data = json.loads(last.get("content", ""))
    except json.JSONDecodeError:
        data = {}
    if name == "search":
        return json.dumps(
            {"type": "answer", "content": data.get("result", "搜索完成")},
            ensure_ascii=False,
        )
    if name == "calculator":
        return json.dumps(
            {"type": "answer", "content": f"计算结果为 {data.get('result')}"},
            ensure_ascii=False,
        )
    if name == "todo":
        return json.dumps(
            {"type": "answer", "content": data.get("result", "待办已处理")},
            ensure_ascii=False,
        )
    return json.dumps({"type": "answer", "content": "已完成。"}, ensure_ascii=False)


def offline_handler(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
) -> str:
    """离线演示用的简单规则 LLM：展示 Agent Loop 而不依赖真实 API。"""
    last = messages[-1]
    if last.get("role") == "tool":
        return _tool_result_answer(last)

    content = last.get("content", "")

    if re.search(r"计算|算一下|等于", content) or re.search(
        r"\d+\s*[+\-*/%]\s*\d+", content
    ):
        expr = re.search(r"[\d\s()+\-*/%.]+", content)
        expression = expr.group(0).strip() if expr else content
        return json.dumps(
            {
                "type": "tool_call",
                "tool": "calculator",
                "arguments": {"expression": expression},
            },
            ensure_ascii=False,
        )

    if "天气" in content:
        return json.dumps(
            {"type": "tool_call", "tool": "search", "arguments": {"query": content}},
            ensure_ascii=False,
        )

    if re.search(r"待办|记住|记下来|添加任务", content):
        return json.dumps(
            {
                "type": "tool_call",
                "tool": "todo",
                "arguments": {"action": "add", "task": content},
            },
            ensure_ascii=False,
        )

    if re.search(r"查看.*待办|待办列表", content):
        return json.dumps(
            {"type": "tool_call", "tool": "todo", "arguments": {"action": "list"}},
            ensure_ascii=False,
        )

    return json.dumps(
        {"type": "answer", "content": "你好，我是 Mini Agent。我可以计算、模拟搜索和管理待办。"},
        ensure_ascii=False,
    )


def build_runtime(offline: bool, model: str) -> AgentRuntime:
    llm = FakeLLM(handler=offline_handler) if offline else OpenAILLM(model=model)
    return AgentRuntime(llm=llm, tools=build_tools())


def main() -> None:
    parser = argparse.ArgumentParser(description="Mini Agent Runtime")
    parser.add_argument(
        "--offline", action="store_true", help="不调用真实 LLM，使用内置规则演示"
    )
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI 模型名")
    parser.add_argument("--session", default=None, help="指定 session id")
    args = parser.parse_args()

    runtime = build_runtime(args.offline, args.model)
    print("Mini Agent Runtime 已启动（输入 exit 退出）")
    while True:
        try:
            user_input = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if user_input.lower() in {"exit", "quit", "q"}:
            break
        if not user_input:
            continue
        answer = runtime.run(user_input, session_id=args.session)
        print(f"Agent> {answer}")


if __name__ == "__main__":
    main()
