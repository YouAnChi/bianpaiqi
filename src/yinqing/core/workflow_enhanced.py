"""
增强版工作流引擎 (Enhanced Workflow Engine)
支持审核Agent和流程回溯功能
"""

import os
import asyncio
import traceback
from typing import Dict, List, Any, Optional, Tuple
from collections import deque
from datetime import datetime

from yinqing.core.types import ExecutionPlan, TaskStep, ParallelConfig, generate_trace_id
from yinqing.core.parser import TaskParserLayer
from yinqing.core.matcher import CapabilityMatcherLayer
from yinqing.core.executor import TaskExecutorLayer
from yinqing.core.reviewer import ReviewerLayer, ReviewConfig, ReviewResult
from yinqing.core.snapshot import SnapshotManager, ExecutionSnapshot
from yinqing.utils.logger import get_logger

logger = get_logger(__name__)


class EnhancedWorkflowEngine:
    """
    增强版工作流引擎

    新增功能:
    1. 审核层 (ReviewerLayer) - 对执行结果进行质量审核
    2. 快照管理 (SnapshotManager) - 支持状态快照和流程回溯
    3. 智能重试 - 根据审核结果自动重试或回溯
    4. 人工介入接口 - 支持暂停等待人工处理
    """

    def __init__(self, review_config: ReviewConfig = None):
        """
        初始化增强版工作流引擎

        Args:
            review_config: 审核配置，None则使用默认配置
        """
        # 核心组件
        self.parser = TaskParserLayer()
        self.matcher = CapabilityMatcherLayer()
        self.executor = TaskExecutorLayer()

        # 新增：审核层和快照管理器
        self.review_config = review_config or ReviewConfig()
        self.reviewer = ReviewerLayer(config=self.review_config)
        self.snapshot_manager = SnapshotManager()

        # 状态存储
        self.global_context_store: Dict[str, Dict[str, Any]] = {}
        self.step_status_store: Dict[str, Dict[int, TaskStep]] = {}
        self.parallel_config = ParallelConfig(fail_strategy="continue", max_parallel=5)

        # 运行时上下文
        self.global_context: Dict[str, Any] = {}

        # 重试计数器 {trace_id: {step_id: retry_count}}
        self.retry_counters: Dict[str, Dict[int, int]] = {}

        # 输出目录
        self.output_dir = os.path.join(os.getcwd(), "output")
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def format_response(
        self,
        content: str,
        is_complete: bool = False,
        phase: str = "progress",
        **kwargs
    ) -> Dict[str, Any]:
        """格式化响应消息"""
        response = {
            "content": content,
            "is_complete": is_complete,
            "phase": phase,
            "timestamp": datetime.now().isoformat()
        }
        response.update(kwargs)
        return response

    def _save_result_to_file(self, query: str, result: str, trace_id: str) -> Optional[str]:
        """将最终结果保存到文件"""
        try:
            safe_query = "".join(
                [c for c in query if c.isalnum() or c in (' ', '-', '_')]
            ).strip().replace(' ', '_')[:50]
            filename = f"{safe_query}_{trace_id[:8]}.md"
            filepath = os.path.join(self.output_dir, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# Task: {query}\n\n")
                f.write(f"Trace ID: {trace_id}\n")
                f.write(f"Date: {datetime.now().isoformat()}\n\n")
                f.write("---\n\n")
                f.write(result)

            logger.info(f"[bold green]Result saved to {filepath}[/bold green]")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save result to file: {e}")
            return None

    def _get_step_states_dict(self, plan: ExecutionPlan) -> Dict[int, Dict]:
        """获取所有步骤状态的字典形式"""
        return {
            step.step_id: {
                "status": step.status,
                "result": step.result,
                "retry_count": self.retry_counters.get(plan.trace_id, {}).get(step.step_id, 0),
                "error_history": getattr(step, 'error_history', []),
                "start_time": step.start_time,
                "end_time": step.end_time
            }
            for step in plan.steps
        }

    def _get_in_degrees_dict(self, plan: ExecutionPlan) -> Dict[int, int]:
        """获取所有步骤入度的字典"""
        return {step.step_id: step.in_degree for step in plan.steps}

    async def _create_snapshot(self, plan: ExecutionPlan, step_id: int):
        """创建执行快照"""
        if not self.review_config.enable_rollback:
            return

        self.snapshot_manager.create_snapshot(
            trace_id=plan.trace_id,
            step_id=step_id,
            context=self.global_context,
            step_states=self._get_step_states_dict(plan),
            in_degrees=self._get_in_degrees_dict(plan)
        )

    async def _restore_from_snapshot(
        self,
        plan: ExecutionPlan,
        snapshot: ExecutionSnapshot
    ) -> ExecutionPlan:
        """从快照恢复状态"""
        restored_context, restored_states, restored_in_degrees = \
            self.snapshot_manager.restore_from_snapshot(snapshot)

        # 恢复上下文
        self.global_context = restored_context

        # 恢复步骤状态
        for step in plan.steps:
            state = restored_states.get(step.step_id)
            if state:
                step.status = state.get("status", "pending")
                step.result = state.get("result")
                step.in_degree = restored_in_degrees.get(step.step_id, step.in_degree)

        return plan

    async def _execute_parallel_steps(
        self,
        steps: List[TaskStep],
        context: Dict[str, Any],
        trace_id: str
    ) -> List[Tuple[TaskStep, str]]:
        """并行执行多个步骤"""
        tasks = []
        for step in steps:
            if step.status == "pending":
                tasks.append(self.executor.execute_step(step, context, trace_id))

        if not tasks:
            return []

        # 控制最大并行数
        if len(tasks) > self.parallel_config.max_parallel:
            chunks = [
                tasks[i:i + self.parallel_config.max_parallel]
                for i in range(0, len(tasks), self.parallel_config.max_parallel)
            ]
            all_results = []
            for chunk in chunks:
                chunk_results = await asyncio.gather(
                    *chunk,
                    return_exceptions=self.parallel_config.fail_strategy == "continue"
                )
                all_results.extend(chunk_results)
        else:
            all_results = await asyncio.gather(
                *tasks,
                return_exceptions=self.parallel_config.fail_strategy == "continue"
            )

        return all_results

    async def _execute_step_with_review(
        self,
        step: TaskStep,
        plan: ExecutionPlan,
    ) -> Tuple[TaskStep, str, Optional[ReviewResult]]:
        """
        执行单个步骤并进行审核

        Returns:
            Tuple[step, result, review_result]
        """
        trace_id = plan.trace_id

        # 初始化重试计数
        if trace_id not in self.retry_counters:
            self.retry_counters[trace_id] = {}
        if step.step_id not in self.retry_counters[trace_id]:
            self.retry_counters[trace_id][step.step_id] = 0

        max_retries = self.review_config.max_retries
        review_result = None

        while self.retry_counters[trace_id][step.step_id] < max_retries:
            # 创建执行前快照
            await self._create_snapshot(plan, step.step_id)

            # 执行步骤
            step, result = await self.executor.execute_step(
                step, self.global_context, trace_id
            )

            if step.status == "failed":
                self.retry_counters[trace_id][step.step_id] += 1
                logger.warning(
                    f"[重试] Step {step.step_id} 执行失败，重试 "
                    f"{self.retry_counters[trace_id][step.step_id]}/{max_retries}"
                )
                step.status = "pending"  # 重置状态以便重试
                continue

            # 检查是否需要审核
            is_final = all(
                s.status in ("success", "failed")
                for s in plan.steps
                if s.step_id != step.step_id
            )
            should_review = self.reviewer.should_review_step(step.step_id, is_final)

            if should_review:
                logger.info(f"[审核] 开始审核 Step {step.step_id}")
                review_result = await self.reviewer.review_step(
                    step_id=step.step_id,
                    task_description=step.description,
                    result=result,
                    context=self.global_context,
                    dependencies=step.dependencies
                )

                if not review_result.passed:
                    # 审核未通过
                    self.retry_counters[trace_id][step.step_id] += 1
                    logger.warning(
                        f"[审核] Step {step.step_id} 审核未通过 "
                        f"(score={review_result.score:.2f}), "
                        f"重试 {self.retry_counters[trace_id][step.step_id]}/{max_retries}"
                    )

                    # 将审核建议加入上下文
                    if review_result.suggestions:
                        self.global_context["_review_suggestions"] = review_result.suggestions

                    # 检查是否需要回溯
                    if (review_result.rollback_recommendation and
                            review_result.rollback_recommendation.action_type == "revert"):
                        return step, result, review_result

                    step.status = "pending"
                    continue

            # 执行成功且审核通过（或无需审核）
            return step, result, review_result

        # 超过最大重试次数
        step.status = "failed"
        step.error = f"超过最大重试次数({max_retries})"
        return step, "", review_result

    async def _handle_rollback(
        self,
        step: TaskStep,
        plan: ExecutionPlan,
        review_result: ReviewResult
    ) -> Tuple[bool, Optional[int]]:
        """
        处理回溯逻辑

        Returns:
            Tuple[should_continue, rollback_target_step_id]
        """
        if not review_result or not review_result.rollback_recommendation:
            return False, None

        action = review_result.rollback_recommendation

        if action.action_type == "revert":
            # 尝试回溯
            snapshot = self.snapshot_manager.get_rollback_snapshot(
                plan.trace_id, action.target_step_id
            )
            if snapshot:
                logger.info(
                    f"[回溯] 回溯到 Step {action.target_step_id} "
                    f"(原因: {action.reason})"
                )
                await self._restore_from_snapshot(plan, snapshot)
                return True, action.target_step_id
            else:
                logger.warning(f"[回溯] 未找到可用快照，无法回溯到 Step {action.target_step_id}")

        elif action.action_type == "human_intervention":
            logger.warning(f"[人工介入] Step {step.step_id} 需要人工处理: {action.reason}")
            # 这里可以实现暂停等待机制
            return False, None

        return False, None

    async def stream(
        self,
        query: str,
        context_id: str = None,
        task_id: str = None,
        review_config: ReviewConfig = None
    ):
        """
        主入口流式函数 - 支持审核和回溯

        Args:
            query: 用户查询
            context_id: 上下文ID
            task_id: 任务ID
            review_config: 审核配置（覆盖默认配置）
        """
        # 更新审核配置
        if review_config:
            self.review_config = review_config
            self.reviewer = ReviewerLayer(config=review_config)

        trace_id = generate_trace_id()
        logger.info(f"[bold magenta]Workflow Started[/bold magenta] (Query: '{query}')")
        yield self.format_response(
            f"收到任务：{query}，正在分析... (trace_id: {trace_id})",
            phase="start",
            trace_id=trace_id
        )

        try:
            # 初始化上下文
            self.global_context = {"user_query": query, "trace_id": trace_id}

            # ========== Phase 1: 任务解析 ==========
            yield self.format_response("Phase 1: 解析任务...", phase="parsing")
            plan = await self.parser.parse(query, context_id, task_id)
            self.global_context["trace_id"] = plan.trace_id

            yield self.format_response(
                f"任务已拆解为 {len(plan.steps)} 个步骤",
                phase="parsing",
                steps=[{
                    "step_id": s.step_id,
                    "name": s.name,
                    "dependencies": s.dependencies
                } for s in plan.steps]
            )

            # ========== Phase 2: Agent匹配 ==========
            yield self.format_response("Phase 2: 匹配Agent...", phase="matching")
            plan = await self.matcher.match_agents(plan)

            yield self.format_response(
                "Agent匹配完成",
                phase="matching",
                assignments=[{
                    "step_id": s.step_id,
                    "agent": getattr(s.assigned_agent, 'name', 'Unknown') if s.assigned_agent else None
                } for s in plan.steps]
            )

            # ========== Phase 3: DAG并行执行（带审核） ==========
            yield self.format_response(
                "Phase 3: 开始执行...",
                phase="execution",
                review_enabled=self.review_config.enabled
            )

            queue = deque()
            for step in plan.steps:
                if step.in_degree == 0 and step.status == "pending":
                    queue.append(step.step_id)

            logger.info("[bold yellow]Starting Execution Phase[/bold yellow]")

            while queue:
                current_step_ids = list(queue)
                queue.clear()

                current_steps = [plan.step_map[sid] for sid in current_step_ids]

                # 输出当前批次信息
                step_names = [s.name for s in current_steps]
                logger.info(f"Executing Batch: Steps {current_step_ids} ({', '.join(step_names)})")
                yield self.format_response(
                    f"正在执行: {', '.join(step_names)}",
                    phase="execution",
                    batch_steps=current_step_ids
                )

                # 逐个执行（带审核，不完全并行以支持精确的审核和回溯）
                for step in current_steps:
                    # 创建快照
                    await self._create_snapshot(plan, step.step_id)

                    # 执行并审核
                    step, result, review = await self._execute_step_with_review(step, plan)

                    if step.status == "failed":
                        # 检查是否需要回溯
                        if review and review.rollback_recommendation:
                            should_rollback, target_id = await self._handle_rollback(
                                step, plan, review
                            )
                            if should_rollback and target_id:
                                # 回溯后重新加入队列
                                queue.append(target_id)
                                yield self.format_response(
                                    f"回溯到 Step {target_id}，重新执行",
                                    phase="rollback",
                                    rollback_target=target_id
                                )
                                continue

                        # 无法恢复的失败
                        yield self.format_response(
                            f"Step {step.step_id} 执行失败: {step.error}",
                            phase="error",
                            step_id=step.step_id,
                            error=step.error
                        )
                        continue

                    # 成功：更新上下文
                    self.global_context[f"step_{step.step_id}_output"] = result

                    # 输出结果
                    preview = result[:150] + "..." if len(result) > 150 else result
                    review_info = ""
                    if review:
                        review_info = f" [审核: {'通过' if review.passed else '未通过'}, 分数: {review.score:.2f}]"

                    yield self.format_response(
                        f"Step {step.step_id} ({step.name}) 完成{review_info}",
                        phase="step_complete",
                        step_id=step.step_id,
                        step_name=step.name,
                        result_preview=preview,
                        review_score=review.score if review else None,
                        review_passed=review.passed if review else None
                    )

                    # 更新后继步骤入度
                    for succ_id in step.successors:
                        succ_step = plan.step_map[succ_id]
                        succ_step.in_degree -= 1
                        if succ_step.in_degree == 0 and succ_step.status == "pending":
                            queue.append(succ_id)

            # ========== Phase 4: 最终审核（可选） ==========
            if self.review_config.review_final_only and self.review_config.enabled:
                yield self.format_response("Phase 4: 最终审核...", phase="final_review")

                all_results = {
                    s.step_id: s.result
                    for s in plan.steps if s.status == "success" and s.result
                }
                step_names = {s.step_id: s.name for s in plan.steps}

                final_review = await self.reviewer.review_final_result(
                    goal=plan.goal,
                    all_results=all_results,
                    step_names=step_names
                )

                yield self.format_response(
                    f"最终审核{'通过' if final_review.passed else '未通过'} "
                    f"(分数: {final_review.score:.2f})",
                    phase="final_review",
                    review_passed=final_review.passed,
                    review_score=final_review.score,
                    issues=final_review.issues,
                    suggestions=final_review.suggestions
                )

            # ========== Phase 5: 结果汇总 ==========
            final_output = []
            for step in plan.steps:
                if step.status == "success":
                    final_output.append(f"## Step {step.step_id}: {step.name}\n\n{step.result}\n")

            full_result_text = "\n".join(final_output)
            saved_path = self._save_result_to_file(query, full_result_text, plan.trace_id)

            # 保存上下文
            self.global_context_store[plan.trace_id] = self.global_context

            # 清理快照
            self.snapshot_manager.clear_trace_snapshots(plan.trace_id)

            logger.info(f"[bold green]Workflow Completed![/bold green] (trace_id: {plan.trace_id})")

            completion_msg = "所有任务步骤执行完毕！"
            if saved_path:
                completion_msg += f"\n结果已保存至: {saved_path}"

            yield self.format_response(
                completion_msg,
                is_complete=True,
                phase="complete",
                trace_id=plan.trace_id,
                saved_path=saved_path,
                total_steps=len(plan.steps),
                successful_steps=len([s for s in plan.steps if s.status == "success"])
            )

        except Exception as e:
            logger.error(f"Workflow crashed (trace_id: {trace_id}): {traceback.format_exc()}")
            yield self.format_response(
                f"Workflow Critical Error: {e}",
                phase="error",
                trace_id=trace_id,
                error=str(e),
                traceback=traceback.format_exc()
            )

    async def run(
        self,
        query: str,
        review_config: ReviewConfig = None
    ) -> Dict[str, Any]:
        """
        同步风格的运行方法（等待完成后返回完整结果）
        """
        results = []
        async for response in self.stream(query, review_config=review_config):
            results.append(response)

        return {
            "trace_id": results[-1].get("trace_id") if results else None,
            "responses": results,
            "final_response": results[-1] if results else None
        }


# ==================== 便捷函数 ====================

def create_review_config(
    enabled: bool = True,
    review_all: bool = False,
    review_final: bool = True,
    critical_steps: List[int] = None,
    threshold: float = 0.7,
    max_retries: int = 3,
    enable_rollback: bool = True
) -> ReviewConfig:
    """创建审核配置的便捷函数"""
    return ReviewConfig(
        enabled=enabled,
        review_all_steps=review_all,
        review_final_only=review_final,
        critical_steps=critical_steps or [],
        quality_threshold=threshold,
        max_retries=max_retries,
        enable_rollback=enable_rollback
    )


# ==================== 使用示例 ====================

async def example_usage():
    """使用示例"""
    # 创建审核配置
    config = create_review_config(
        enabled=True,
        review_all=False,       # 不审核所有步骤
        review_final=True,      # 审核最终结果
        critical_steps=[],      # 无特定关键步骤
        threshold=0.7,          # 质量阈值0.7
        max_retries=3,          # 最大重试3次
        enable_rollback=True    # 启用回溯
    )

    # 创建增强版引擎
    engine = EnhancedWorkflowEngine(review_config=config)

    # 执行任务
    async for response in engine.stream(
        "分析Python、Java和Go的优缺点，并写一份对比报告"
    ):
        print(f"[{response['phase']}] {response['content']}")

        if response.get('review_score'):
            print(f"  审核分数: {response['review_score']:.2f}")


if __name__ == "__main__":
    asyncio.run(example_usage())
