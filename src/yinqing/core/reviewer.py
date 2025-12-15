"""
审核层 (Reviewer Layer)
负责对Agent执行结果进行质量审核，并提供回溯建议
"""

import json
from typing import Dict, Any, Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from yinqing.utils.logger import get_logger
from yinqing.utils.config import get_mcp_server_config

logger = get_logger(__name__)


# ==================== 数据模型 ====================

class RollbackAction(BaseModel):
    """回溯动作"""
    action_type: Literal["retry", "revert", "human_intervention"] = Field(
        description="回溯类型: retry-重试当前步骤, revert-回退到前置步骤, human_intervention-需要人工介入"
    )
    target_step_id: int = Field(description="目标步骤ID")
    reason: str = Field(description="回溯原因")
    modified_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="修改后的上下文（如有改进建议）"
    )
    max_retries: int = Field(default=3, description="最大重试次数")


class ReviewResult(BaseModel):
    """审核结果"""
    step_id: int = Field(description="被审核的步骤ID")
    passed: bool = Field(description="是否通过审核")
    score: float = Field(ge=0, le=1, description="质量评分 0-1")
    issues: List[str] = Field(default_factory=list, description="发现的问题列表")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")
    rollback_recommendation: Optional[RollbackAction] = Field(
        default=None,
        description="回溯建议（仅当未通过时）"
    )
    review_time: datetime = Field(default_factory=datetime.now, description="审核时间")
    reviewer: str = Field(default="QualityReviewerAgent", description="审核者")


class ReviewConfig(BaseModel):
    """审核配置"""
    enabled: bool = Field(default=True, description="是否启用审核")
    review_all_steps: bool = Field(default=False, description="是否审核所有步骤")
    review_final_only: bool = Field(default=True, description="只审核最终结果")
    critical_steps: List[int] = Field(default_factory=list, description="关键步骤列表（必须审核）")
    quality_threshold: float = Field(default=0.7, ge=0, le=1, description="质量阈值")
    max_retries: int = Field(default=3, ge=1, description="最大重试次数")
    enable_rollback: bool = Field(default=True, description="是否启用回溯")
    auto_retry_on_fail: bool = Field(default=True, description="审核失败时自动重试")


# ==================== 审核层实现 ====================

class ReviewerLayer:
    """
    审核层 - 负责质量检查和回溯建议

    职责:
    1. 对Agent执行结果进行质量评估
    2. 检查结果的完整性、准确性
    3. 提供具体的改进建议
    4. 必要时建议回溯到之前的步骤
    """

    def __init__(self, config: ReviewConfig = None):
        self.config = config or ReviewConfig()
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0.1  # 低温度确保审核一致性
        )

        self.review_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一位严格且专业的质量审核专家。你的职责是评估任务执行结果的质量。

## 评分标准 (0-1分):
- 0.9-1.0: 优秀 - 完全满足要求，质量上乘
- 0.7-0.9: 良好 - 基本满足要求，小问题可接受
- 0.5-0.7: 一般 - 部分满足要求，需要改进
- 0.3-0.5: 较差 - 未能满足要求，需要重做
- 0.0-0.3: 不合格 - 严重问题，需要人工介入

## 审核维度:
1. 完整性: 结果是否覆盖了任务描述的所有要求
2. 准确性: 内容是否正确、无明显错误
3. 质量: 表达是否清晰、逻辑是否连贯
4. 可用性: 结果是否可以直接使用或作为下一步的输入

请严格按照JSON格式返回审核结果。"""),
            ("user", """## 审核请求

### 任务描述
{task_description}

### 执行结果
{result}

### 相关上下文
{context}

