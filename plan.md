# 项目实现计划：从零实现一个最小可用 Agent

> 说明：本文档为开发前设计稿，仅供 review。评审通过后再动手写代码。
> 依据：仓库根目录 `README.md`（`README2.md` 是另一份架构设计题，与本任务无关）。

## 0. 项目目标

不依赖任何现有 Agent 框架（langgraph / openhands / openclaw / PI），从零实现一个最小可用的 Agent Runtime，具备：

1. 基本的 Agent 循环：接收输入 → 决策（直接回复 / 调用工具）→ 执行工具 → 依据结果继续循环或返回答案。
2. 工具注册机制 + 至少三个工具（calculator、search 可 mock、todo 等自定义工具），LLM 基于工具 Schema 自主决策调用。
3. LLM 输出解析逻辑：从模型输出中提取「思考过程 / 工具调用 / 最终答案」。
4. 多窗口 session 隔离：同一用户的两个窗口彼此独立、可随时续聊。
5. context 有效管理：最大轮次限制、记住历史、支持纯对话与带工具的追问、基础压缩。
6. 基本异常处理与工具调用 trace / 执行日志。
7. 使用真实 LLM API，并配测试用例。

### 0.1 关于「从零实现」的开发策略（两阶段）

README 要求 1 强调「不能依赖现有 Agent 框架完成主流程，核心 Agent Runtime 需要自行实现」。经确认，采用如下两阶段策略：

1. **第一阶段（原型）**：使用 AgentScope（阿里云开源的 Agent 框架，Python 版仓库 github.com/agentscope-ai/agentscope，Apache-2.0 协议）作为「上层建筑」快速搭出可用版本，验证主循环、工具调用、session、context 等设计是否成立；其 Agent / Tool / Memory / ReActAgent 等抽象可直接对应本项目的各模块。
2. **第二阶段（最终版）**：把原型所依赖的框架底层代码内联（vendor）进本项目文件，删除对框架包的一切运行时依赖，使核心 Agent Runtime 落在我们自己的项目文件内、可自行维护。

**内联边界（已确认）**：只内联「主循环执行引擎」这一个点；工具、session、context、解析、LLM 封装、日志 trace、测试等其余模块全部自研，不内联框架代码。

最终版的验收标准（不满足则不算完成）：

- 运行时代码路径中不存在任何 Agent 框架的 import（如 `import agentscope`）。
- 依赖清单（requirements / pyproject）不再包含任何 Agent 框架包。
- 仅「主循环执行引擎」从框架源码内联而来；其余模块（工具 / session / context / 解析 / LLM 封装 / 日志 / 测试）均为自研代码。
- 内联的框架源码需保留其 License 与出处说明（AgentScope 为 Apache-2.0），避免版权问题。
- 全部测试在移除框架依赖后仍然通过。

---

## 1. 项目实现逻辑

### 1.1 总体架构

```
┌─────────────┐   1.用户输入    ┌──────────────────┐
│   入口/API   │ ──────────────▶ │  Agent Runtime   │
│ (CLI / HTTP)│                 │    (主循环)       │
└─────────────┘                 └───┬──────┬───────┘
                                    │      │
                         2.组装context│      │5.最终答案
                                    ▼      │
                            ┌──────────────┐     ┌──────────────┐
                            │ LLM Client   │◀───▶│ 真实 LLM API │
                            │ (真实 API)   │     └──────────────┘
                            └──────┬───────┘
                         3.原始输出  │
                                   ▼
                            ┌──────────────┐
                            │ OutputParser │
                            └──┬───────┬───┘
                   思考/答案    │       │ 工具调用
                               ▼       ▼
                     ┌────────────┐   ┌──────────────────┐
                     │ 直接回复    │   │  Tool Registry    │
                     └────────────┘   │  (名称/描述/Schema)│
                                      └────────┬─────────┘
                                               │4.执行
                                               ▼
                                    ┌────────────────────┐
                                    │ calculator/search/ │
                                    │ todo（降级处理）    │
                                    └────────────────────┘
                                               │ 结果回填context
                                               └────▶ 回到主循环
```

### 1.2 核心技术栈（建议，待确认）

- 语言：Python 3.10+
- LLM 接入：`openai` SDK 或裸 `httpx` 调 OpenAI 兼容接口（读环境变量配置 key/base_url/model）
- 测试：`pytest`
- 原型阶段：可用 AgentScope 快速搭建（仅开发期脚手架，见 0.1）
- 最终版：移除框架依赖，运行时仅保留 `openai` / `httpx` 等非 Agent 框架的普通库

### 1.3 Agent 主循环（核心 Runtime，自行实现）

单次用户消息处理的循环，伪代码：

