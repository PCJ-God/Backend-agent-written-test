"""最小可用 Agent 的命令行入口。"""

from agent.context_manager import ContextManager
from agent.llm_client import LLMClient
from agent.output_parser import OutputParser
from agent.runtime import AgentRuntime
from agent.session_manager import SessionManager
from agent.tool_registry import ToolRegistry
from agent.tools.todo import create_todo_system


def main() -> None:
    sessions = SessionManager()
    registry = ToolRegistry()
    todo_tool, todo_middleware = create_todo_system()
    registry.register(todo_tool)

    runtime = AgentRuntime(
        llm=LLMClient(),
        registry=registry,
        parser=OutputParser(),
        context=ContextManager(),
        sessions=sessions,
        middlewares=[todo_middleware],
    )

    if not runtime.llm.api_key:
        print("警告：未检测到 OPENAI_API_KEY / LLM_API_KEY，对话将无法调用模型。")

    print("最小可用 Agent（输入 exit 退出，输入 new 开启新会话）")
    session = sessions.create("cli")

    while True:
        try:
            line = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.lower() in ("exit", "quit"):
            break
        if line.lower() == "new":
            session = sessions.create("cli")
            print("已开启新会话")
            continue
        answer = runtime.run(line, user_id="cli", session_id=session.session_id)
        print(f"Agent> {answer}")


if __name__ == "__main__":
    main()
