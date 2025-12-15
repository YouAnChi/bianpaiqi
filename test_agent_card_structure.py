#!/usr/bin/env python3
"""
测试AgentCard的结构要求
"""
from a2a.types import AgentCard
import json

# 测试最小结构
minimal_card = {
    "name": "Test Agent",
    "description": "测试Agent",
    "url": "http://localhost:10001"
}

print("=" * 70)
print("测试 AgentCard 结构")
print("=" * 70)
print()

print("1. 测试最小结构:")
print(json.dumps(minimal_card, indent=2, ensure_ascii=False))
print()

try:
    agent = AgentCard(**minimal_card)
    print("✅ 最小结构可以工作")
    print(f"   Agent: {agent.name}")
except Exception as e:
    print(f"❌ 最小结构失败: {e}")
    print()
    print("需要的字段:")
    # 尝试查看AgentCard的字段
    try:
        from pydantic import BaseModel
        if hasattr(AgentCard, 'model_fields'):
            print("  必需字段:")
            for field_name, field_info in AgentCard.model_fields.items():
                required = field_info.is_required()
                print(f"    - {field_name}: {'必需' if required else '可选'}")
    except:
        pass

print()
print("=" * 70)

# 测试完整结构
full_card = {
    "name": "Test Agent",
    "description": "测试Agent",
    "version": "1.0.0",
    "url": "http://localhost:10001",
    "capabilities": {
        "streaming": True,
        "pushNotifications": True,
        "stateTransitionHistory": False
    },
    "defaultInputModes": ["text", "text/plain"],
    "defaultOutputModes": ["text", "text/plain"],
    "skills": [
        {
            "id": "test",
            "name": "测试",
            "description": "测试技能",
            "tags": ["test"],
            "examples": ["测试"]
        }
    ]
}

print("2. 测试完整结构:")
try:
    agent = AgentCard(**full_card)
    print("✅ 完整结构可以工作")
    print(f"   Agent: {agent.name}")
    print(f"   Version: {agent.version}")
    print(f"   Skills: {len(agent.skills)}")
except Exception as e:
    print(f"❌ 完整结构失败: {e}")

print()
print("=" * 70)
