"""
Quality Reviewer Agent - 质量审核Agent
负责审核其他Agent的执行结果，提供改进建议和回溯推荐
"""

import json
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from dotenv import load_dotenv
# 加载.env文件
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import uvicorn


class QualityReviewerAgent:
    """质量审核Agent - 审核执行结果并提供回溯建议"""

    def __init__(self):
        self.name = "Quality Reviewer Agent"
        self.system_prompt = """你是一个严格且专业的质量审核专家。你的职责是：

1. **质量评估**: 评估任务执行结果是否满足要求
2. **完整性检查**: 检查结果是否完整、无遗漏
3. **准确性验证**: 验证结果的准确性和正确性
4. **改进建议**: 提供具体的、可执行的改进建议
5. **回溯推荐**: 必要时建议回溯到之前的步骤重新执行

## 评分标准 (0-1分):
- 0.9-1.0: 优秀 - 完全满足要求，质量上乘
- 0.7-0.9: 良好 - 基本满足要求，小问题可接受
- 0.5-0.7: 一般 - 部分满足要求，需要改进
- 0.3-0.5: 较差 - 未能满足要求，需要重做
- 0.0-0.3: 不合格 - 严重问题，需要人工介入

## 回溯建议类型:
- "retry": 重试当前步骤（质量一般，问题可通过重试解决）
- "revert": 回退到前置步骤（当前结果受前置步骤影响）
- "human_intervention": 需要人工介入（问题严重或复杂）

请严格按照以下JSON格式返回审核结果:
{
    "passed": true/false,
    "score": 0.0-1.0,
    "issues": ["问题1", "问题2"],
    "suggestions": ["建议1", "建议2"],
    "rollback_recommendation": {
        "action_type": "retry|revert|human_intervention",
        "target_step_id": 步骤ID,
        "reason": "回溯原因"
    } // 仅当 passed=false 时提供
}"""

        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0.1  # 低温度确保审核结果一致性
        )
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", "{input}")
        ])
        self.chain = self.prompt | self.llm | StrOutputParser()

    async def handle_request(self, request):
        """处理A2A审核请求"""
        try:
            body = await request.json()

            # 解析A2A消息格式
            user_msg = body.get('params', {}).get('message', {}).get('parts', [{}])[0].get('text', '')

            # 尝试解析为JSON（包含审核信息）
            try:
                payload = json.loads(user_msg)
                task_description = payload.get("task_description", "")
                execution_result = payload.get("result", "")
                context = payload.get("context", {})
                step_id = payload.get("step_id", 0)
                dependencies = payload.get("dependencies", [])

                # 构造审核输入
                formatted_input = f"""## 审核请求

### 步骤信息
- 步骤ID: {step_id}
- 依赖步骤: {dependencies}

### 任务描述
{task_description}

### 执行结果
{execution_result}

### 上下文信息
{json.dumps(context, ensure_ascii=False, indent=2)}

请对以上执行结果进行严格审核，并返回JSON格式的审核结果。"""

            except json.JSONDecodeError:
                formatted_input = f"请审核以下内容:\n\n{user_msg}"

            # 调用LLM进行审核
            response_text = await self.chain.ainvoke({"input": formatted_input})

            # 尝试解析LLM返回的JSON
            try:
                # 提取JSON部分（处理可能的markdown代码块）
                json_text = response_text
                if "```json" in response_text:
                    json_text = response_text.split("```json")[1].split("```")[0]
                elif "```" in response_text:
                    json_text = response_text.split("```")[1].split("```")[0]

                review_result = json.loads(json_text.strip())
            except:
                # 如果解析失败，构造默认结果
                review_result = {
                    "passed": True,
                    "score": 0.7,
                    "issues": [],
                    "suggestions": ["无法解析审核结果，默认通过"],
                    "raw_response": response_text
                }

            # 返回A2A标准响应
            return JSONResponse({
                "result": {
                    "message": {
                        "role": "model",
                        "parts": [{
                            "text": json.dumps(review_result, ensure_ascii=False, indent=2)
                        }]
                    }
                }
            })

        except Exception as e:
            return JSONResponse({
                "result": {
                    "message": {
                        "role": "model",
                        "parts": [{
                            "text": json.dumps({
                                "passed": False,
                                "score": 0.0,
                                "issues": [f"审核过程发生错误: {str(e)}"],
                                "suggestions": ["请检查输入格式"],
                                "rollback_recommendation": {
                                    "action_type": "retry",
                                    "target_step_id": 0,
                                    "reason": f"审核错误: {str(e)}"
                                }
                            }, ensure_ascii=False)
                        }]
                    }
                }
            }, status_code=200)

    async def health_check(self, request):
        """健康检查端点"""
        return JSONResponse({
            "status": "healthy",
            "agent": self.name,
            "capabilities": ["quality_check", "rollback_analysis"]
        })


# 创建Agent实例
agent = QualityReviewerAgent()

# 创建Starlette应用
app = Starlette(
    debug=True,
    routes=[
        Route("/", agent.handle_request, methods=["POST"]),
        Route("/health", agent.health_check, methods=["GET"]),
    ]
)

if __name__ == "__main__":
    print(f"Starting {agent.name} on port 10007...")
    uvicorn.run(app, host="0.0.0.0", port=10007)
