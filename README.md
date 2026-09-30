# Vibe coding题目：从零实现一个最小可用 Agent

## 要求1：从零完成

- 不能依赖现有agent框架（langgraph/openhands/openclaw/PI）完成主流程，
- 允许使用任何 AI 工具辅助开发，但核心 Agent Runtime 需要自行实现。

## 要求2：实现基本循环

### Loop大致步骤

- Step one 接收用户输入
- Step two 判断是直接回复，还是调用工具
- Step three 调用工具
- Step four 根据工具结果判断是继续loop，还是返回结果给用户

### 工具相关

- 至少实现三个工具
  - calculator
  - search（可 mock）
  - read_docs / todo / weather（可自定义）

- 需实现工具注册机制（每个工具包含名称、描述、参数 Schema），LLM 基于 Schema 自主决策调用。需实现 LLM 输出的解析逻辑，提取思考过程、工具调用或最终答案。

### session管理

- 用户 A 开了窗口 1：让 Agent 查天气记待办
- 用户 A 开了窗口 2：让 Agent 写周报记待办
- 这两个窗口应该是独立的session，用户A可以随时接着窗口1/2和继续聊，彼此不会影响。

### context的有效管理

- 最大轮次限制
- 用户持续的对话，要能记住之前的状态。
- 能支持追问
  - 纯对话追问
  - 带着工具的追问
- 要如何实现？哪些信息要塞入context更合适？
  - 用户输入、工具执行结果、Agent 思考过程等，自行判断。
- context过长要有基础的压缩，复杂的压缩不用在这里实现。

### 额外要求

- 基本异常处理
- 工具调用trace或执行日志

## 要求3: 测试用例构建

- 构建测试用例，来测试以上功能

## 提交内容：

- 需要使用真实的LLM Api
- 代码链接（github即可）
- README（运行方式、系统设计、memory 的召回时机与放置方式说明）
- AI Prompt 与问题解决记录

---

## 运行方式

### 环境准备

- Python 3.10+
- 安装依赖（真实 LLM 调用所需）：`pip install openai`

### 配置 LLM

通过环境变量配置（OpenAI 兼容接口）：

| 环境变量 | 说明 |
|----------|------|
| `OPENAI_API_KEY` / `LLM_API_KEY` / `DEEPSEEK_API_KEY` / `API_KEY` | API Key（必填，按顺序取第一个非空） |
| `OPENAI_BASE_URL` / `LLM_BASE_URL` / `DEEPSEEK_BASE_URL` / `BASE_URL` | 接口地址（可选，不设则用 OpenAI 默认地址） |
| `LLM_MODEL` / `OPENAI_MODEL` / `DEEPSEEK_MODEL` / `MODEL` | 模型名（默认 `gpt-4o-mini`） |

Windows PowerShell 示例：

```powershell
# OpenAI 示例
$env:OPENAI_API_KEY = "sk-..."
$env:OPENAI_BASE_URL = "https://api.openai.com/v1"
$env:OPENAI_MODEL = "gpt-4o-mini"

# DeepSeek 示例
$env:DEEPSEEK_API_KEY = "sk-..."
$env:DEEPSEEK_BASE_URL = "https://api.deepseek.com"
$env:DEEPSEEK_MODEL = "deepseek-flash"
```

### 启动

```bash
python main.py
```

交互命令：

- 直接输入自然语言对话
- `new`：开启一个新会话（等价于新窗口，session 隔离）
- `exit` / `quit`：退出

### 运行测试

```bash
pip install pytest
python -m pytest tests/ -v
```

`tests/test_llm_smoke.py` 是真实 LLM 冒烟测试（可选），默认跳过；配置 API Key 且安装了 `openai` 后会自动执行。

### 目录结构

```
agent/
  runtime.py          # 主循环
  llm_client.py       # 真实 LLM API 封装
  output_parser.py    # 输出解析
  tool_registry.py    # 工具注册
  session_manager.py  # session 管理
  context_manager.py  # context 组装/压缩
  logger.py           # trace 与日志
  tools/
    calculator.py
    search.py
    todo.py
main.py               # 命令行入口
```

