import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator
from a2a.types import AgentCard

def generate_trace_id() -> str:
    return str(uuid.uuid4())

class TaskStep(BaseModel):
    """定义单个任务步骤（扩展DAG相关字段）"""
    step_id: int = Field(description="步骤ID，唯一且递增")
    name: str = Field(description="简短的步骤名称")
    description: str = Field(description="该步骤具体要做什么，用于搜索 Agent")
    context_keys: List[str] = Field(description="该步骤依赖前序步骤的哪些输出key")
    dependencies: List[int] = Field(default=[], description="依赖的步骤ID列表（如[1,2]表示依赖步骤1和2）")
    
    # DAG相关字段（运行时注入）
    in_degree: int = Field(default=0, description="入度：依赖的步骤数量，用于拓扑排序")
    successors: List[int] = Field(default=[], description="后继步骤ID：依赖当前步骤的步骤，用于更新入度")
    assigned_agent: Optional[AgentCard] = None
    result: Any = None
    status: str = Field(default="pending", description="步骤状态：pending/running/success/failed/skipped")
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error: Optional[str] = None

    @validator("step_id")
    def step_id_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("step_id must be a positive integer")
        return v

class ExecutionPlan(BaseModel):
    """定义整体执行计划（扩展DAG相关）"""
    goal: str
    steps: List[TaskStep]
    trace_id: str = Field(default_factory=generate_trace_id)
    task_id: Optional[str] = None
    context_id: Optional[str] = None
    # DAG依赖映射：step_id -> 步骤对象（运行时注入）
    step_map: Dict[int, TaskStep] = Field(default_factory=dict, exclude=True)

    def init_dag(self):
        """初始化DAG的入度和后继步骤"""
        # 构建step_map
        self.step_map = {step.step_id: step for step in self.steps}
        # 初始化入度和后继步骤
        for step in self.steps:
            # 入度 = 依赖的步骤数量
            step.in_degree = len(step.dependencies)
            # 为每个依赖的步骤添加后继步骤
            for dep_id in step.dependencies:
                if dep_id in self.step_map:
                    self.step_map[dep_id].successors.append(step.step_id)

    def check_cycle(self) -> bool:
        """检测DAG是否有循环依赖（有则返回True）"""
        visited = set()
        rec_stack = set()

        def dfs(step_id):
            if step_id in rec_stack:
                return True
            if step_id in visited:
                return False
            visited.add(step_id)
            rec_stack.add(step_id)
            # 遍历后继步骤
            for succ_id in self.step_map[step_id].successors:
                if dfs(succ_id):
                    return True
            rec_stack.remove(step_id)
            return False

        for step_id in self.step_map:
            if dfs(step_id):
                return True
        return False

class ParallelConfig(BaseModel):
    """并行执行配置"""
    fail_strategy: str = Field(default="continue", description="失败策略：continue（继续）/ abort（终止所有并行步骤）")
    max_parallel: int = Field(default=5, description="最大并行数")