```
def run(session, user_input, max_turns=10):
    session.append(user: user_input)

    for turn in range(max_turns):            # 最大轮次限制
        messages = context_manager.build(session)   # 组装 system + 历史 + 工具schema
        raw      = llm_client.chat(messages)        # 真实 LLM 调用

        parsed = output_parser.parse(raw)           # 提取 思考/工具调用/答案

        if parsed.kind == "answer":
            session.append(assistant: parsed.answer)
            return parsed.answer                    # Step four：返回结果给用户

        if parsed.kind == "tool_call":
            result = tool_registry.execute(parsed)  # Step three：调用工具（含降级）
            session.append(tool_result: result)     # 结果回填，进入下一轮
            continue                                # Step four：继续 loop

    return "已达最大轮次，结束本轮。"                # 兜底
```

四个步骤与 README 一一对应：

- Step one 接收用户输入 → 追加进 session
- Step two 判断直接回复还是调用工具 → 交给 LLM + OutputParser 决策
- Step three 调用工具 → Tool Registry 执行
- Step four 依据工具结果决定继续 loop 还是返回 → 答案直接返回，工具结果回填后继续循环

### 1.4 LLM 输出解析（OutputParser）

采用「提示词约束 + JSON 结构化输出」方案，不依赖框架，自行实现解析：

- 系统提示词中注入工具清单（名称、描述、JSON Schema），要求模型输出如下 JSON：

```json
{
  "thinking": "内部思考过程",
  "action": "reply | tool_call",
  "tool_name": "calculator",
  "tool_args": { "expression": "1+2*3" },
  "final_answer": "给用户的自然语言答案"
}
```

解析逻辑（重点，需鲁棒）：

1. 纯文本回复：模型没输出 JSON → 直接当作 `action=reply`，原文返回。
2. JSON 输出：优先 `json.loads`；失败则用「首个 `{` 到最后一个 `}`」截取后重试。
3. 字段校验：`action` 非法 / `tool_name` 未注册 / `tool_args` 非对象 → 视为解析失败。
4. 解析失败降级：携带「请按给定 JSON 格式输出」的提示重试一次；再失败则返回友好的兜底话术，不抛异常中断。

### 1.5 Session 管理

- `SessionManager` 维护 `session_id -> Session` 映射（进程内 dict，可选 JSON 文件持久化）。
- `Session` 结构：`session_id`、`user_id`、`history`（消息列表）、`turn` 计数、工具私有状态（如 todo 列表）。
- 窗口隔离：窗口 1、窗口 2 各生成独立 `session_id`（同一 `user_id` 下多个 session），各自的 history 与 todo 状态互不可见。
- 续聊：按 `session_id` 取回对应 Session，在其 `history` 上继续追加即可。

### 1.6 Context 管理（含 memory 召回时机与放置方式）

组装进 context 的内容（system prompt + 消息列表）：

- system prompt：角色设定、工具 Schema、JSON 输出格式要求、当前轮次上限提示。
- 对话历史：`user` 消息、`assistant` 最终答案、`tool` 执行结果（思考过程 `thinking` 默认不进上下文以省 token，仅记录到日志）。
- 工具私有状态：如 todo 当前列表，作为一条 `tool`/`system` 消息在需要时注入。

管理与压缩策略：

1. 最大轮次限制：单次用户输入最多循环 `max_turns`（默认 10），防死循环。
2. 历史记忆：Session 持久保存完整 history，追问（纯对话追问、带工具的追问）都因历史在而自然成立。
3. 基础压缩：用 token 估算（字符长度近似）；超过阈值时，将最早一段历史交给 LLM 摘要成一条 `system` 摘要消息，保留最近 N 条原文。复杂压缩不做。
4. memory 召回时机：进入新一轮循环前按需召回（完整历史 + 摘要）；放置方式：摘要作为 system 层消息，最近原文作为普通消息，工具结果紧跟其调用之后，保证模型能对齐「哪次调用 → 哪个结果」。

### 1.7 异常处理与日志 trace

- LLM 网络/超时：指数退避重试（如 2 次），最终失败返回友好提示。
- 工具异常：捕获后格式化为错误结果回填给 LLM，不中断主循环（见第 3 节降级）。
- 解析异常：见 1.4 的降级路径。
- 全程日志：每轮记录 `turn`、`thinking`、`tool_name/tool_args`、`tool_result`、耗时，形成可回放的 trace。

---

## 2. 项目要求的硬性模块（必做模块）

以下为 README 明确要求、不可省略的核心模块：