---

## 系统设计

### 总体架构

```
用户输入 → AgentRuntime 主循环
              │
              ├─ 组装 context（ContextManager）
              ├─ 调用 LLM（LLMClient，真实 API）
              ├─ 解析输出（OutputParser：思考 / 工具调用 / 答案）
              ├─ 调用工具（ToolRegistry：calculator / search / todo）
              └─ 结果回填 → 继续循环或返回答案
```

### 主循环四步

1. 接收用户输入，追加进当前 session。
2. 组装 context 交给 LLM，由其决策「直接回复」还是「调用工具」。
3. 调用工具（ToolRegistry 执行，失败时降级为错误对象回填）。
4. 依据工具结果决定继续循环，还是把最终答案返回给用户。

单次用户输入最多循环 `max_turns`（默认 10）轮，防止死循环；同一工具连续失败 3 次会强制转最终答案。

### 模块职责

| 模块 | 职责 |
|------|------|
| `runtime.py` | 主循环四步逻辑 |
| `llm_client.py` | OpenAI 兼容接口封装，带退避重试 |
| `output_parser.py` | 解析 LLM 输出：思考 / 工具调用 / 最终答案，含降级 |
| `tool_registry.py` | 工具注册：名称 + 描述 + 参数 Schema，按 Schema 检索与执行 |
| `tools/calculator.py` | 安全计算（AST 白名单，不用 eval） |
| `tools/search.py` | 搜索（mock） |
| `tools/todo.py` | 待办系统：todo_write 工具 + 反应式提醒 middleware（共享状态） |
| `session_manager.py` | 多窗口 session 隔离与续聊 |
| `context_manager.py` | context 组装、最大轮次、基础压缩 |
| `logger.py` | 执行日志与工具调用 trace |

### 工具的输入 / 输出 / 降级

- 通用约定：成功返回 `{"ok": true, ...}`，失败返回 `{"ok": false, "error": "..."}`；工具抛异常会被 ToolRegistry 捕获并转成错误对象回填，主循环不中断。
- `calculator`：输入 `expression`；输出 `result`；非法表达式 / 除零返回错误，由 LLM 改写后重试。
- `search`：输入 `query`、`top_k`；输出 `results`；mock 模式永远成功，真实检索失败返回「搜索暂不可用」。
- `todo_write`：输入 `name`、`todos`（id/content/status）、`merge`；输出完整清单 summary；非法 status / 缺字段返回错误，同 step 并发写仅第一次生效。

---

## memory 召回时机与放置方式说明

### 召回时机

在**每一次主循环迭代、调用 LLM 之前**，由 `ContextManager.build()` 按需召回：

1. 召回当前 session 的完整 `history`（user / assistant / tool 消息）。
2. 召回工具私有状态（如 todo 当前列表），该状态就存在 session 的 `tool_state` 里，随历史一起被读取。
3. 若历史超过压缩阈值（`compress_threshold`，默认 4000 字符），只保留最近 `keep_recent`（默认 8）条原文，更早的历史被截断，并在 system 提示中追加省略说明。

### 放置方式

组装后的 messages 顺序如下：

1. `system`：角色设定 + 工具 JSON Schema + 输出格式要求 + 规则 +（若发生截断）省略提示。
2. 历史消息按时间顺序排列：`user`、`assistant` 原文直接放入。
3. 工具执行结果以 `[工具执行结果]\n<json>` 的形式，紧跟在其对应的工具决策之后，保证模型能对齐「哪次调用 → 哪个结果」。
4. 思考过程 `thinking` **不放入 context**（节省 token），只写入 `Trace` 日志，供调试与回放。

### 为什么不塞入思考过程

`thinking` 只对本次决策有意义，放入历史会挤占后续轮次的 token 预算；把它留在 trace 日志里，既满足「可回放」的观测需求，又不污染上下文。
