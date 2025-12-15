import json
import uuid
import asyncio
import httpx
from typing import Tuple, Dict, Any
from datetime import datetime
from a2a.client import A2AClient
from a2a.types import SendMessageRequest, MessageSendParams, Message, Role, TextPart, Task
from yinqing.core.types import TaskStep
from yinqing.utils.logger import get_logger
from yinqing.utils.common import RETRY_TIMES, RETRY_DELAY, clean_response_str

logger = get_logger(__name__)

class TaskExecutorLayer:
    """工头：负责最底层的 A2A 调用、重试和脏数据清洗"""
    
    async def _retry_async(self, func, *args, **kwargs):
        for attempt in range(RETRY_TIMES):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt == RETRY_TIMES - 1:
                    raise e
                logger.warning(f"Attempt {attempt+1} failed: {e}, retrying in {RETRY_DELAY}s...")
                await asyncio.sleep(RETRY_DELAY)
        return None

    async def execute_step(self, step: TaskStep, context: Dict[str, Any], trace_id: str) -> Tuple[TaskStep, str]:
        """执行单个步骤，返回步骤对象和结果"""
        step.status = "running"
        step.start_time = datetime.now()
        
        # 详细日志：开始执行
        logger.info(f"  [cyan]Step {step.step_id} Started[/cyan]: Invoking Agent '{step.assigned_agent.name if step.assigned_agent else 'None'}'")
        
        if not step.assigned_agent:
            step.status = "failed"
            step.error = "No agent assigned"
            step.end_time = datetime.now()
            logger.error(f"  [red]Step {step.step_id} Failed[/red]: No agent assigned")
            return step, "Error: No agent assigned to this step."

        # 筛选上下文
        filtered_context = {}
        for key in step.context_keys:
            if key in context:
                filtered_context[key] = context[key]
            else:
                logger.warning(f"  ⚠️ Context key '{key}' not found for step {step.step_id}")
        
        payload = {
            "task_description": step.description,
            "context": filtered_context
        }
        query_str = json.dumps(payload)

        async def _call_agent():
            # 优先尝试从 config 获取 URL
            target_url = None
            
            # 安全地访问 config 属性
            agent_config = getattr(step.assigned_agent, 'config', {})
            if agent_config and 'http_url' in agent_config:
                target_url = agent_config['http_url']
            
            # 尝试从 url 属性获取 (直接属性)
            if not target_url and hasattr(step.assigned_agent, 'url'):
                 target_url = step.assigned_agent.url
                 
            # 如果 config 中没有，尝试解析 interaction_endpoints (如果存在)
            if not target_url and hasattr(step.assigned_agent, 'interaction_endpoints'):
                # 假设 interaction_endpoints 是个列表，取第一个
                endpoints = step.assigned_agent.interaction_endpoints
                if endpoints:
                    target_url = endpoints[0].get('url') if isinstance(endpoints[0], dict) else getattr(endpoints[0], 'url', None)

            if not target_url:
                # 最后的尝试：有些 AgentCard 可能把 url 直接放在根级别，但通过 dict 访问
                if hasattr(step.assigned_agent, 'dict'):
                    agent_dict = step.assigned_agent.dict()
                    target_url = agent_dict.get('url')
                elif isinstance(step.assigned_agent, dict):
                    target_url = step.assigned_agent.get('url')

            if not target_url:
                raise ValueError(f"Could not find HTTP URL for agent {step.assigned_agent.name}. Card data: {step.assigned_agent}")

            # 直接构造 A2A 协议的 JSON Payload
            msg_id = str(uuid.uuid4())
            raw_payload = {
                "id": msg_id,
                "method": "sendMessage", # A2A 标准方法名，虽然这里我们只关心 body
                "params": {
                    "message": {
                        "messageId": msg_id,
                        "role": "user",
                        "parts": [{"text": query_str}]
                    }
                }
            }
            
            # 使用 httpx 直接发送请求，绕过 a2a 库的严格 Pydantic 校验
            async with httpx.AsyncClient(timeout=60.0) as client:
                # logger.info(f"  [Executor] POST {target_url}")
                response = await client.post(target_url, json=raw_payload)
                response.raise_for_status()
                response_json = response.json()
                
                # 手动解析响应，提取 text
                # 预期结构: {"result": {"message": {"parts": [{"text": "..."}]}}}
                try:
                    result = response_json.get("result", {})
                    message = result.get("message", {})
                    parts = message.get("parts", [])
                    if parts and isinstance(parts, list):
                        text = parts[0].get("text", "")
                        return clean_response_str(text)
                    
                    # 备用路径：直接看有没有 text 字段
                    if "text" in result:
                        return clean_response_str(result["text"])
                        
                    return clean_response_str(str(response_json))
                    
                except Exception as e:
                    logger.warning(f"Failed to parse agent response structure: {e}. Raw: {str(response_json)[:100]}")
                    return clean_response_str(str(response_json))

        try:
            result = await self._retry_async(_call_agent)
            step.status = "success" if not result.startswith("Error") else "failed"
            step.result = result
            step.error = result if result.startswith("Error") else None
            
            # 日志：执行结果
            if step.status == "success":
                # logger.info(f"  [green]Step {step.step_id} Success[/green]")
                pass
            else:
                logger.error(f"  [red]Step {step.step_id} Failed[/red]: {step.error}")

        except Exception as e:
            result = f"Execution Error: {e}"
            step.status = "failed"
            step.result = result
            step.error = str(e)
            logger.error(f"  [red]Step {step.step_id} Exception[/red]: {e}")
            
        step.end_time = datetime.now()
        return step, result

    def _extract_text(self, response) -> str:
        """清洗提取逻辑"""
        try:
            if hasattr(response, 'root') and hasattr(response.root, 'result'):
                result = response.root.result
                # Artifacts倒序
                if isinstance(result, Task) or (hasattr(result, 'artifacts') and result.artifacts):
                    if result.artifacts:
                        for artifact in reversed(result.artifacts):
                            if artifact.parts:
                                part = artifact.parts[0]
                                text = getattr(part.root, 'text', getattr(part, 'text', ""))
                                if text:
                                    return clean_response_str(text)
                # Status message
                if hasattr(result, 'status') and result.status and result.status.message and result.status.message.parts:
                    part = result.status.message.parts[0]
                    text = getattr(part.root, 'text', getattr(part, 'text', ""))
                    if text:
                        return clean_response_str(text)
                # Message
                if isinstance(result, Message) and result.parts:
                    part = result.parts[0]
                    text = getattr(part.root, 'text', getattr(part, 'text', ""))
                    if text:
                        return clean_response_str(text)
            return clean_response_str(str(response))
        except Exception as e:
            logger.error(f"Error extracting text from response: {e}")
            return clean_response_str(str(response))
