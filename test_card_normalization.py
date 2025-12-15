#!/usr/bin/env python3
"""
测试card字段名转换
"""
import json
from a2a.types import AgentCard

# 模拟normalize_card_fields函数
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

# 测试
print("=" * 70)
print("测试 Card 字段名转换")
print("=" * 70)
print()

# 读取实际的card文件
with open("real_ecosystem/cards/researcher.json", "r", encoding="utf-8") as f:
    original_card = json.load(f)

print("1. 原始card (camelCase):")
print(f"   defaultInputModes: {original_card.get('defaultInputModes')}")
print(f"   defaultOutputModes: {original_card.get('defaultOutputModes')}")
print()

# 转换
normalized_card = normalize_card_fields(original_card)

print("2. 转换后的card (snake_case):")
print(f"   default_input_modes: {normalized_card.get('default_input_modes')}")
print(f"   default_output_modes: {normalized_card.get('default_output_modes')}")
print()

# 验证是否可以创建AgentCard
print("3. 验证AgentCard创建:")
try:
    agent = AgentCard(**normalized_card)
    print(f"   ✅ 成功创建 AgentCard")
    print(f"   Agent: {agent.name}")
    print(f"   Version: {agent.version}")
    print(f"   Skills: {len(agent.skills)}")
except Exception as e:
    print(f"   ❌ 失败: {e}")

print()
print("=" * 70)
