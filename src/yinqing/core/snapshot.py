"""
快照管理器 (Snapshot Manager)
负责执行过程中的状态快照和恢复，支持流程回溯
"""

import copy
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from pydantic import BaseModel, Field
from collections import OrderedDict

from yinqing.utils.logger import get_logger

logger = get_logger(__name__)


# ==================== 数据模型 ====================

class StepState(BaseModel):
    """步骤状态快照"""
    step_id: int
    status: str = "pending"  # pending, running, success, failed
    result: Optional[Any] = None
    retry_count: int = 0
    error_history: List[str] = Field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class ExecutionSnapshot(BaseModel):
    """执行快照 - 保存某一时刻的完整执行状态"""
    snapshot_id: str = Field(description="快照唯一ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="快照时间")
    trace_id: str = Field(description="任务追踪ID")
    step_id: int = Field(description="快照对应的步骤ID（执行前）")

    # 状态数据
    global_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="全局上下文副本"
    )
    step_states: Dict[int, StepState] = Field(
        default_factory=dict,
        description="所有步骤状态"
    )

    # DAG状态
    in_degrees: Dict[int, int] = Field(
        default_factory=dict,
        description="各步骤的入度"
    )
    completed_steps: List[int] = Field(
        default_factory=list,
        description="已完成的步骤ID列表"
    )
    pending_steps: List[int] = Field(
        default_factory=list,
        description="待执行的步骤ID列表"
    )

    class Config:
        arbitrary_types_allowed = True


# ==================== 快照管理器 ====================

