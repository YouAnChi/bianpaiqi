import os
import asyncio
import traceback
from typing import Dict, List, Any, Optional
from collections import deque
from yinqing.core.types import ExecutionPlan, TaskStep, ParallelConfig, generate_trace_id
from yinqing.core.parser import TaskParserLayer
from yinqing.core.matcher import CapabilityMatcherLayer
from yinqing.core.executor import TaskExecutorLayer
from yinqing.utils.logger import get_logger

logger = get_logger(__name__)

class WorkflowEngine:
    """项目经理：支持并行执行和依赖处理的通用编排器"""
    
    def __init__(self):
        self.parser = TaskParserLayer()
        self.matcher = CapabilityMatcherLayer()
        self.executor = TaskExecutorLayer()
        self.global_context_store: Dict[str, Dict[str, Any]] = {}
        self.step_status_store: Dict[str, Dict[int, TaskStep]] = {}
        self.parallel_config = ParallelConfig(fail_strategy="continue", max_parallel=5)
        
        # Current context (runtime)
        self.global_context = {}
        
        # 输出目录
        self.output_dir = os.path.join(os.getcwd(), "output")
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def format_response(self, content: str, is_complete: bool = False):
        return {"content": content, "is_complete": is_complete}

    def _save_result_to_file(self, query: str, result: str, trace_id: str, plan: ExecutionPlan = None):
        """将最终结果保存到文件，根据执行的Agent类型智能选择格式"""
        try:
            # 清理文件名中的非法字符
            safe_query = "".join([c for c in query if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_')
            
            # 检测是否有Excel或Word生成步骤
            has_excel = False
            has_word = False
            saved_files = []
            
            if plan:
                for step in plan.steps:
                    if step.status == "success" and step.assigned_agent:
                        agent_name = step.assigned_agent.name.lower()
                        if "excel" in agent_name:
                            has_excel = True
                        if "word" in agent_name:
                            has_word = True
            
            # 默认保存Markdown文件
            md_filename = f"{safe_query}_{trace_id[:8]}.md"
            md_filepath = os.path.join(self.output_dir, md_filename)
            
            with open(md_filepath, "w", encoding="utf-8") as f:
                f.write(f"# Task: {query}\n\n")
                f.write(f"Trace ID: {trace_id}\n")
                f.write(f"Date: {asyncio.get_event_loop().time()}\n\n")
                f.write("---\n\n")
                f.write(result)
            
            saved_files.append(md_filepath)
            logger.info(f"✅ Markdown result saved to {md_filepath}")
            
            # 如果检测到Excel或Word生成，添加提示信息
            if has_excel or has_word:
                file_types = []
                if has_excel:
                    file_types.append("Excel (.xlsx)")
                if has_word:
                    file_types.append("Word (.docx)")
                logger.info(f"📊 检测到生成了 {', '.join(file_types)} 文件，请查看output目录")
            
            return ", ".join(saved_files) if len(saved_files) > 1 else saved_files[0]
        except Exception as e:
            logger.error(f"Failed to save result to file: {e}")
            return None

    async def _execute_parallel_steps(self, steps: List[TaskStep], context: Dict[str, Any], trace_id: str):
        """并行执行多个步骤，返回执行结果"""
        # 构建并行任务列表
        tasks = []
        for step in steps:
            if step.status == "pending":
                tasks.append(self.executor.execute_step(step, context, trace_id))
        
        if not tasks:
            return []

        # 控制最大并行数
        if len(tasks) > self.parallel_config.max_parallel:
            chunks = [tasks[i:i+self.parallel_config.max_parallel] for i in range(0, len(tasks), self.parallel_config.max_parallel)]
            all_results = []
            for chunk in chunks:
                chunk_results = await asyncio.gather(*chunk, return_exceptions=self.parallel_config.fail_strategy == "continue")
                all_results.extend(chunk_results)
        else:
            # 执行并行任务，return_exceptions=True表示某个任务失败不影响其他任务
            all_results = await asyncio.gather(*tasks, return_exceptions=self.parallel_config.fail_strategy == "continue")
        return all_results

    async def stream(self, query: str, context_id: str = None, task_id: str = None):
        """主入口流式函数（支持并行与依赖）"""
        trace_id = generate_trace_id()
        logger.info(f"[bold magenta]🚀 Workflow Started[/bold magenta] (Query: '{query}')")
        yield self.format_response(f"收到任务：{query}，正在分析... (trace_id: {trace_id})", is_complete=False)

        try:
            # 初始化上下文和状态
            if trace_id in self.global_context_store:
                self.global_context = self.global_context_store[trace_id]
                saved_steps = self.step_status_store[trace_id]
                logger.info(f"🔄 Resuming workflow from breakpoint (trace_id: {trace_id})")
                yield self.format_response(f"发现断点，将从上次中断处继续执行... (trace_id: {trace_id})", is_complete=False)
            else:
                self.global_context = {"user_query": query, "trace_id": trace_id}
                saved_steps = {}

            # Phase 1: 解析与DAG初始化
            plan = await self.parser.parse(query, context_id, task_id)
            self.global_context["trace_id"] = plan.trace_id
            yield self.format_response(f"计划生成完毕，共 {len(plan.steps)} 个步骤。", is_complete=False)

            # Phase 2: 匹配Agent
            plan = await self.matcher.match_agents(plan)
            yield self.format_response("资源调度完毕，Agent 匹配完成。", is_complete=False)

            # 合并保存的步骤状态
            for step_id, saved_step in saved_steps.items():
                if step_id in plan.step_map:
                    plan.step_map[step_id] = saved_step

            # Phase 3: 拓扑排序 + 并行执行
            queue = deque()
            for step in plan.steps:
                if step.in_degree == 0 and step.status == "pending":
                    queue.append(step.step_id)

            logger.info("[bold yellow]⚡️ Starting Execution Phase[/bold yellow]")

            while queue:
                # 取出当前所有入度为0的步骤（可并行执行）
                current_parallel_steps = [plan.step_map[step_id] for step_id in queue]
                queue.clear()

                if not current_parallel_steps:
                    break

                # 输出并行执行提示
                step_ids = [step.step_id for step in current_parallel_steps]
                step_names = [step.name for step in current_parallel_steps]
                logger.info(f"▶️  Executing Batch: Steps {step_ids} ({', '.join(step_names)})")
                yield self.format_response(f"正在执行步骤：{', '.join(step_names)}...", is_complete=False)

                # 并行执行步骤
                results = await self._execute_parallel_steps(current_parallel_steps, self.global_context, plan.trace_id)

                # 处理执行结果
                for result in results:
                    if isinstance(result, Exception):
                        # 处理任务执行异常
                        logger.error(f"❌ Step execution failed: {result}")
                        yield self.format_response(f"步骤执行异常：{str(result)[:100]}...", is_complete=False)
                        continue
                    
                    step, result_str = result # type: ignore
                    # 更新上下文和状态
                    self.global_context[f"step_{step.step_id}_output"] = result_str
                    self.step_status_store[plan.trace_id] = self.step_status_store.get(plan.trace_id, {})
                    self.step_status_store[plan.trace_id][step.step_id] = step

                    # 输出步骤结果
                    preview = result_str[:100] + "..." if len(str(result_str)) > 100 else result_str
                    status_icon = "✅" if step.status == "success" else "❌"
                    logger.info(f"  {status_icon} Step {step.step_id} finished: {preview}")
                    yield self.format_response(f"步骤 {step.step_id} {step.status}。输出: {preview}", is_complete=False)

                    # 更新后继步骤的入度
                    for succ_id in step.successors:
                        succ_step = plan.step_map[succ_id]
                        succ_step.in_degree -= 1
                        # 入度为0则加入队列（后续可执行）
                        if succ_step.in_degree == 0 and succ_step.status == "pending":
                            queue.append(succ_id)

            # 汇总最终结果并保存
            final_output = []
            for step in plan.steps:
                if step.status == "success":
                    final_output.append(f"## Step {step.step_id}: {step.name}\n\n{step.result}\n")
            
            full_result_text = "\n".join(final_output)
            saved_path = self._save_result_to_file(query, full_result_text, plan.trace_id, plan)

            # 保存上下文
            self.global_context_store[plan.trace_id] = self.global_context
            logger.info(f"[bold green]🏁 Workflow Completed Successfully![/bold green] (trace_id: {plan.trace_id})")
            
            completion_msg = f"✅ 所有任务步骤执行完毕！"
            if saved_path:
                completion_msg += f"\n📄 结果已保存至: {saved_path}"
                
            yield self.format_response(completion_msg, is_complete=True)

        except Exception as e:
            logger.error(f"Workflow crashed (trace_id: {trace_id}): {traceback.format_exc()}")
            yield self.format_response(f"Workflow Critical Error: {e} (trace_id: {trace_id})")