请对以上执行结果进行审核，返回JSON格式:
{{
    "passed": true/false,
    "score": 0.0-1.0,
    "issues": ["问题1", "问题2"],
    "suggestions": ["建议1", "建议2"]
}}""")
        ])

        self.parser = JsonOutputParser()
        self.chain = self.review_prompt | self.llm | self.parser

    async def review_step(
        self,
        step_id: int,
        task_description: str,
        result: str,
        context: Dict[str, Any],
        dependencies: List[int] = None
    ) -> ReviewResult:
        """
        审核单个步骤的执行结果

        Args:
            step_id: 步骤ID
            task_description: 任务描述
            result: 执行结果
            context: 上下文信息
            dependencies: 依赖的步骤ID列表

        Returns:
            ReviewResult: 审核结果
        """
        logger.info(f"[审核] 开始审核步骤 {step_id}: {task_description[:50]}...")

        try:
            # 调用LLM进行审核
            llm_result = await self.chain.ainvoke({
                "task_description": task_description,
                "result": result,
                "context": json.dumps(context, ensure_ascii=False, indent=2)
            })

            # 构造审核结果
            review_result = ReviewResult(
                step_id=step_id,
                passed=llm_result.get("passed", True),
                score=float(llm_result.get("score", 0.7)),
                issues=llm_result.get("issues", []),
                suggestions=llm_result.get("suggestions", [])
            )

            # 根据配置的阈值判断是否通过
            review_result.passed = review_result.score >= self.config.quality_threshold

            # 如果不通过，生成回溯建议
            if not review_result.passed:
                review_result.rollback_recommendation = self._generate_rollback_action(
                    step_id=step_id,
                    score=review_result.score,
                    issues=review_result.issues,
                    dependencies=dependencies or []
                )
                logger.warning(
                    f"[审核] 步骤 {step_id} 未通过审核 "
                    f"(score={review_result.score:.2f}, threshold={self.config.quality_threshold})"
                )
            else:
                logger.info(f"[审核] 步骤 {step_id} 通过审核 (score={review_result.score:.2f})")

            return review_result

        except Exception as e:
            logger.error(f"[审核] 步骤 {step_id} 审核失败: {e}")
            # 审核失败时默认通过，避免阻塞流程
            return ReviewResult(
                step_id=step_id,
                passed=True,
                score=0.7,
                issues=[f"审核过程发生错误: {str(e)}"],
                suggestions=["建议人工检查此步骤结果"]
            )

    def _generate_rollback_action(
        self,
        step_id: int,
        score: float,
        issues: List[str],
        dependencies: List[int]
    ) -> RollbackAction:
        """
        根据审核结果生成回溯动作建议

        策略:
        - score >= 0.5: 重试当前步骤
        - 0.3 <= score < 0.5: 如果有依赖，回退到最近的依赖步骤
        - score < 0.3: 需要人工介入
        """

        if score >= 0.5:
            # 质量一般，重试当前步骤应该能解决
            return RollbackAction(
                action_type="retry",
                target_step_id=step_id,
                reason=f"质量评分{score:.2f}未达标，问题: {'; '.join(issues[:2])}",
                max_retries=self.config.max_retries
            )

        elif score >= 0.3 and dependencies:
            # 质量较差，可能需要回退到前置步骤
            return RollbackAction(
                action_type="revert",
                target_step_id=dependencies[-1],  # 回退到最近的依赖
                reason=f"结果质量较差(score={score:.2f})，可能是前置步骤输出不佳，建议回退重新执行",
                max_retries=self.config.max_retries
            )

        else:
            # 质量很差，需要人工介入
            return RollbackAction(
                action_type="human_intervention",
                target_step_id=step_id,
                reason=f"执行结果严重不合格(score={score:.2f})，问题: {'; '.join(issues)}，需要人工检查"
            )

    async def review_final_result(
        self,
        goal: str,
        all_results: Dict[int, str],
        step_names: Dict[int, str]
    ) -> ReviewResult:
        """
        对整个执行流程的最终结果进行综合审核

        Args:
            goal: 原始任务目标
            all_results: 所有步骤的执行结果 {step_id: result}
            step_names: 步骤名称映射 {step_id: name}

        Returns:
            ReviewResult: 综合审核结果
        """
        logger.info("[审核] 开始最终综合审核...")

        # 构造综合结果文本
        combined_result = "\n\n".join([
            f"### 步骤{sid}: {step_names.get(sid, 'Unknown')}\n{result}"
            for sid, result in sorted(all_results.items())
        ])

        return await self.review_step(
            step_id=0,  # 使用0表示最终审核
            task_description=f"完成目标: {goal}",
            result=combined_result,
            context={"goal": goal, "total_steps": len(all_results)}
        )

    def should_review_step(self, step_id: int, is_final: bool = False) -> bool:
        """
        判断是否需要审核某个步骤

        Args:
            step_id: 步骤ID
            is_final: 是否是最终步骤

        Returns:
            bool: 是否需要审核
        """
        if not self.config.enabled:
            return False

        if self.config.review_all_steps:
            return True

        if step_id in self.config.critical_steps:
            return True

        if is_final and self.config.review_final_only:
            return True

        return False
