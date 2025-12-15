# 智能体编排系统 (Agent Orchestration System)

## 📖 项目简介
本项目是一个高级的多智能体协作编排系统（Yinqing Core），旨在通过自然语言指令自动调度多个AI Agent协同完成复杂任务。系统采用"大脑-肢体"架构，由中央编排器负责任务拆解、分发、审核，各垂直领域Agent负责具体执行。

## 🌟 核心特性
- **增强型编排器 (Enhanced Workflow Engine)**:
  - **DAG任务流**: 支持并行任务执行和依赖管理。
  - **质量审核 (Reviewer Layer)**: 内置审核机制，自动检查任务结果质量。
  - **状态回溯 (Snapshot & Rollback)**: 支持执行快照，失败时可回溯到指定步骤。
  - **智能重试**: 基于审核结果自动优化重试。

- **多模态Agent生态**:
  - **Writer**: 内容创作与大纲编写。
  - **Researcher**: 网络信息搜集与整合。
  - **Word/Excel Generator**: 自动化生成结构化文档。
  - **Coder**: 代码生成与执行。

## 🏗️ 系统架构

### 1. 核心层 (`src/yinqing/core`)
- **Parser (大脑)**: 解析用户指令，生成包含依赖关系的执行计划 (ExecutionPlan)。
- **Matcher (调度)**: 根据Agent能力描述卡片 (`cards/`)，将任务步骤分配给最合适的Agent。
- **Executor (执行)**: 负责与Agent通信（HTTP/MCP协议），执行具体步骤。
- **Reviewer (质检)**: 对执行结果进行评分和反馈，决定是否通过或需要重试。

### 2. 生态层 (`real_ecosystem`)
包含实际运行的Agent服务。每个Agent都是一个独立的HTTP服务，通过标准接口与编排器交互。

## 🚀 快速开始

### 环境准备
```bash
# 安装依赖
pip install -r requirements.txt
```

### 运行编排器
```bash
# 启动本地Agent集群
./start_real_agents.sh

# 运行编排器示例
python src/yinqing/main_enhanced.py
```

## 🔮 未来规划 (Roadmap)

### 1. PPT 自动生成 (PPT Agent)
目标：实现"一句话生成图文并茂的PPT"。
- **自主视觉决策**: 编排器将分析每一页PPT的文本内容，自主判断是否需要配图。
- **图像生成集成**: 动态调用图像生成Agent（如Flux/Midjourney）生成素材。
- **智能排版**: 根据内容量自动选择合适的幻灯片布局。

### 2. 编排器能力升级
- **动态规划 (Dynamic Planning)**: 允许在执行过程中根据中间结果动态增加或修改后续步骤（例如：发现资料不足时自动增加搜索步骤）。
- **人机交互增强**: 在关键节点支持人工介入确认或修改方向。

## 🛠️ 项目结构
```
.
├── src/
│   └── yinqing/
│       ├── core/           # 核心引擎代码
│       ├── utils/          # 工具函数
│       └── main_enhanced.py # 主入口
├── real_ecosystem/         # Agent实现
│   ├── agents/             # 具体Agent代码
│   └── cards/              # Agent能力描述
├── output/                 # 任务生成结果
└── start_real_agents.sh    # 启动脚本
```