| 模块 | 职责 | 对应 README 要求 |
|------|------|------------------|
| `agent_runtime` | 主循环四步逻辑；最终版仅「主循环执行引擎」内联框架源码，其余自研 | 要求1、要求2-Loop |
| `llm_client` | 封装真实 LLM API 调用（key/base_url/model 可配） | 提交内容：真实 LLM API |
| `output_parser` | 解析模型输出：思考 / 工具调用 / 最终答案，含降级 | 要求2-解析逻辑 |
| `tool_registry` | 工具注册机制：名称 + 描述 + 参数 Schema，按 Schema 检索与执行 | 要求2-工具注册机制 |
| `tools/calculator` | 数学计算工具 | 要求2-工具 |
| `tools/search` | 搜索工具（可 mock） | 要求2-工具 |
| `tools/todo` | 待办系统：todo_write 工具 + 反应式提醒 middleware（共享状态） | 要求2-工具 |
| `session_manager` | 多窗口 session 隔离与续聊 | 要求2-session 管理 |
| `context_manager` | context 组装、最大轮次、历史记忆、基础压缩 | 要求2-context 管理 |
| `logger/tracer` | 工具调用 trace 与执行日志、异常记录 | 要求2-额外要求 |
| `tests/` | 覆盖上述功能的测试用例 | 要求3-测试用例 |

> 注 1：README 原文「硬编码模块」此处理解为「项目明确要求、必须实现的硬性模块」。第三个工具 README 允许在 `read_docs / todo / weather` 中自定义，本计划选择 `todo`（与 session 示例「记待办」直接契合），`weather`/`read_docs` 可作为替换实现，接口保持一致。
>
> 注 2：上表为「最终版」的模块形态。原型阶段这些职责可借助 AgentScope 实现；最终版仅将「主循环执行引擎」从框架源码按需内联进本项目，其余模块（工具 / session / context / 解析 / LLM 封装 / 日志 / 测试）全部自研，不依赖框架包。

---

## 3. 工具的输入参数、输出参数、调用失败的降级处理

### 3.0 通用降级策略（所有工具共用）

1. 工具执行抛异常 → 捕获后返回 `{"ok": false, "error": "<异常信息>"}` 回填给 LLM，主循环不中断。
2. 参数缺字段 / 类型错误 → 返回错误对象，让 LLM 依据错误信息自行修正后重试。
3. 同一工具连续失败达到上限（如 3 次）→ 强制让 LLM 给出最终答案，避免死循环。
4. 错误信息均以「机器可读 + 可被 LLM 理解」的文本返回，作为上下文的一部分。

### 3.1 calculator

- 描述：安全计算数学表达式。
- 输入参数（Schema）：
  - `expression`：string，必填，数学表达式，如 `"1+2*3"`。
- 输出参数：
  - 成功：`{"ok": true, "expression": "...", "result": <number>}`
  - 失败：`{"ok": false, "error": "..."}`
- 降级处理：
  - 表达式非法 / 除零 → 返回带原因的错误对象；由 LLM 改写表达式重试。
  - 安全：**不用 `eval`**，采用白名单 AST 解析（仅数字、四则运算、括号等），防止注入。

### 3.2 search（可 mock）

- 描述：联网/检索信息（演示用可返回 mock 数据）。
- 输入参数（Schema）：
  - `query`：string，必填，搜索关键词。
  - `top_k`：int，选填，默认 3，返回条数。
- 输出参数：
  - 成功：`{"ok": true, "results": [{"title": "...", "snippet": "...", "url": "..."}]}`
  - 失败：`{"ok": false, "error": "..."}`
- 降级处理：
  - mock 模式：对关键词返回固定的几条本地结果，永远成功。
  - 真实检索失败/超时：返回 `{"ok": false, "error": "搜索暂不可用"}`，让 LLM 转告用户「搜索不可用」并基于已有信息回答。

### 3.3 todo（todo_write 工具 + 反应式提醒 middleware）

todo 采用「工具 + middleware」配对设计，由 `create_todo_system()` 工厂一次产出，两者共享同一份闭包状态（按 session_id 隔离）：工具是写入端，middleware 是观察端，负责在 LLM「写完就忘」时提醒。

- 工具名：`todo_write`。
- 输入参数（Schema）：
  - `name`：string，必填，计划短标签。
  - `todos`：array，必填，每项含 `id`、`content`、`status`（pending / in_progress / completed）。
  - `merge`：boolean，必填，true 按 id 增量合并，false 整表替换（首次建表用 false，之后用 true 省 token）。
- 输出参数：
  - 成功：`{"ok": true, "action": "merge|replace", "todos": [...], "summary": "Plan ... updated, x/y completed.\n1. [x] ..."}`
  - 失败：`{"ok": false, "error": "..."}`
- 降级处理：
  - 非法 `status` / 缺字段 / `merge` 非布尔 → 返回错误对象，LLM 修正后重试。
  - 同一 step 第二次调用 `todo_write` → 返回「只有第一次生效」，不改状态（并发写防护）。
