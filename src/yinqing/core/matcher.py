import json
import asyncio
from datetime import datetime
from typing import Dict, Tuple, Optional, List
from yinqing.core.types import ExecutionPlan, AgentCard
from yinqing.core.mcp_client import init_session, find_agent, list_all_agents
from yinqing.utils.config import get_mcp_server_config
from yinqing.utils.logger import get_logger
from yinqing.utils.common import RETRY_TIMES, RETRY_DELAY, AGENT_CACHE_TTL, clean_response_str
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

logger = get_logger(__name__)

class CapabilityMatcherLayer:
    """猎头：负责根据步骤描述去 MCP 市场寻找合适的 Agent（增强版：使用LLM辅助匹配）"""
    
    def __init__(self):
        self.config = get_mcp_server_config()
        self.agent_cache: Dict[str, Tuple[AgentCard, datetime]] = {}
        
        # 新增：LLM辅助匹配
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.1)
        self.match_prompt = ChatPromptTemplate.from_template(
            """你是一位专业的Agent匹配专家。

任务描述: {task_description}

可用的Agent列表:
{agents_info}

请分析任务描述，选择最合适的Agent。注意：
1. 如果任务明确要求生成Excel文件，必须选择"Excel Generator Agent"
2. 如果任务明确要求生成Word文档，必须选择"Word Generator Agent"
3. 如果任务需要研究/收集信息，选择"Researcher Agent"
4. 如果任务需要写作/创作内容，选择"Writer Agent"
5. 如果任务需要数据分析，选择"Data Analyst Agent"
6. 如果任务需要编程，选择"Coder Agent"

返回JSON格式:
{{
    "selected_agent": "Agent名称",
    "reason": "选择理由"
}}
"""
        )
        self.match_chain = self.match_prompt | self.llm | JsonOutputParser()

    def _get_cached_agent(self, description: str) -> Optional[AgentCard]:
        if description in self.agent_cache:
            agent_card, expire_time = self.agent_cache[description]
            if datetime.now() < expire_time:
                return agent_card
            else:
                del self.agent_cache[description]
        return None

    def _set_cached_agent(self, description: str, agent_card: AgentCard):
        expire_time = datetime.now() + AGENT_CACHE_TTL
        self.agent_cache[description] = (agent_card, expire_time)

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

    async def _find_agent_wrapper(self, session, description: str) -> Optional[AgentCard]:
        """使用MCP Server的find_agent工具查找Agent"""
        result = await find_agent(session, description)
        if result and result.content:
            text = result.content[0].text
            cleaned_text = clean_response_str(text)
            
            # 检查是否为空响应
            if not cleaned_text or cleaned_text.strip() == "":
                logger.warning(f"Empty response from find_agent for: {description[:50]}")
                return None
            
            try:
                agent_card_json = json.loads(cleaned_text)
                agent_card = AgentCard(**agent_card_json)
                self._set_cached_agent(description, agent_card)
                return agent_card
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse agent card JSON: {e}. Text: {cleaned_text[:100]}")
                return None
        return None
    
    async def _get_all_agents(self, session) -> List[Dict]:
        """获取所有可用的Agent信息"""
        try:
            result = await list_all_agents(session)
            if result and result.content:
                text = result.content[0].text
                cleaned_text = clean_response_str(text)
                agents = json.loads(cleaned_text)
                return agents if isinstance(agents, list) else []
        except Exception as e:
            logger.warning(f"Failed to get all agents: {e}")
        return []
    
    async def _llm_match_agent(self, session, description: str, all_agents: List[Dict]) -> Optional[AgentCard]:
        """使用LLM智能匹配Agent"""
        try:
            # 构建Agent信息摘要
            agents_info = []
            for agent in all_agents:
                agent_summary = f"- {agent.get('name', 'Unknown')}: {agent.get('description', '')}"
                skills = agent.get('skills', [])
                if skills:
                    tags = []
                    for skill in skills:
                        tags.extend(skill.get('tags', []))
                    agent_summary += f" (关键词: {', '.join(tags[:5])})"
                agents_info.append(agent_summary)
            
            agents_text = "\n".join(agents_info)
            
            # 调用LLM进行匹配
            logger.info(f"🤖 Using LLM to match agent for: {description[:50]}...")
            match_result = await self.match_chain.ainvoke({
                "task_description": description,
                "agents_info": agents_text
            })
            
            selected_name = match_result.get("selected_agent", "")
            reason = match_result.get("reason", "")
            
            logger.info(f"🎯 LLM selected: {selected_name} (Reason: {reason})")
            
            # 根据名称找到对应的Agent卡片
            for agent in all_agents:
                if agent.get('name') == selected_name:
                    agent_card = AgentCard(**agent)
                    self._set_cached_agent(description, agent_card)
                    return agent_card
            
            logger.warning(f"LLM selected agent '{selected_name}' not found in agent list")
            return None
            
        except Exception as e:
            logger.error(f"LLM matching failed: {e}")
            return None

    async def match_agents(self, plan: ExecutionPlan, use_llm: bool = True) -> ExecutionPlan:
        """
        匹配Agent（增强版）
        
        Args:
            plan: 执行计划
            use_llm: 是否使用LLM辅助匹配（默认True）
        """
        logger.info(f"[bold blue]🔍 [Matcher] Starting agent discovery (LLM: {use_llm})[/bold blue] (trace_id: {plan.trace_id})...")
        
        try:
            async with init_session(self.config.host, self.config.port, self.config.transport) as session:
                # 如果使用LLM，先获取所有Agent列表
                all_agents = []
                if use_llm:
                    all_agents = await self._get_all_agents(session)
                    logger.info(f"📋 Loaded {len(all_agents)} agents for LLM matching")
                
                for step in plan.steps:
                    logger.info(f"  Step {step.step_id}: Searching for agent suitable for '[italic]{step.description}[/italic]'")
                    
                    # 检查缓存
                    agent_card = self._get_cached_agent(step.description)
                    if agent_card:
                        step.assigned_agent = agent_card
                        agent_id = getattr(step.assigned_agent, 'id', getattr(step.assigned_agent, 'name', 'Unknown'))
                        logger.info(f"    ✅ [green]Cached Match:[/green] {step.assigned_agent.name} (ID: {agent_id})")
                        continue
                    
                    try:
                        # 优先使用LLM匹配
                        if use_llm and all_agents:
                            agent_card = await self._llm_match_agent(session, step.description, all_agents)
                        
                        # 如果LLM匹配失败，回退到传统匹配
                        if not agent_card:
                            logger.info(f"    🔄 Falling back to traditional matching...")
                            agent_card = await self._retry_async(self._find_agent_wrapper, session, step.description)
                        
                        if agent_card:
                            step.assigned_agent = agent_card
                            agent_id = getattr(step.assigned_agent, 'id', getattr(step.assigned_agent, 'name', 'Unknown'))
                            logger.info(f"    ✅ [green]Found:[/green] {step.assigned_agent.name} (ID: {agent_id})")
                        else:
                            logger.warning(f"    ❌ [red]No agent found[/red]")
                    except Exception as e:
                        logger.error(f"    ⚠️ Error finding agent for step {step.step_id}: {e}")
        except Exception as e:
            import traceback
            logger.error(f"Failed to initialize MCP session: {e}")
            logger.error(traceback.format_exc())
                    
        return plan
