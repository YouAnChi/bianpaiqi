# YinQing Agent Orchestrator (引擎 Agent 编排器)

## 📖 简介

**YinQing Agent** 是一个企业级的通用智能 Agent 编排器，旨在将复杂的自然语言任务转化为可执行的多 Agent 协作工作流。

它扮演着"项目经理"的角色，利用 LLM (Gemini) 的强大推理能力将模糊的用户指令拆解为严谨的**有向无环图 (DAG)** 任务链。随后，它通过 **MCP (Model Context Protocol)** 协议在开放的 Agent 市场中动态寻找最合适的执行者，并利用内置的并行调度引擎，高效地指挥这些 Agent 协同工作，最终完成目标。

## ✨ 核心特性

1.  **🧠 智能任务拆解 (DAG Generation)**: 
    *   集成 Google Gemini 模型，将自然语言指令解析为结构化的 `ExecutionPlan`。
    *   自动识别任务间的依赖关系，构建 DAG 图，确保执行顺序逻辑正确。
    *   具备循环依赖检测与自动修正能力。

2.  **🔍 动态能力匹配 (MCP Integration)**: 
    *   深度集成 **MCP (Model Context Protocol)**，实现 Agent 的动态发现。
    *   不硬编码 Agent 工具，而是根据步骤描述实时去 MCP Server 搜索最佳匹配。
    *   支持模糊语义匹配，根据任务描述（如"写一段代码"）自动匹配具备相应技能的 Agent（如 Coder Agent）。
    *   内置内存级缓存 (TTL 10分钟)，在保证灵活性的同时优化匹配延迟。

3.  **⚡️ 高效并行执行引擎 (Parallel Execution)**: 
    *   基于拓扑排序算法维护任务就绪队列。
    *   自动识别无依赖的任务步骤，使用 `asyncio` 实现**真正的并行执行**，最大化缩短任务总耗时。
    *   支持断点续传（基于 Trace ID 恢复上下文）。
    *   **结果自动归档**：执行完毕后，自动将所有步骤的产出汇总保存为 Markdown 文件，方便查阅。

4.  **🎨 可视化日志系统 (Rich Logging)**: 
    *   **全新升级**：基于 `rich` 库构建的终端日志系统。
    *   实时以高亮、结构化的方式展示任务拆解、Agent 匹配、并行执行流和调用结果。
    *   让复杂的后台调度逻辑对用户透明、可视。

5.  **🤝 稳健的 A2A 通信**: 
    *   基于 **A2A (Agent-to-Agent)** 协议标准进行 Agent 间交互。
    *   **高兼容性设计**：支持多种 Agent URL 发现策略（Config, Direct Attribute, Interaction Endpoints），并能自适应不同 Agent 的响应格式（严格 A2A JSON 或松散文本）。
    *   内置重试机制 (Retry Policy)、错误处理和响应清洗管道。

## 🏗 系统架构设计

本系统采用分层架构设计，各模块职责清晰，松耦合。

```mermaid
graph TD
    User[用户指令] --> Parser[Parser Layer (大脑)]
    Parser -->|生成 DAG| Plan[ExecutionPlan]
    Plan --> Matcher[Matcher Layer (猎头)]
    Matcher -->|查询| MCPServer[MCP Server (人才市场)]
    MCPServer -->|返回 AgentCard| Matcher
    Matcher -->|补全 Agent 信息| PlanWithAgents[Plan (已分配 Agent)]
    PlanWithAgents --> Workflow[Workflow Engine (项目经理)]
    
    subgraph "并行执行循环"
        Workflow -->|拓扑排序| ReadyQueue[就绪队列]
        ReadyQueue -->|分发| Executor[Executor Layer (工头)]
        Executor -->|HTTP POST| Agent1[Coder Agent]
        Executor -->|HTTP POST| Agent2[Writer Agent]
        Executor -->|HTTP POST| Agent3[Researcher Agent]
    end
    
    Agent1 -->|结果| Context[全局上下文]
    Agent2 -->|结果| Context
    Agent3 -->|结果| Context
    Context -->|依赖注入| Executor
    Workflow -->|最终汇总| OutputFile[Markdown 报告]
```

### 核心模块详解

#### 1. Task Parser Layer (`src/yinqing/core/parser.py`)
- **角色**: 系统大脑。
- **职责**: 将自然语言转化为结构化执行计划。
- **技术**: 
    - 使用 `LangChain` + `Gemini-2.0-Flash` 进行推理。
    - 输出严格符合 Pydantic 模型的 JSON 数据。
    - 自动生成 `TaskStep` 对象，包含 `step_id`, `description`, `dependencies` 等关键字段。

#### 2. Capability Matcher Layer (`src/yinqing/core/matcher.py`)
- **角色**: 资源调度/猎头。
- **职责**: 为每个任务步骤找到最合适的执行者。
- **技术**:
    - 通过 MCP Client 连接 `mcp-server`。
    - 使用语义搜索 (`find_agent` tool) 匹配 Agent。
    - **智能容错**：自动处理 AgentCard 字段缺失（如缺少 ID）的情况，确保流程不中断。
    - **缓存机制**: 使用 LRU 策略缓存 AgentCard，减少网络开销。

