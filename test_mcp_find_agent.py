#!/usr/bin/env python3
"""
测试MCP Server的find_agent功能
"""
import asyncio
import sys
sys.path.insert(0, 'src')

from yinqing.core.mcp_client import init_session, find_agent
from yinqing.utils.config import get_mcp_server_config

async def test_find_agent():
    """测试find_agent工具"""
    config = get_mcp_server_config()
    
    print("=" * 70)
    print("测试 MCP Server find_agent 功能")
    print("=" * 70)
    print(f"MCP Server: {config.host}:{config.port}")
    print()
    
    # 测试查询列表
    test_queries = [
        "研究好莱坞的历史",
        "写一篇文章",
        "编写Python代码",
        "分析销售数据",
        "审核代码质量",
        "翻译这段文字",
        "收集信息",
        "生成报告",
    ]
    
    try:
        async with init_session(config.host, config.port, config.transport) as session:
            for i, query in enumerate(test_queries, 1):
                print(f"{i}. 查询: '{query}'")
                try:
                    result = await find_agent(session, query)
                    if result and result.content:
                        text = result.content[0].text
                        
                        # 尝试解析JSON
                        import json
                        try:
                            agent_data = json.loads(text)
                            agent_name = agent_data.get("name", "Unknown")
                            agent_desc = agent_data.get("description", "")
                            print(f"   ✅ 匹配到: {agent_name}")
                            print(f"   描述: {agent_desc[:60]}...")
                        except json.JSONDecodeError as e:
                            print(f"   ❌ JSON解析失败: {e}")
                            print(f"   响应: {text[:100]}")
                    else:
                        print(f"   ❌ 无响应")
                except Exception as e:
                    print(f"   ❌ 错误: {e}")
                print()
                
    except Exception as e:
        print(f"❌ 连接MCP Server失败: {e}")
        print()
        print("请确保MCP Server正在运行:")
        print("  ./start_real_agents.sh")
        return False
    
    print("=" * 70)
    print("测试完成")
    print("=" * 70)
    return True

if __name__ == "__main__":
    asyncio.run(test_find_agent())
