"""
YinQing Agent Core Module

核心编排引擎组件:
- types: 数据模型定义
- parser: 任务解析层
- matcher: 能力匹配层
- executor: 任务执行层
- workflow: 基础工作流引擎
- workflow_enhanced: 增强版工作流引擎（支持审核和回溯）
- reviewer: 审核层
- snapshot: 快照管理器
- mcp_client: MCP客户端
"""

from yinqing.core.types import (
    TaskStep,
    ExecutionPlan,
    ParallelConfig,
    AgentCard,
    generate_trace_id
)

from yinqing.core.workflow import WorkflowEngine

# 新增：增强版组件
from yinqing.core.reviewer import (
    ReviewerLayer,
    ReviewConfig,
    ReviewResult,
    RollbackAction
)

from yinqing.core.snapshot import (
    SnapshotManager,
    ExecutionSnapshot,
    StepState
)

from yinqing.core.workflow_enhanced import (
    EnhancedWorkflowEngine,
    create_review_config
)

__all__ = [
    # 基础类型
    "TaskStep",
    "ExecutionPlan",
    "ParallelConfig",
    "AgentCard",
    "generate_trace_id",

    # 基础引擎
    "WorkflowEngine",

    # 审核组件
    "ReviewerLayer",
    "ReviewConfig",
    "ReviewResult",
    "RollbackAction",

    # 快照组件
    "SnapshotManager",
    "ExecutionSnapshot",
    "StepState",

    # 增强版引擎
    "EnhancedWorkflowEngine",
    "create_review_config",
]
