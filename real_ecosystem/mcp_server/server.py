import os
import json
import uvicorn
from mcp.server.fastmcp import FastMCP

# ==========================================
# MCP Server Implementation (Port 10000)
# ==========================================
mcp = FastMCP("Real Agent Registry")

def normalize_card_fields(card: dict) -> dict:
    """
    将card字段从camelCase转换为snake_case以匹配AgentCard模型
    """
    normalized = card.copy()
    
    # 字段名映射
    field_mapping = {
        "defaultInputModes": "default_input_modes",
        "defaultOutputModes": "default_output_modes",
        "pushNotifications": "push_notifications",
        "stateTransitionHistory": "state_transition_history"
    }
    
    # 转换顶层字段
    for old_name, new_name in field_mapping.items():
        if old_name in normalized:
            normalized[new_name] = normalized.pop(old_name)
    
    # 转换capabilities中的字段
    if "capabilities" in normalized and isinstance(normalized["capabilities"], dict):
        caps = normalized["capabilities"]
        for old_name, new_name in field_mapping.items():
            if old_name in caps:
                caps[new_name] = caps.pop(old_name)
    
    return normalized

@mcp.tool()
def find_agent(query: str) -> str:
    """Finds an agent based on a natural language query."""
    print(f"🔎 [Real MCP Server] Received find_agent query: {query}")
    query_lower = query.lower()
    
    # Load all cards from real_ecosystem/cards
    cards_dir = os.path.join(os.path.dirname(__file__), "../cards")
    matched_card = None
    
    # Simple keyword matching logic
    best_score = 0
    
    if not os.path.exists(cards_dir):
        print(f"❌ [Real MCP Server] Cards directory not found: {cards_dir}")
        # 返回默认的Researcher Agent（完整结构，使用snake_case）
        default_card = {
            "name": "Researcher Agent",
            "description": "由Gemini驱动的智能研究助手",
            "version": "2.0.0",
            "url": "http://localhost:10001",
            "capabilities": {
                "streaming": True,
                "pushNotifications": True,
                "stateTransitionHistory": False
            },
            "default_input_modes": ["text", "text/plain"],
            "default_output_modes": ["text", "text/plain"],
            "skills": [
                {
                    "id": "research",
                    "name": "研究调查",
                    "description": "对给定主题进行全面研究",
                    "tags": ["research", "analysis", "研究", "调查"],
                    "examples": ["研究任何主题"]
                }
            ]
        }
        return json.dumps(default_card, ensure_ascii=False)

    for filename in os.listdir(cards_dir):
        if filename.endswith(".json"):
            try:
                with open(os.path.join(cards_dir, filename), "r", encoding="utf-8") as f:
                    card = json.load(f)
                    score = 0
                    
                    # Construct searchable text from name, description, capabilities, and skills
                    searchable_parts = [
                        card.get("name", ""),
                        card.get("description", ""),
                        " ".join(card.get("capabilities", {}).keys())
                    ]
                    
                    # Add skills info
                    for skill in card.get("skills", []):
                        searchable_parts.append(skill.get("name", ""))
                        searchable_parts.append(skill.get("description", ""))
                        searchable_parts.extend(skill.get("tags", []))
                    
                    # 支持中文搜索：不转小写，直接匹配
                    text = " ".join(searchable_parts)
                    text_lower = text.lower()
                    
                    # 中文关键词匹配（不分词，直接子串匹配）
                    # 检查整个查询是否在文本中
                    if query in text or query_lower in text_lower:
                        score += 10  # 完整匹配得高分
                    
                    # 分词匹配（支持中英文）
                    keywords = query.split()
                    for kw in keywords:
                        kw_lower = kw.lower()
                        # 中文或英文关键词匹配
                        if kw in text or kw_lower in text_lower:
                            score += 2
                    
                    # 特殊关键词加权
                    keyword_mapping = {
                        "研究": ["researcher", "research", "调查", "信息"],
                        "写": ["writer", "write", "创作", "文章", "内容"],
                        "代码": ["coder", "code", "编程", "程序"],
                        "分析": ["analyst", "analyze", "数据", "统计"],
                        "审核": ["reviewer", "review", "检查", "质量"],
                        "翻译": ["translator", "translate", "语言"],
                    }
                    
                    for cn_key, related_words in keyword_mapping.items():
                        if cn_key in query:
                            for word in related_words:
                                if word in text_lower:
                                    score += 3
                    
                    if score > best_score:
                        best_score = score
                        matched_card = card
            except Exception as e:
                print(f"⚠️ Error reading card {filename}: {e}")

    if matched_card:
        print(f"✅ [Real MCP Server] Matched: {matched_card['name']} (score: {best_score})")
        # 转换字段名从camelCase到snake_case
        normalized_card = normalize_card_fields(matched_card)
        return json.dumps(normalized_card, ensure_ascii=False)
    
    # 如果没有匹配，返回默认的Researcher Agent（最通用）
    print(f"❌ [Real MCP Server] No match found, returning default Researcher Agent")
    default_card = {
        "name": "Researcher Agent",
        "description": "由Gemini驱动的智能研究助手",
        "version": "2.0.0",
        "url": "http://localhost:10001",
        "capabilities": {
            "streaming": True,
            "pushNotifications": True,
            "stateTransitionHistory": False
        },
        "default_input_modes": ["text", "text/plain"],
        "default_output_modes": ["text", "text/plain"],
        "skills": [
            {
                "id": "research",
                "name": "研究调查",
                "description": "对给定主题进行全面研究",
                "tags": ["research", "analysis", "研究", "调查", "分析"],
                "examples": ["研究任何主题", "分析信息", "收集数据"]
            }
        ]
    }
    return json.dumps(default_card, ensure_ascii=False)

def run_mcp():
    print("🚀 Starting Real MCP Server on port 10000 (SSE)...")
    app = mcp.sse_app()
    uvicorn.run(app, host="0.0.0.0", port=10000)

if __name__ == "__main__":
    run_mcp()
