from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from yinqing.core.types import ExecutionPlan
from yinqing.utils.logger import get_logger

logger = get_logger(__name__)

class TaskParserLayer:
    """大脑：负责将自然语言拆解为结构化步骤（支持并行依赖）"""
    
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.1)
        self.parser = JsonOutputParser(pydantic_object=ExecutionPlan)
        
        # 优化Prompt：明确支持并行依赖，并智能拆分内容创作和文件生成
        self.prompt = ChatPromptTemplate.from_template(
            """
            你是一位资深系统架构师，擅长AI智能体编排和并行任务调度。
            用户目标: {query}
            
            你的任务是将这个目标拆解为**支持并行执行的逻辑子任务列表（步骤）**。
            每个步骤必须：
            1. 是一个单一的、可执行的任务，可以由专业的AI智能体完成（例如："生成结构化的演示大纲"、"收集AI趋势数据"、"为幻灯片编写内容"）。
            2. 有清晰、简洁的描述，便于智能体发现（避免模糊的语言）。
            3. 列出它依赖的上下文键（例如：["step_1_output", "step_2_output"] 表示需要步骤1和步骤2的结果）。
            4. 列出依赖项（此步骤依赖的步骤ID；如果没有则使用空列表）。没有依赖项的步骤可以并行执行。
            5. 分配唯一的、从1开始的连续步骤ID（例如：1, 2, 3...）。
            
            并行性的重要规则：
            - 将独立的任务拆分为可以并行运行的单独步骤（例如："生成大纲"和"收集数据"是独立的，所以它们应该是步骤1和步骤2，没有依赖关系）。
            - 保持步骤数量合理（大多数目标3-10个步骤）。
            - 确保没有循环依赖（例如：步骤1依赖步骤2，步骤2依赖步骤1）。
            
            **文件生成的特殊规则（重要）：**
            如果用户要求生成Excel或Word文件，必须遵循以下模式：
            1. 先创建"收集/研究/撰写内容"的步骤（由Researcher/Writer Agent完成）
            2. 再创建"生成Excel文件"或"生成Word文档"的步骤（由Excel/Word Generator Agent完成）
            3. 文件生成步骤必须依赖内容创作步骤
            
            示例：
            用户输入："我想要一个关于广州天河区介绍的Word文档和经济数据的Excel文件"
            正确拆解：
            - Step 1: 收集广州天河区的介绍信息（地理、历史、文化等）
            - Step 2: 收集广州天河区的经济数据（GDP、产业、人口等）
            - Step 3: 生成Word文档（依赖Step 1）
            - Step 4: 生成Excel文件（依赖Step 2）
            
            关键词识别：
            - "Excel文件"、"Excel表格"、"xlsx" → 需要"生成Excel文件"步骤
            - "Word文档"、"Word文件"、"docx" → 需要"生成Word文档"步骤
            - 这些步骤的描述必须明确包含"生成Excel文件"或"生成Word文档"字样
            
            {format_instructions}
            """
        )
        self.chain = self.prompt | self.llm | self.parser

    async def parse(self, query: str, context_id: str, task_id: str) -> ExecutionPlan:
        logger.info(f"🧠 [Parser] Analyzing query: {query}")
        try:
            response = await self.chain.ainvoke({
                "query": query,
                "format_instructions": self.parser.get_format_instructions()
            })
            plan = ExecutionPlan(**response)
            plan.task_id = task_id
            plan.context_id = context_id
            # 修复LLM生成的重复step_id
            step_ids = [step.step_id for step in plan.steps]
            if len(step_ids) != len(set(step_ids)):
                for idx, step in enumerate(plan.steps):
                    step.step_id = idx + 1
            # 初始化DAG
            plan.init_dag()
            # 检测循环依赖
            if plan.check_cycle():
                raise ValueError("Execution plan contains circular dependencies!")
            
            # 详细日志输出
            logger.info(f"[bold green]🧠 [Parser] Plan Generated[/bold green] (trace_id: {plan.trace_id}):")
            for step in plan.steps:
                dep_str = f"depends on {step.dependencies}" if step.dependencies else "no dependencies"
                logger.info(f"  Step {step.step_id}: [bold]{step.name}[/bold] - {step.description} ([italic]{dep_str}[/italic])")
            
            return plan
        except Exception as e:
            logger.error(f"Parser failed: {e}")
            raise