class SnapshotManager:
    """
    执行快照管理器

    职责:
    1. 在关键执行点创建状态快照
    2. 支持恢复到指定快照状态
    3. 管理快照生命周期（自动清理过期快照）
    """

    def __init__(self, max_snapshots_per_trace: int = 50):
        """
        初始化快照管理器

        Args:
            max_snapshots_per_trace: 每个trace最多保留的快照数量
        """
        self.snapshots: Dict[str, ExecutionSnapshot] = OrderedDict()
        self.trace_snapshots: Dict[str, List[str]] = {}  # trace_id -> [snapshot_ids]
        self.max_snapshots_per_trace = max_snapshots_per_trace

    def create_snapshot(
        self,
        trace_id: str,
        step_id: int,
        context: Dict[str, Any],
        step_states: Dict[int, Dict],
        in_degrees: Dict[int, int]
    ) -> ExecutionSnapshot:
        """
        创建执行快照

        Args:
            trace_id: 任务追踪ID
            step_id: 当前要执行的步骤ID（快照为执行前状态）
            context: 全局上下文
            step_states: 所有步骤的状态 {step_id: {status, result, ...}}
            in_degrees: 各步骤的入度

        Returns:
            ExecutionSnapshot: 创建的快照
        """
        snapshot_id = f"{trace_id}_{step_id}_{int(time.time() * 1000)}"

        # 深拷贝上下文避免后续修改影响快照
        snapshot = ExecutionSnapshot(
            snapshot_id=snapshot_id,
            trace_id=trace_id,
            step_id=step_id,
            global_context=copy.deepcopy(context),
            step_states={
                sid: StepState(
                    step_id=sid,
                    status=state.get("status", "pending"),
                    result=copy.deepcopy(state.get("result")),
                    retry_count=state.get("retry_count", 0),
                    error_history=list(state.get("error_history", [])),
                    start_time=state.get("start_time"),
                    end_time=state.get("end_time")
                )
                for sid, state in step_states.items()
            },
            in_degrees=copy.deepcopy(in_degrees),
            completed_steps=[
                sid for sid, state in step_states.items()
                if state.get("status") == "success"
            ],
            pending_steps=[
                sid for sid, state in step_states.items()
                if state.get("status") == "pending"
            ]
        )

        # 存储快照
        self.snapshots[snapshot_id] = snapshot

        # 维护trace -> snapshots映射
        if trace_id not in self.trace_snapshots:
            self.trace_snapshots[trace_id] = []
        self.trace_snapshots[trace_id].append(snapshot_id)

        # 清理过多的快照
        self._cleanup_old_snapshots(trace_id)

        logger.debug(
            f"[快照] 创建快照 {snapshot_id} "
            f"(step={step_id}, completed={len(snapshot.completed_steps)})"
        )

        return snapshot

    def get_snapshot(self, snapshot_id: str) -> Optional[ExecutionSnapshot]:
        """获取指定快照"""
        return self.snapshots.get(snapshot_id)

    def get_latest_snapshot(self, trace_id: str) -> Optional[ExecutionSnapshot]:
        """获取指定trace的最新快照"""
        if trace_id not in self.trace_snapshots:
            return None

        snapshot_ids = self.trace_snapshots[trace_id]
        if not snapshot_ids:
            return None

        return self.snapshots.get(snapshot_ids[-1])

    def get_rollback_snapshot(
        self,
        trace_id: str,
        target_step_id: int
    ) -> Optional[ExecutionSnapshot]:
        """
        获取回溯到指定步骤的快照

        找到目标步骤执行前的最近快照

        Args:
            trace_id: 任务追踪ID
            target_step_id: 要回溯到的步骤ID

        Returns:
            ExecutionSnapshot: 适合回溯的快照，如果不存在则返回None
        """
        if trace_id not in self.trace_snapshots:
            logger.warning(f"[快照] 未找到trace {trace_id} 的任何快照")
            return None

        # 找到目标步骤执行前的快照
        candidates = []
        for snapshot_id in self.trace_snapshots[trace_id]:
            snapshot = self.snapshots.get(snapshot_id)
            if snapshot and snapshot.step_id <= target_step_id:
                # 确保目标步骤在这个快照中是pending状态
                step_state = snapshot.step_states.get(target_step_id)
                if step_state and step_state.status == "pending":
                    candidates.append(snapshot)

        if not candidates:
            # 退而求其次，找最近的能用于重新执行的快照
            for snapshot_id in reversed(self.trace_snapshots[trace_id]):
                snapshot = self.snapshots.get(snapshot_id)
                if snapshot and target_step_id not in snapshot.completed_steps:
                    candidates.append(snapshot)
                    break

        if not candidates:
            logger.warning(f"[快照] 未找到适合回溯到步骤 {target_step_id} 的快照")
            return None

        # 返回最接近目标的快照
        best_snapshot = max(candidates, key=lambda s: s.timestamp)
        logger.info(
            f"[快照] 找到回溯快照 {best_snapshot.snapshot_id} "
            f"(target_step={target_step_id})"
        )
        return best_snapshot

    def restore_from_snapshot(
        self,
        snapshot: ExecutionSnapshot
    ) -> Tuple[Dict[str, Any], Dict[int, Dict], Dict[int, int]]:
        """
        从快照恢复状态

        Args:
            snapshot: 要恢复的快照

        Returns:
            Tuple[context, step_states, in_degrees]: 恢复后的状态
        """
        logger.info(f"[快照] 恢复快照 {snapshot.snapshot_id} (step={snapshot.step_id})")

        # 恢复上下文
        restored_context = copy.deepcopy(snapshot.global_context)

        # 恢复步骤状态
        restored_step_states = {
            sid: {
                "status": state.status,
                "result": copy.deepcopy(state.result),
                "retry_count": state.retry_count,
                "error_history": list(state.error_history),
                "start_time": state.start_time,
                "end_time": state.end_time
            }
            for sid, state in snapshot.step_states.items()
        }

        # 恢复入度
        restored_in_degrees = copy.deepcopy(snapshot.in_degrees)

        return restored_context, restored_step_states, restored_in_degrees

    def get_snapshot_history(self, trace_id: str) -> List[Dict]:
        """
        获取指定trace的快照历史（用于调试和监控）

        Returns:
            List[Dict]: 快照摘要列表
        """
        if trace_id not in self.trace_snapshots:
            return []

        history = []
        for snapshot_id in self.trace_snapshots[trace_id]:
            snapshot = self.snapshots.get(snapshot_id)
            if snapshot:
                history.append({
                    "snapshot_id": snapshot_id,
                    "timestamp": snapshot.timestamp.isoformat(),
                    "step_id": snapshot.step_id,
                    "completed_steps": snapshot.completed_steps,
                    "pending_steps": snapshot.pending_steps
                })

        return history

    def _cleanup_old_snapshots(self, trace_id: str):
        """清理过多的快照，保留最近的"""
        if trace_id not in self.trace_snapshots:
            return

        snapshot_ids = self.trace_snapshots[trace_id]
        if len(snapshot_ids) <= self.max_snapshots_per_trace:
            return

        # 删除最旧的快照
        to_remove = len(snapshot_ids) - self.max_snapshots_per_trace
        for snapshot_id in snapshot_ids[:to_remove]:
            if snapshot_id in self.snapshots:
                del self.snapshots[snapshot_id]

        self.trace_snapshots[trace_id] = snapshot_ids[to_remove:]
        logger.debug(f"[快照] 清理了 {to_remove} 个旧快照 (trace={trace_id})")

    def clear_trace_snapshots(self, trace_id: str):
        """清除指定trace的所有快照"""
        if trace_id not in self.trace_snapshots:
            return

        for snapshot_id in self.trace_snapshots[trace_id]:
            if snapshot_id in self.snapshots:
                del self.snapshots[snapshot_id]

        del self.trace_snapshots[trace_id]
        logger.info(f"[快照] 清除trace {trace_id} 的所有快照")

    def get_stats(self) -> Dict:
        """获取快照管理器统计信息"""
        return {
            "total_snapshots": len(self.snapshots),
            "total_traces": len(self.trace_snapshots),
            "snapshots_per_trace": {
                trace_id: len(ids)
                for trace_id, ids in self.trace_snapshots.items()
            }
        }