#### 3. Workflow Engine (`src/yinqing/core/workflow.py`)
- **角色**: 项目经理/调度器。
- **职责**: 管理任务全生命周期，处理依赖与并行。
- **算法**:
    - **DAG 初始化**: 计算所有节点的入度 (In-Degree) 和后继节点 (Successors)。
    - **拓扑排序**: 维护一个 `Ready Queue`，仅包含入度为 0 的节点。
    - **并行调度**: 每一轮循环中，从 Queue 取出所有节点，使用 `asyncio.gather` 并发执行。
    - **状态更新**: 节点完成后，递减其后继节点的入度；入度归零则加入 Queue。
- **输出**: 自动在 `output/` 目录下生成包含 Trace ID 的结果文档。

#### 4. Task Executor Layer (`src/yinqing/core/executor.py`)
- **角色**: 执行工头。
- **职责**: 负责与具体 Agent 的底层通信。
- **技术**:
    - **自适应通信**: 自动探测 Agent 的 HTTP URL 位置（支持多种数据结构）。
    - **协议封装**: 将任务描述和上下文封装为 A2A 标准 JSON (`{"task_description": "...", "context": {...}}`)。
    - **宽容解析**: 使用原生 `httpx` 发送请求，手动解析响应，绕过 `a2a` 库过于严格的 Pydantic 校验，大幅提高系统兼容性。
    - **重试机制**: 对网络抖动或临时故障进行自动重试。

## 📂 项目目录结构

```text
YinQing_Agent/
├── src/
│   └── yinqing/
│       ├── core/               # 核心引擎层
│       │   ├── parser.py       # [Parser] 任务拆解
│       │   ├── matcher.py      # [Matcher] 能力匹配
│       │   ├── executor.py     # [Executor] 任务执行
│       │   ├── workflow.py     # [Workflow] 流程编排与状态管理
│       │   ├── mcp_client.py   # [MCP] MCP 客户端封装
│       │   └── types.py        # [Types] Pydantic 数据模型
│       ├── utils/              # 工具层
│       │   ├── logger.py       # [Log] Rich 日志配置
│       │   ├── config.py       # [Config] 环境变量读取
│       │   └── common.py       # [Common] 通用常量与函数
│       └── main.py             # CLI 入口
├── real_ecosystem/             # 真实 Agent 生态 (模拟生产环境)
│   ├── agents/                 # 具体 Agent 实现 (FastAPI/Starlette)
│   │   ├── coder.py
│   │   ├── writer.py
│   │   └── ...
│   ├── cards/                  # Agent 名片 (JSON 定义)
│   └── mcp_server/             # MCP Server 实现
├── output/                     # 自动生成的任务结果文件
├── run_local.sh                # 一键启动脚本
└── README.md                   # 项目文档
```

## 🚀 快速开始

### 1. 环境准备

确保安装 Python 3.10+ 和 `uv` (可选，但推荐)。

```bash
# 安装依赖
pip install -e .

# 配置环境变量 (必须)
# 在项目根目录创建 .env 文件或直接 export
export GOOGLE_API_KEY="your-google-api-key"
```

### 2. 启动系统

本项目提供了一键启动脚本，会自动拉起 MCP Server、所有 Agent 实例以及 CLI 交互界面。

```bash
# 在终端中运行
./run_local.sh
```

### 3. 使用示例

进入交互模式后，你可以输入任意复杂指令。

**场景一：并行任务**
> "帮我分析 Python、Java 和 Go 三种编程语言的优缺点，并最后写一份对比总结报告"
*   **观察**: 系统会自动拆解为 3 个并行的分析任务，同时调度 Agent 执行，最后汇总结果。

**场景二：长链依赖**
> "先搜索一下目前最流行的 3 个 Python Web 框架，然后分别写一个简单的 'Hello World' 示例代码，最后把这些代码翻译成中文注释"
*   **观察**: 系统会严格按照 搜索 -> 编码 -> 翻译 的顺序执行，确保上下文正确传递。

### 4. 查看结果

任务执行完毕后，结果会自动保存。
```text
📄 结果已保存至: /path/to/YinQing_Agent/output/任务名_TraceID.md
```

## 🔌 接口协议说明

### Agent A2A 协议
为了保证编排器与 Agent 之间的通信顺畅，本项目中的 Agent 遵循以下协议规范：

1.  **输入格式**: Agent 接收标准 A2A JSON 格式的消息：
    ```json
    {
      "id": "uuid",
      "method": "sendMessage",
      "params": {
        "message": {
            "role": "user",
            "parts": [{
                "text": "{\"task_description\": \"...\", \"context\": {...}}"
            }]
        }
      }
    }
    ```
    Agent 内部会自动解析 `text` 字段中的 JSON 字符串，提取任务描述和上下文信息。

2.  **输出格式**: Agent 需返回包含结果文本的 JSON，结构可以是标准的 A2A Response，也可以是简化的 `{"result": {"message": ...}}` 甚至 `{"text": "..."}`，编排器均能自适应解析。

3.  **MCP 发现机制**:
    MCP Server 在搜索 Agent 时，不仅匹配名称和描述，还会深度搜索 `skills` 和 `capabilities`，确保基于能力的模糊查询能精准定位到合适的 Agent。