- middleware 钩子：
  - `before_step`：清零并发写计数器。
  - `after_tool_use`：`todo_write` 后把「距上次写入」归零。
  - `before_model`：距上次写入 ≥5 步且距上次提醒 ≥5 步时，注入软提醒（附当前清单）。

> `weather` / `read_docs` 作为第三个工具的可替换实现：接口与工具注册同构，新增时仅需实现工具函数并注册，主流程零改动。

---

## 4. 项目的测试案例

### 4.1 单元测试

| 编号 | 用例 | 预期 |
|------|------|------|
| T1 | `output_parser` 解析「纯文本回复」 | 识别为 `reply`，原文返回 |
| T2 | `output_parser` 解析「合法 JSON 工具调用」 | 提取 `tool_name`/`tool_args`/`thinking` |
| T3 | `output_parser` 解析「带噪声的 JSON（前后有杂文本）」 | 截取后解析成功 |
| T4 | `output_parser` 解析「非法 JSON」 | 触发降级重试/兜底，不抛异常 |
| T5 | `calculator` 合法表达式 `"1+2*3"` | 返回 `7` |
| T6 | `calculator` 非法表达式 / 除零 | 返回 `ok:false` 错误对象，不崩溃 |
| T7 | `search` mock 查询 | 返回固定结果列表 |
| T8 | `todo_write` 首次建表（merge=false）+ 增量更新（merge=true） | 列表状态正确变更 |
| T9 | `todo_write` 非法 status / 缺 merge / 同 step 并发写 | 返回错误对象，状态无副作用 |

### 4.2 集成测试（用脚本化假 LLM 驱动 Runtime）

| 编号 | 用例 | 预期 |
|------|------|------|
| T10 | 假 LLM 直接返回答案 | 主循环 Step four 直接返回结果给用户 |
| T11 | 假 LLM 先返回 `calculator` 工具调用，再返回答案 | 工具被调用，结果回填，循环两轮后返回 |
| T12 | 假 LLM 连续返回工具调用 | 最多执行 `max_turns` 后强制结束，不死循环 |
| T13 | 工具执行抛异常 | 主循环捕获、降级回填、继续运行并最终给出答案 |
| T14 | 同一工具连续失败 3 次 | 强制转为最终答案 |

### 4.3 Session 隔离测试

| 编号 | 用例 | 预期 |
|------|------|------|
| T15 | 窗口 1 记 todo A，窗口 2 记 todo B | 两 session 的 todo 互不可见 |
| T16 | 窗口 1 会话后新建对话，再回到窗口 1 续聊 | 能读到窗口 1 的历史与 todo |
| T17 | 同一用户两窗口并发交替对话 | history 不串扰 |

### 4.4 Context / 追问测试

| 编号 | 用例 | 预期 |
|------|------|------|
| T18 | 纯对话追问（上文提到信息，下文直接问） | 历史被携带，回答能引用上文 |
| T19 | 带工具的追问（上文记 todo，下文要求「再加一条」） | 工具状态 + 历史共同支撑追问 |
| T20 | 超长历史 | 触发基础压缩，压缩后仍能回答关键问题 |
| T21 | 单次输入触发超过最大轮次 | 触发轮次上限，友好结束 |

### 4.5 真实 LLM 冒烟测试（需 API key，标记为可选/CI 可跳过）

| 编号 | 用例 | 预期 |
|------|------|------|
| T22 | 真实 API 走一遍「查天气并记待办」多工具链路 | 端到端跑通主循环 |
| T23 | 真实 API 追问链路 | 续聊上下文正确 |

> 测试分层原则：Runtime/循环/解析/降级全部可用假 LLM 与 mock 工具覆盖，不依赖网络；真实 API 仅做冒烟，便于 CI 稳定。

---

## 5. 建议目录结构（供 review 参考）

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
tests/
  test_output_parser.py
  test_tools.py
  test_runtime.py
  test_session.py
  test_context.py
  test_llm_smoke.py   # 可选
README.md            # 运行方式、系统设计、memory 召回时机与放置方式说明
plan.md              # 本文档
```

---

## 6. 待确认问题（review 时一并看）

1. 技术栈是否用 Python 3.10+ 与 `pytest`？还是希望换 TypeScript？
2. 内联边界已确认：仅内联「主循环执行引擎」，其余全部自研。剩余待定：AgentScope 中「主循环执行引擎」具体对应哪些模块（如 ReActAgent 的循环逻辑），内联时以这些模块为准。
3. 第三个工具选 `todo` 是否符合预期？还是需要 `weather` / `read_docs`？
4. 入口形态：先用 CLI 跑通，还是需要一并提供 HTTP 接口？
5. 真实 LLM 的接入方式（OpenAI 兼容接口 / 具体模型名）是否已有约定？
