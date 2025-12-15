# YinQing Agent 项目架构详解

## 📋 目录

- [项目概述](#项目概述)
- [核心设计理念](#核心设计理念)
- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [核心模块详解](#核心模块详解)
- [数据流转](#数据流转)
- [目录结构](#目录结构)
- [关键算法](#关键算法)
- [扩展性设计](#扩展性设计)

---

## 项目概述

**YinQing Agent** 是一个企业级的通用智能 Agent 编排器，核心功能是将复杂的自然语言任务转化为可执行的多 Agent 协作工作流。

### 核心价值

1. **智能拆解**：利用 LLM 将模糊的用户指令转化为结构化的 DAG（有向无环图）任务链
2. **动态匹配**：通过 MCP 协议在 Agent 市场中动态发现和匹配最合适的执行者
3. **并行执行**：基于拓扑排序的并行调度引擎，最大化任务执行效率
4. **开放生态**：不硬编码 Agent，支持任意符合 A2A 协议的 Agent 接入

### 应用场景

- 复杂的多步骤研究任务（搜索 → 分析 → 总结 → 翻译）
- 并行数据处理（同时分析多个数据源）
- 跨领域协作任务（代码生成 + 文档编写 + 代码审查）
- 自动化工作流编排

---

## 核心设计理念

### 1. 分层架构

系统采用经典的分层设计，每层职责单一、松耦合：

```
┌─────────────────────────────────────┐
│   CLI Layer (用户交互层)             │
├─────────────────────────────────────┤
│   Workflow Engine (编排引擎层)       │
├─────────────────────────────────────┤
│   Parser | Matcher | Executor       │
│   (任务拆解 | 能力匹配 | 任务执行)    │
├─────────────────────────────────────┤
│   MCP Client | A2A Protocol         │
│   (协议层)                           │
├─────────────────────────────────────┤
│   Agent Ecosystem (Agent 生态)      │
└─────────────────────────────────────┘
```

### 2. DAG 驱动

- 所有任务被建模为 DAG，节点是任务步骤，边是依赖关系
- 支持循环依赖检测和自动修正
- 基于拓扑排序实现并行调度

### 3. 协议标准化

- **MCP (Model Context Protocol)**：用于 Agent 发现和能力查询
- **A2A (Agent-to-Agent)**：用于 Agent 间通信
- 高兼容性设计，支持多种响应格式


---

## 系统架构

### 整体架构图

```
┌──────────────┐
│  用户指令     │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│                    Workflow Engine                        │
│  (项目经理 - 负责全局调度和状态管理)                       │
└──────┬───────────────────────────────────────────────────┘
       │
       ├─────► Parser Layer (大脑)
       │       └─ 使用 Gemini LLM 将自然语言转为 ExecutionPlan
       │       └─ 生成 DAG 结构，识别依赖关系
       │
       ├─────► Matcher Layer (猎头)
       │       └─ 连接 MCP Server
       │       └─ 为每个步骤匹配最合适的 Agent
       │       └─ 内置缓存机制 (TTL 10分钟)
       │
       └─────► Executor Layer (工头)
               └─ 封装 A2A 协议通信
               └─ 处理重试和错误恢复
               └─ 自适应解析多种响应格式
                      │
                      ▼
       ┌──────────────────────────────────┐
       │      MCP Server (人才市场)        │
       │  - 维护 Agent 注册表              │
       │  - 提供语义搜索能力               │
       └──────────────┬───────────────────┘
                      │
                      ▼
       ┌──────────────────────────────────┐
       │      Agent Ecosystem              │
       │  ┌─────────┬─────────┬─────────┐ │
       │  │ Coder   │ Writer  │Research │ │
       │  │ Agent   │ Agent   │ Agent   │ │
       │  └─────────┴─────────┴─────────┘ │
       │  ┌─────────┬─────────┬─────────┐ │
       │  │Reviewer │Analyst  │Translator│ │
       │  │ Agent   │ Agent   │ Agent   │ │
       │  └─────────┴─────────┴─────────┘ │
       └──────────────────────────────────┘
```

### 执行流程

```
1. 用户输入任务
   ↓
2. Parser 解析生成 ExecutionPlan (DAG)
   ↓
3. Matcher 为每个步骤匹配 Agent
   ↓
4. Workflow Engine 初始化 DAG
   - 计算入度 (in_degree)
   - 构建后继节点映射 (successors)
   ↓
5. 并行执行循环
   ├─ 从就绪队列取出所有入度为 0 的节点
   ├─ 使用 asyncio.gather 并发执行
   ├─ 更新全局上下文
   └─ 递减后继节点入度，入度为 0 则加入队列
   ↓
6. 汇总结果并保存为 Markdown 文件
```


---

## 技术栈

### 核心依赖

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | ≥3.10 | 主要开发语言 |
| Google Gemini | 2.0-flash | LLM 推理引擎 |
| LangChain | 2.0+ | LLM 应用框架 |
| MCP | 1.5+ | Agent 发现协议 |
| A2A SDK | 0.3+ | Agent 通信协议 |
| Pydantic | 2.11+ | 数据验证和建模 |
| asyncio | 内置 | 异步并发执行 |
| httpx | 0.28+ | HTTP 客户端 |
| Rich | - | 终端日志美化 |

### Agent 生态技术栈

| 组件 | 技术 | 端口 |
|------|------|------|
| MCP Server | FastMCP + Uvicorn | 10000 |
| Coder Agent | Starlette + Gemini | 10003 |
| Writer Agent | Starlette + Gemini | 10001 |
| Researcher Agent | Starlette + Gemini | 10002 |
| Reviewer Agent | Starlette + Gemini | 10004 |
| Translator Agent | Starlette + Gemini | 10005 |
| Data Analyst Agent | Starlette + Gemini | 10006 |

---

## 核心模块详解

### 1. Parser Layer (`src/yinqing/core/parser.py`)

**角色**：系统大脑，负责任务理解和拆解

**核心功能**：
- 使用 LangChain + Gemini 进行自然语言理解
- 将用户指令转化为结构化的 `ExecutionPlan`
- 自动识别任务间的依赖关系
- 生成符合 Pydantic 模型的 JSON 数据

**关键代码逻辑**：
```python
# 1. 构建 Prompt，明确要求 LLM 输出 DAG 结构
prompt = ChatPromptTemplate.from_template("""
    Break this goal into logical sub-tasks that support parallel execution.
    Each step must have:
    - Unique step_id
    - Clear description
    - Dependencies (step IDs)
    - Context keys needed
""")

# 2. 使用 JsonOutputParser 确保输出符合 ExecutionPlan 模型
chain = prompt | llm | JsonOutputParser(pydantic_object=ExecutionPlan)

# 3. 初始化 DAG 并检测循环依赖
plan.init_dag()
if plan.check_cycle():
    raise ValueError("Circular dependencies detected!")
```

**输出示例**：
```json
{
  "goal": "分析 Python、Java、Go 的优缺点并写总结报告",
  "steps": [
    {
      "step_id": 1,
      "name": "分析 Python",
      "description": "分析 Python 编程语言的优缺点",
      "dependencies": [],
      "context_keys": []
    },
    {
      "step_id": 2,
      "name": "分析 Java",
      "description": "分析 Java 编程语言的优缺点",
      "dependencies": [],
      "context_keys": []
    },
    {
      "step_id": 3,
      "name": "分析 Go",
      "description": "分析 Go 编程语言的优缺点",
      "dependencies": [],
      "context_keys": []
    },
    {
      "step_id": 4,
      "name": "写总结报告",
      "description": "基于前面的分析写一份对比总结报告",
      "dependencies": [1, 2, 3],
      "context_keys": ["step_1_output", "step_2_output", "step_3_output"]
    }
  ]
}
```


### 2. Matcher Layer (`src/yinqing/core/matcher.py`)

**角色**：资源调度器/猎头，负责为任务找到最合适的执行者

**核心功能**：
- 通过 MCP Client 连接 MCP Server
- 使用语义搜索匹配 Agent
- 内置 LRU 缓存机制（TTL 10分钟）
- 智能容错处理（处理 AgentCard 字段缺失）

**关键代码逻辑**：
```python
# 1. 缓存机制
def _get_cached_agent(self, description: str) -> Optional[AgentCard]:
    if description in self.agent_cache:
        agent_card, expire_time = self.agent_cache[description]
        if datetime.now() < expire_time:
            return agent_card
    return None

# 2. 调用 MCP Server 的 find_agent 工具
async def _find_agent_wrapper(self, session, description: str):
    result = await find_agent(session, description)
    if result and result.content:
        text = result.content[0].text
        agent_card_json = json.loads(clean_response_str(text))
        agent_card = AgentCard(**agent_card_json)
        self._set_cached_agent(description, agent_card)
        return agent_card
    return None

# 3. 为计划中的每个步骤匹配 Agent
async def match_agents(self, plan: ExecutionPlan):
    async with init_session(...) as session:
        for step in plan.steps:
            agent_card = await self._find_agent_wrapper(session, step.description)
            step.assigned_agent = agent_card
```

**匹配策略**：
- MCP Server 基于关键词匹配 Agent 的 name、description、skills、capabilities
- 支持模糊语义匹配（如"写代码" → Coder Agent）
- 评分机制：关键词命中越多，得分越高

### 3. Executor Layer (`src/yinqing/core/executor.py`)

**角色**：执行工头，负责与具体 Agent 的底层通信

**核心功能**：
- 封装 A2A 协议通信
- 自适应 Agent URL 发现（支持多种数据结构）
- 宽容的响应解析（绕过严格的 Pydantic 校验）
- 重试机制和错误处理

**关键代码逻辑**：
```python
# 1. 自适应 URL 发现
target_url = None
# 尝试从 config.http_url 获取
if hasattr(agent, 'config') and 'http_url' in agent.config:
    target_url = agent.config['http_url']
# 尝试从 url 属性获取
elif hasattr(agent, 'url'):
    target_url = agent.url
# 尝试从 interaction_endpoints 获取
elif hasattr(agent, 'interaction_endpoints'):
    target_url = agent.interaction_endpoints[0].get('url')

# 2. 构造 A2A 协议 Payload
payload = {
    "id": str(uuid.uuid4()),
    "method": "sendMessage",
    "params": {
        "message": {
            "role": "user",
            "parts": [{
                "text": json.dumps({
                    "task_description": step.description,
                    "context": filtered_context
                })
            }]
        }
    }
}

# 3. 使用 httpx 直接发送请求（绕过 a2a 库的严格校验）
async with httpx.AsyncClient(timeout=60.0) as client:
    response = await client.post(target_url, json=payload)
    response_json = response.json()
    
    # 4. 宽容解析响应
    result = response_json.get("result", {})
    message = result.get("message", {})
    parts = message.get("parts", [])
    text = parts[0].get("text", "") if parts else str(response_json)
```

**容错设计**：
- 支持标准 A2A 响应格式
- 支持简化格式（如 `{"result": {"message": "..."}}`）
- 支持纯文本响应
- 自动重试机制（默认 3 次，间隔 2 秒）


### 4. Workflow Engine (`src/yinqing/core/workflow.py`)

**角色**：项目经理/调度器，管理任务全生命周期

**核心功能**：
- 全局状态管理（上下文存储、步骤状态）
- DAG 初始化和拓扑排序
- 并行任务调度
- 断点续传支持
- 结果自动归档

**关键算法**：

#### 拓扑排序并行调度

```python
# 1. 初始化就绪队列（入度为 0 的节点）
queue = deque()
for step in plan.steps:
    if step.in_degree == 0 and step.status == "pending":
        queue.append(step.step_id)

# 2. 并行执行循环
while queue:
    # 取出当前所有可执行的步骤
    current_parallel_steps = [plan.step_map[step_id] for step_id in queue]
    queue.clear()
    
    # 并发执行（使用 asyncio.gather）
    results = await asyncio.gather(
        *[executor.execute_step(step, context, trace_id) 
          for step in current_parallel_steps],
        return_exceptions=True
    )
    
    # 处理结果并更新后继节点入度
    for step, result in results:
        context[f"step_{step.step_id}_output"] = result
        
        # 递减后继节点入度
        for succ_id in step.successors:
            succ_step = plan.step_map[succ_id]
            succ_step.in_degree -= 1
            
            # 入度为 0 则加入队列
            if succ_step.in_degree == 0:
                queue.append(succ_id)
```

**并行控制**：
- 支持最大并行数限制（默认 5）
- 失败策略可配置（continue/abort）
- 自动分批执行大规模并行任务

**状态管理**：
```python
# 全局上下文存储（支持断点续传）
self.global_context_store: Dict[str, Dict[str, Any]] = {}
# 步骤状态存储
self.step_status_store: Dict[str, Dict[int, TaskStep]] = {}
```

### 5. MCP Client (`src/yinqing/core/mcp_client.py`)

**角色**：MCP 协议客户端封装

**核心功能**：
- 支持 SSE 和 STDIO 两种传输方式
- 会话管理和初始化
- 工具调用封装

**关键代码**：
```python
@asynccontextmanager
async def init_session(host, port, transport):
    if transport == 'sse':
        url = f'http://{host}:{port}/sse'
        async with sse_client(url) as (read_stream, write_stream):
            async with ClientSession(
                read_stream=read_stream, 
                write_stream=write_stream
            ) as session:
                await session.initialize()
                yield session
    elif transport == 'stdio':
        # STDIO 传输方式
        ...

async def find_agent(session: ClientSession, query: str):
    return await session.call_tool(
        name='find_agent',
        arguments={'query': query}
    )
```

### 6. Types (`src/yinqing/core/types.py`)

**角色**：数据模型定义

**核心模型**：

#### TaskStep
```python
class TaskStep(BaseModel):
    step_id: int              # 步骤 ID
    name: str                 # 步骤名称
    description: str          # 步骤描述（用于 Agent 匹配）
    context_keys: List[str]   # 依赖的上下文键
    dependencies: List[int]   # 依赖的步骤 ID
    
    # DAG 相关字段
    in_degree: int = 0        # 入度（依赖数量）
    successors: List[int]     # 后继步骤 ID
    
    # 执行相关字段
    assigned_agent: Optional[AgentCard] = None
    result: Any = None
    status: str = "pending"   # pending/running/success/failed
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error: Optional[str] = None
```

#### ExecutionPlan
```python
class ExecutionPlan(BaseModel):
    goal: str                 # 用户目标
    steps: List[TaskStep]     # 任务步骤列表
    trace_id: str             # 追踪 ID
    task_id: Optional[str]
    context_id: Optional[str]
    step_map: Dict[int, TaskStep]  # 步骤映射（运行时）
    
    def init_dag(self):
        """初始化 DAG 的入度和后继步骤"""
        
    def check_cycle(self) -> bool:
        """检测循环依赖（DFS）"""
```


---

## 数据流转

### 完整数据流示例

假设用户输入：**"分析 Python 和 Java 的优缺点，然后写一份对比报告"**

#### 阶段 1：任务解析

```
用户输入 → Parser Layer
           ↓
       Gemini LLM 推理
           ↓
       ExecutionPlan {
         steps: [
           {step_id: 1, name: "分析Python", dependencies: []},
           {step_id: 2, name: "分析Java", dependencies: []},
           {step_id: 3, name: "写对比报告", dependencies: [1, 2]}
         ]
       }
           ↓
       DAG 初始化
       - Step 1: in_degree=0, successors=[3]
       - Step 2: in_degree=0, successors=[3]
       - Step 3: in_degree=2, successors=[]
```

#### 阶段 2：Agent 匹配

```
ExecutionPlan → Matcher Layer
                ↓
            MCP Client → MCP Server
                         ↓
                     find_agent("分析Python...")
                         ↓
                     返回 Researcher Agent Card
                ↓
Step 1.assigned_agent = Researcher Agent
Step 2.assigned_agent = Researcher Agent
Step 3.assigned_agent = Writer Agent
```

#### 阶段 3：并行执行

```
Workflow Engine 初始化
    ↓
就绪队列 = [Step 1, Step 2]  (入度为 0)
    ↓
并行执行 Step 1 和 Step 2
    ├─ Executor → POST http://localhost:10002 (Researcher Agent)
    │   Payload: {"task_description": "分析Python...", "context": {}}
    │   Response: "Python 优点：简洁易学... 缺点：性能较慢..."
    │
    └─ Executor → POST http://localhost:10002 (Researcher Agent)
        Payload: {"task_description": "分析Java...", "context": {}}
        Response: "Java 优点：性能优秀... 缺点：语法冗长..."
    ↓
更新全局上下文
    context["step_1_output"] = "Python 优点：..."
    context["step_2_output"] = "Java 优点：..."
    ↓
更新 Step 3 入度
    Step 3.in_degree = 2 - 1 - 1 = 0
    ↓
就绪队列 = [Step 3]
    ↓
执行 Step 3
    Executor → POST http://localhost:10001 (Writer Agent)
    Payload: {
        "task_description": "写对比报告",
        "context": {
            "step_1_output": "Python 优点：...",
            "step_2_output": "Java 优点：..."
        }
    }
    Response: "# Python vs Java 对比报告\n\n## Python\n..."
    ↓
保存结果到文件
    output/分析Python和Java_abc12345.md
```

### 上下文传递机制

```python
# 1. 全局上下文初始化
global_context = {
    "user_query": "分析 Python 和 Java...",
    "trace_id": "abc12345-..."
}

# 2. 步骤执行后更新上下文
global_context[f"step_{step.step_id}_output"] = result

# 3. 后续步骤筛选所需上下文
filtered_context = {}
for key in step.context_keys:  # ["step_1_output", "step_2_output"]
    if key in global_context:
        filtered_context[key] = global_context[key]

# 4. 传递给 Agent
payload = {
    "task_description": step.description,
    "context": filtered_context
}
```


---

## 目录结构

```
YinQing_Agent/
│
├── src/yinqing/                    # 核心引擎代码
│   ├── core/                       # 核心模块
│   │   ├── __init__.py
│   │   ├── parser.py               # [Parser] 任务拆解层
│   │   ├── matcher.py              # [Matcher] 能力匹配层
│   │   ├── executor.py             # [Executor] 任务执行层
│   │   ├── workflow.py             # [Workflow] 编排引擎
│   │   ├── mcp_client.py           # [MCP] MCP 客户端封装
│   │   └── types.py                # [Types] 数据模型定义
│   │
│   ├── utils/                      # 工具模块
│   │   ├── logger.py               # Rich 日志配置
│   │   ├── config.py               # 环境变量和配置
│   │   └── common.py               # 通用常量和函数
│   │
│   └── main.py                     # CLI 入口
│
├── real_ecosystem/                 # Agent 生态系统
│   ├── agents/                     # Agent 实现
│   │   ├── coder.py                # 代码生成 Agent (端口 10003)
│   │   ├── writer.py               # 内容写作 Agent (端口 10001)
│   │   ├── researcher.py           # 研究分析 Agent (端口 10002)
│   │   ├── reviewer.py             # 代码审查 Agent (端口 10004)
│   │   ├── translator.py           # 翻译 Agent (端口 10005)
│   │   └── data_analyst.py         # 数据分析 Agent (端口 10006)
│   │
│   ├── cards/                      # Agent 名片（JSON 格式）
│   │   ├── coder.json
│   │   ├── writer.json
│   │   ├── researcher.json
│   │   ├── reviewer.json
│   │   ├── translator.json
│   │   └── data_analyst.json
│   │
│   ├── mcp_server/                 # MCP Server 实现
│   │   └── server.py               # Agent 注册和发现服务 (端口 10000)
│   │
│   └── integration_test.py         # 集成测试脚本
│
├── output/                         # 自动生成的任务结果
│   └── *.md                        # 按 trace_id 命名的结果文件
│
├── .env                            # 环境变量配置
├── pyproject.toml                  # 项目配置和依赖
├── uv.lock                         # 依赖锁定文件
├── README.md                       # 项目说明文档
├── ARCHITECTURE.md                 # 架构详解文档（本文件）
├── run_local.sh                    # 一键启动脚本
└── start_real_agents.sh            # 启动所有 Agent 的脚本
```

### 关键文件说明

#### 配置文件

- `.env`: 存储 API Key 等敏感信息
  ```bash
  GOOGLE_API_KEY=your-api-key
  MCP_SERVER_HOST=localhost
  MCP_SERVER_PORT=10000
  MCP_SERVER_TRANSPORT=sse
  ```

- `pyproject.toml`: Python 项目配置
  ```toml
  [project]
  name = "yinqing-agent"
  version = "0.1.0"
  dependencies = [
      "a2a-sdk[sql]>=0.3.0",
      "langchain-google-genai>=2.0.10",
      "mcp[cli]>=1.5.0",
      ...
  ]
  ```

#### Agent 名片示例 (`cards/coder.json`)

```json
{
  "name": "Coder Agent",
  "description": "A senior software engineer specialized in writing clean code",
  "capabilities": {
    "code_generation": "Generate code in multiple languages",
    "code_review": "Review and provide feedback on code",
    "algorithm_design": "Design efficient algorithms"
  },
  "skills": [
    {
      "name": "Python Programming",
      "description": "Expert in Python development",
      "tags": ["python", "coding", "programming"]
    },
    {
      "name": "Code Review",
      "description": "Provide constructive code review",
      "tags": ["review", "feedback", "quality"]
    }
  ],
  "config": {
    "http_url": "http://localhost:10003"
  }
}
```


---

## 关键算法

### 1. DAG 循环依赖检测（DFS）

```python
def check_cycle(self) -> bool:
    """使用深度优先搜索检测 DAG 中的循环依赖"""
    visited = set()      # 已访问节点
    rec_stack = set()    # 递归栈（当前路径）
    
    def dfs(step_id):
        if step_id in rec_stack:
            return True  # 发现循环
        if step_id in visited:
            return False # 已访问过，无循环
            
        visited.add(step_id)
        rec_stack.add(step_id)
        
        # 遍历后继节点
        for succ_id in self.step_map[step_id].successors:
            if dfs(succ_id):
                return True
                
        rec_stack.remove(step_id)
        return False
    
    # 检查所有节点
    for step_id in self.step_map:
        if dfs(step_id):
            return True
    return False
```

**时间复杂度**：O(V + E)，其中 V 是节点数，E 是边数

### 2. 拓扑排序并行调度

```python
# 初始化入度
for step in plan.steps:
    step.in_degree = len(step.dependencies)

# 初始化就绪队列
queue = deque([step.step_id for step in plan.steps if step.in_degree == 0])

# 并行执行循环
while queue:
    # 取出所有可执行节点
    current_batch = [plan.step_map[sid] for sid in queue]
    queue.clear()
    
    # 并发执行
    results = await asyncio.gather(*[
        executor.execute_step(step, context, trace_id)
        for step in current_batch
    ])
    
    # 更新后继节点入度
    for step, result in results:
        for succ_id in step.successors:
            succ_step = plan.step_map[succ_id]
            succ_step.in_degree -= 1
            if succ_step.in_degree == 0:
                queue.append(succ_id)
```

**关键特性**：
- 每轮执行所有入度为 0 的节点（最大化并行度）
- 使用 `asyncio.gather` 实现真正的并发
- 动态更新入度，自动发现新的可执行节点

### 3. Agent 匹配算法（关键词评分）

```python
def find_agent(query: str) -> AgentCard:
    """基于关键词评分匹配最合适的 Agent"""
    query_lower = query.lower()
    keywords = query_lower.split()
    
    best_score = 0
    best_agent = None
    
    for agent_card in all_agents:
        # 构建可搜索文本
        searchable_text = " ".join([
            agent_card.name,
            agent_card.description,
            " ".join(agent_card.capabilities.keys()),
            " ".join([skill.name for skill in agent_card.skills]),
            " ".join([tag for skill in agent_card.skills for tag in skill.tags])
        ]).lower()
        
        # 计算匹配分数
        score = sum(1 for kw in keywords if kw in searchable_text)
        
        if score > best_score:
            best_score = score
            best_agent = agent_card
    
    return best_agent
```

**优化策略**：
- 深度搜索 skills 和 tags，提高匹配准确率
- 支持模糊匹配（如"写代码"可以匹配"code generation"）
- 缓存机制减少重复查询

### 4. 自适应响应解析

```python
def parse_agent_response(response_json: dict) -> str:
    """宽容解析多种 Agent 响应格式"""
    try:
        # 标准 A2A 格式
        result = response_json.get("result", {})
        message = result.get("message", {})
        parts = message.get("parts", [])
        if parts:
            return parts[0].get("text", "")
        
        # 简化格式 1
        if "text" in result:
            return result["text"]
        
        # 简化格式 2
        if "message" in response_json:
            return response_json["message"]
        
        # 兜底：返回整个 JSON 字符串
        return str(response_json)
    except Exception:
        return str(response_json)
```

**容错设计**：
- 多层级尝试解析
- 兜底策略确保不会崩溃
- 自动清理响应中的 Markdown 代码块标记


---

## 扩展性设计

### 1. 添加新 Agent

#### 步骤 1：实现 Agent 服务

```python
# real_ecosystem/agents/my_agent.py
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

class MyAgent:
    async def handle_request(self, request):
        body = await request.json()
        # 提取任务描述
        user_msg = body['params']['message']['parts'][0]['text']
        payload = json.loads(user_msg)
        
        # 执行任务逻辑
        result = self.process_task(payload['task_description'], payload['context'])
        
        # 返回 A2A 格式响应
        return JSONResponse({
            "result": {
                "message": {
                    "role": "model",
                    "parts": [{"text": result}]
                }
            }
        })

agent = MyAgent()
app = Starlette(routes=[Route("/", agent.handle_request, methods=["POST"])])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10007)
```

#### 步骤 2：创建 Agent 名片

```json
// real_ecosystem/cards/my_agent.json
{
  "name": "My Custom Agent",
  "description": "A specialized agent for custom tasks",
  "capabilities": {
    "custom_task": "Perform custom operations"
  },
  "skills": [
    {
      "name": "Custom Skill",
      "description": "Specialized skill description",
      "tags": ["custom", "specialized", "task"]
    }
  ],
  "config": {
    "http_url": "http://localhost:10007"
  }
}
```

#### 步骤 3：启动 Agent

```bash
# 添加到 start_real_agents.sh
python real_ecosystem/agents/my_agent.py &
```

### 2. 扩展 MCP Server

#### 添加新工具

```python
# real_ecosystem/mcp_server/server.py
@mcp.tool()
def list_all_agents() -> str:
    """列出所有可用的 Agent"""
    cards_dir = os.path.join(os.path.dirname(__file__), "../cards")
    agents = []
    for filename in os.listdir(cards_dir):
        if filename.endswith(".json"):
            with open(os.path.join(cards_dir, filename), "r") as f:
                agents.append(json.load(f))
    return json.dumps(agents)

@mcp.tool()
def get_agent_by_name(name: str) -> str:
    """根据名称获取 Agent 详细信息"""
    # 实现逻辑
    ...
```

### 3. 自定义执行策略

#### 添加新的失败策略

```python
# src/yinqing/core/types.py
class ParallelConfig(BaseModel):
    fail_strategy: str = "continue"  # continue/abort/retry
    max_parallel: int = 5
    retry_times: int = 3  # 新增：重试次数
    retry_delay: int = 2  # 新增：重试延迟

# src/yinqing/core/workflow.py
async def _execute_parallel_steps(self, steps, context, trace_id):
    if self.parallel_config.fail_strategy == "retry":
        # 实现重试逻辑
        for attempt in range(self.parallel_config.retry_times):
            try:
                results = await asyncio.gather(*tasks)
                break
            except Exception as e:
                if attempt == self.parallel_config.retry_times - 1:
                    raise
                await asyncio.sleep(self.parallel_config.retry_delay)
```

### 4. 集成外部服务

#### 添加数据库支持

```python
# src/yinqing/utils/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class TaskRepository:
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
    
    def save_execution_plan(self, plan: ExecutionPlan):
        """保存执行计划到数据库"""
        session = self.Session()
        # 实现保存逻辑
        session.commit()
    
    def load_execution_plan(self, trace_id: str) -> ExecutionPlan:
        """从数据库加载执行计划"""
        session = self.Session()
        # 实现加载逻辑
        return plan
```

#### 添加监控和日志

```python
# src/yinqing/utils/monitoring.py
from prometheus_client import Counter, Histogram

task_counter = Counter('yinqing_tasks_total', 'Total tasks executed')
task_duration = Histogram('yinqing_task_duration_seconds', 'Task execution duration')

class MonitoringMiddleware:
    async def track_execution(self, step: TaskStep):
        with task_duration.time():
            result = await self.executor.execute_step(step)
            task_counter.inc()
        return result
```

### 5. 性能优化建议

#### 缓存优化

```python
# 使用 Redis 替代内存缓存
import redis
from datetime import timedelta

class RedisAgentCache:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
    
    def get(self, key: str) -> Optional[AgentCard]:
        data = self.redis.get(key)
        if data:
            return AgentCard(**json.loads(data))
        return None
    
    def set(self, key: str, agent: AgentCard, ttl: timedelta):
        self.redis.setex(key, ttl, json.dumps(agent.dict()))
```

#### 连接池优化

```python
# 使用连接池减少 HTTP 连接开销
import httpx

class OptimizedExecutor:
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=60.0,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
        )
    
    async def execute_step(self, step: TaskStep, context: dict):
        # 复用连接
        response = await self.client.post(url, json=payload)
        return response.json()
```


---

## 设计模式与最佳实践

### 1. 使用的设计模式

#### 分层架构模式（Layered Architecture）
- **表现层**：CLI (main.py)
- **业务逻辑层**：Workflow Engine
- **服务层**：Parser, Matcher, Executor
- **数据访问层**：MCP Client, A2A Protocol

#### 策略模式（Strategy Pattern）
```python
# 不同的失败处理策略
class FailureStrategy:
    def handle(self, error): pass

class ContinueStrategy(FailureStrategy):
    def handle(self, error):
        logger.warning(f"Step failed: {error}, continuing...")

class AbortStrategy(FailureStrategy):
    def handle(self, error):
        raise Exception(f"Aborting workflow: {error}")
```

#### 工厂模式（Factory Pattern）
```python
# Agent 工厂
class AgentFactory:
    @staticmethod
    def create_agent(agent_card: AgentCard):
        if agent_card.type == "coder":
            return CoderAgent(agent_card)
        elif agent_card.type == "writer":
            return WriterAgent(agent_card)
        # ...
```

#### 观察者模式（Observer Pattern）
```python
# 任务状态变化通知
class TaskObserver:
    def on_task_start(self, step: TaskStep): pass
    def on_task_complete(self, step: TaskStep): pass
    def on_task_failed(self, step: TaskStep): pass

class LoggingObserver(TaskObserver):
    def on_task_start(self, step):
        logger.info(f"Task {step.step_id} started")
```

### 2. 代码质量保证

#### 类型注解
```python
from typing import Dict, List, Optional, Tuple

async def execute_step(
    self, 
    step: TaskStep, 
    context: Dict[str, Any], 
    trace_id: str
) -> Tuple[TaskStep, str]:
    """
    执行单个任务步骤
    
    Args:
        step: 任务步骤对象
        context: 全局上下文字典
        trace_id: 追踪 ID
        
    Returns:
        (步骤对象, 执行结果字符串)
    """
    ...
```

#### 错误处理
```python
# 分层错误处理
class YinQingException(Exception):
    """基础异常类"""
    pass

class ParserException(YinQingException):
    """解析异常"""
    pass

class MatcherException(YinQingException):
    """匹配异常"""
    pass

class ExecutorException(YinQingException):
    """执行异常"""
    pass

# 使用
try:
    plan = await self.parser.parse(query)
except ParserException as e:
    logger.error(f"Failed to parse query: {e}")
    # 降级处理
```

#### 日志规范
```python
# 使用结构化日志
logger.info(
    "Task execution completed",
    extra={
        "trace_id": trace_id,
        "step_id": step.step_id,
        "duration": duration,
        "status": step.status
    }
)
```

### 3. 性能考虑

#### 并发控制
```python
# 使用信号量限制并发数
semaphore = asyncio.Semaphore(max_parallel)

async def execute_with_limit(step):
    async with semaphore:
        return await executor.execute_step(step)

results = await asyncio.gather(*[
    execute_with_limit(step) for step in steps
])
```

#### 超时控制
```python
# 为每个步骤设置超时
try:
    result = await asyncio.wait_for(
        executor.execute_step(step),
        timeout=step.timeout or 60.0
    )
except asyncio.TimeoutError:
    logger.error(f"Step {step.step_id} timed out")
    step.status = "timeout"
```

#### 资源清理
```python
# 使用上下文管理器确保资源释放
@asynccontextmanager
async def managed_session():
    session = await create_session()
    try:
        yield session
    finally:
        await session.close()
```


---

## 常见问题与解决方案

### 1. 任务拆解不合理

**问题**：LLM 生成的任务步骤过于粗糙或过于细碎

**解决方案**：
```python
# 优化 Prompt，添加示例
prompt = ChatPromptTemplate.from_template("""
    Break down the task into 3-10 logical steps.
    
    Good Example:
    Task: "研究 AI 趋势并写报告"
    Steps:
    1. 搜索最新 AI 研究论文
    2. 分析主要趋势
    3. 撰写研究报告
    
    Bad Example (too granular):
    1. 打开浏览器
    2. 输入搜索关键词
    3. 点击第一个链接
    ...
""")
```

### 2. Agent 匹配不准确

**问题**：任务描述与 Agent 能力不匹配

**解决方案**：
```python
# 1. 丰富 Agent 名片的 tags
{
  "skills": [
    {
      "name": "Code Generation",
      "tags": ["coding", "programming", "write code", "implement", "develop"]
    }
  ]
}

# 2. 使用语义相似度匹配（可选）
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

def semantic_match(query: str, agent_cards: List[AgentCard]):
    query_embedding = model.encode(query)
    best_score = -1
    best_agent = None
    
    for agent in agent_cards:
        agent_text = f"{agent.name} {agent.description}"
        agent_embedding = model.encode(agent_text)
        similarity = cosine_similarity(query_embedding, agent_embedding)
        
        if similarity > best_score:
            best_score = similarity
            best_agent = agent
    
    return best_agent
```

### 3. 循环依赖问题

**问题**：LLM 生成的依赖关系存在循环

**解决方案**：
```python
# 自动修复循环依赖
def fix_circular_dependencies(plan: ExecutionPlan):
    if not plan.check_cycle():
        return plan
    
    # 策略 1：移除导致循环的边
    for step in plan.steps:
        for dep_id in step.dependencies[:]:
            # 临时移除依赖
            step.dependencies.remove(dep_id)
            if not plan.check_cycle():
                logger.warning(f"Removed circular dependency: {step.step_id} -> {dep_id}")
                break
            # 恢复依赖
            step.dependencies.append(dep_id)
    
    return plan
```

### 4. Agent 响应超时

**问题**：某些 Agent 处理时间过长

**解决方案**：
```python
# 1. 设置合理的超时时间
async def execute_step_with_timeout(step: TaskStep, timeout: float = 120.0):
    try:
        return await asyncio.wait_for(
            executor.execute_step(step),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        # 降级处理
        return await fallback_handler(step)

# 2. 实现降级策略
async def fallback_handler(step: TaskStep):
    logger.warning(f"Step {step.step_id} timed out, using fallback")
    return f"[Timeout] Unable to complete: {step.description}"
```

### 5. 上下文过大

**问题**：随着步骤增多，上下文数据越来越大

**解决方案**：
```python
# 1. 只保留必要的上下文
def prune_context(context: dict, max_size: int = 10000):
    """修剪过大的上下文"""
    pruned = {}
    for key, value in context.items():
        if isinstance(value, str) and len(value) > max_size:
            pruned[key] = value[:max_size] + "... [truncated]"
        else:
            pruned[key] = value
    return pruned

# 2. 使用摘要
async def summarize_context(context: dict):
    """使用 LLM 对上下文进行摘要"""
    if len(str(context)) > 50000:
        summary = await llm.summarize(str(context))
        return {"summary": summary}
    return context
```

### 6. 并发控制

**问题**：过多并发导致资源耗尽

**解决方案**：
```python
# 动态调整并发数
class AdaptiveParallelConfig:
    def __init__(self):
        self.max_parallel = 5
        self.current_load = 0
    
    async def adjust_parallel(self):
        # 根据系统负载动态调整
        cpu_usage = psutil.cpu_percent()
        if cpu_usage > 80:
            self.max_parallel = max(1, self.max_parallel - 1)
        elif cpu_usage < 50:
            self.max_parallel = min(10, self.max_parallel + 1)
```

---

## 未来规划

### 短期目标（1-3 个月）

1. **增强 Parser 能力**
   - 支持更复杂的依赖关系（条件依赖、循环依赖）
   - 添加任务优先级支持
   - 支持动态任务生成

2. **优化 Matcher**
   - 集成向量数据库（如 Pinecone）进行语义搜索
   - 支持 Agent 负载均衡
   - 添加 Agent 性能评分机制

3. **完善监控**
   - 集成 Prometheus + Grafana
   - 添加任务执行可视化面板
   - 实时性能指标监控

### 中期目标（3-6 个月）

1. **分布式支持**
   - 支持多机部署
   - 添加任务队列（如 Celery）
   - 实现 Agent 集群管理

2. **安全增强**
   - 添加 Agent 认证机制
   - 实现任务权限控制
   - 敏感数据加密

3. **生态建设**
   - 建立 Agent 市场
   - 提供 Agent 开发 SDK
   - 社区贡献机制

### 长期目标（6-12 个月）

1. **智能优化**
   - 基于历史数据优化任务拆解
   - 自动学习最优 Agent 匹配
   - 预测任务执行时间

2. **多模态支持**
   - 支持图像、音频、视频处理任务
   - 集成多模态 Agent

3. **企业级特性**
   - SLA 保证
   - 多租户支持
   - 审计日志

---

## 总结

YinQing Agent 是一个设计精良、架构清晰的 Agent 编排系统，具有以下核心优势：

1. **智能化**：利用 LLM 实现任务的智能拆解和理解
2. **高效性**：基于 DAG 的并行调度引擎，最大化执行效率
3. **灵活性**：通过 MCP 协议实现 Agent 的动态发现和匹配
4. **可扩展性**：模块化设计，易于添加新 Agent 和功能
5. **稳健性**：完善的错误处理和重试机制

该系统适用于需要多步骤协作、复杂依赖关系的 AI 任务场景，是构建企业级 AI 应用的理想基础设施。

---

## 参考资料

- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [A2A Protocol Documentation](https://github.com/google/a2a)
- [LangChain Documentation](https://python.langchain.com/)
- [Google Gemini API](https://ai.google.dev/)
- [Asyncio Documentation](https://docs.python.org/3/library/asyncio.html)

---

**文档版本**：1.0  
**最后更新**：2024-12  
**维护者**：YinQing Agent Team
