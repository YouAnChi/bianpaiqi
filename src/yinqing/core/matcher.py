import json
import asyncio
from datetime import datetime
from typing import Dict, Tuple, Optional
from yinqing.core.types import ExecutionPlan, AgentCard
from yinqing.core.mcp_client import init_session, find_agent
from yinqing.utils.config import get_mcp_server_config
from yinqing.utils.logger import get_logger
from yinqing.utils.common import RETRY_TIMES, RETRY_DELAY, AGENT_CACHE_TTL, clean_response_str

logger = get_logger(__name__)

class CapabilityMatcherLayer:
    """猎头：负责根据步骤描述去 MCP 市场寻找合适的 Agent"""
    
    def __init__(self):
        self.config = get_mcp_server_config()
        self.agent_cache: Dict[str, Tuple[AgentCard, datetime]] = {}

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

    async def match_agents(self, plan: ExecutionPlan) -> ExecutionPlan:
        logger.info(f"[bold blue]🔍 [Matcher] Starting agent discovery[/bold blue] (trace_id: {plan.trace_id})...")
        
        try:
            async with init_session(self.config.host, self.config.port, self.config.transport) as session:
                for step in plan.steps:
                    logger.info(f"  Step {step.step_id}: Searching for agent suitable for '[italic]{step.description}[/italic]'")
                    agent_card = self._get_cached_agent(step.description)
                    if agent_card:
                        step.assigned_agent = agent_card
                        # 尝试安全获取 ID，如果不存在则使用 name 或 "Unknown"
                        agent_id = getattr(step.assigned_agent, 'id', getattr(step.assigned_agent, 'name', 'Unknown'))
                        logger.info(f"    ✅ [green]Cached Match:[/green] {step.assigned_agent.name} (ID: {agent_id})")
                        continue
                    try:
                        agent_card = await self._retry_async(self._find_agent_wrapper, session, step.description)
                        if agent_card:
                            step.assigned_agent = agent_card
                            # 尝试安全获取 ID，如果不存在则使用 name 或 "Unknown"
                            agent_id = getattr(step.assigned_agent, 'id', getattr(step.assigned_agent, 'name', 'Unknown'))
                            logger.info(f"    ✅ [green]Found:[/green] {step.assigned_agent.name} (ID: {agent_id})")
                        else:
                            logger.warning(f"    ❌ [red]No agent found[/red]")
                    except Exception as e:
                        logger.error(f"    ⚠️ Error finding agent for step {step.step_id}: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize MCP session: {e}")
            # Consider whether to fail hard or soft here. For now, we log and return plan (steps might be unassigned)
                    
        return plan
