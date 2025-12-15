# MCP Agent 匹配问题修复指南

## 🐛 问题描述

错误信息：`Expecting value: line 1 column 1 (char 0)`

**原因**：
1. MCP Server在没有匹配到Agent时返回空字符串
2. 客户端尝试将空字符串解析为JSON导致错误
3. 中文关键词匹配不够准确

## ✅ 已修复的内容

### 1. MCP Server (`real_ecosystem/mcp_server/server.py`)

**改进**：
- ✅ 永远返回有效的JSON（即使没有匹配）
- ✅ 改进中文关键词匹配算法
- ✅ 添加关键词映射和加权
- ✅ 使用UTF-8编码读取card文件
- ✅ 没有匹配时返回默认的Researcher Agent

**关键改进**：
```python
# 改进前：返回空字符串
if matched_card:
    return json.dumps(matched_card)
return ""  # ❌ 会导致JSON解析错误

# 改进后：总是返回有效JSON
if matched_card:
    return json.dumps(matched_card, ensure_ascii=False)
# 返回默认Agent
default_card = {
    "name": "Researcher Agent",
    "description": "由Gemini驱动的智能研究助手",
    "url": "http://localhost:10001"
}
return json.dumps(default_card, ensure_ascii=False)  # ✅
```

**中文匹配改进**：
```python
# 1. 完整查询匹配（高分）
if query in text or query_lower in text_lower:
    score += 10

# 2. 关键词映射
keyword_mapping = {
    "研究": ["researcher", "research", "调查", "信息"],
    "写": ["writer", "write", "创作", "文章", "内容"],
    "代码": ["coder", "code", "编程", "程序"],
    "分析": ["analyst", "analyze", "数据", "统计"],
    "审核": ["reviewer", "review", "检查", "质量"],
    "翻译": ["translator", "translate", "语言"],
}
```

### 2. Matcher Layer (`src/yinqing/core/matcher.py`)

**改进**：
- ✅ 添加空响应检查
- ✅ 改进JSON解析错误处理
- ✅ 添加详细的错误日志

**关键改进**：
```python
# 检查空响应
if not cleaned_text or cleaned_text.strip() == "":
    logger.warning(f"Empty response from find_agent")
    return None

# 安全的JSON解析
try:
    agent_card_json = json.loads(cleaned_text)
    agent_card = AgentCard(**agent_card_json)
    return agent_card
except json.JSONDecodeError as e:
    logger.error(f"Failed to parse agent card JSON: {e}")
    return None
```

## 🚀 应用修复

### 1. 重启MCP Server

修改后需要重启MCP Server：

```bash
# 停止所有服务
pkill -f "real_ecosystem"

# 重新启动
./start_real_agents.sh
```

### 2. 测试修复

运行测试脚本验证修复：

```bash
python3 test_mcp_find_agent.py
```

**预期输出**：
```
1. 查询: '研究好莱坞的历史'
   ✅ 匹配到: Researcher Agent
   描述: 由Gemini驱动的智能研究助手...

2. 查询: '写一篇文章'
   ✅ 匹配到: Writer Agent
   描述: 由Gemini驱动的创意作家...

3. 查询: '编写Python代码'
   ✅ 匹配到: Coder Agent
   描述: 由Gemini驱动的软件工程师智能体...
```

### 3. 运行完整工作流

```bash
./run_enhanced.sh
```

输入测试任务：
```
请输入任务: 好莱坞的发展历程
```

## 📊 匹配算法说明

### 评分机制

| 匹配类型 | 得分 | 说明 |
|---------|------|------|
| 完整查询匹配 | +10 | 整个查询在Agent描述中 |
| 关键词映射匹配 | +3 | 中文关键词映射到相关词 |
| 单词匹配 | +2 | 单个词在描述中 |

### 关键词映射

```
"研究" → researcher, research, 调查, 信息
"写"   → writer, write, 创作, 文章, 内容
"代码" → coder, code, 编程, 程序
"分析" → analyst, analyze, 数据, 统计
"审核" → reviewer, review, 检查, 质量
"翻译" → translator, translate, 语言
```

### 匹配示例

**查询**: "研究好莱坞的历史"

1. 检查完整匹配：❌ 不在任何Agent描述中
2. 分词：["研究", "好莱坞", "的", "历史"]
3. 关键词"研究"触发映射：
   - Researcher Agent包含"research" → +3分
   - Researcher Agent包含"调查" → +3分
4. 最终匹配：**Researcher Agent** (最高分)

## 🔍 调试技巧

### 1. 查看MCP Server日志

MCP Server会输出匹配信息：
```
🔎 [Real MCP Server] Received find_agent query: 研究好莱坞的历史
✅ [Real MCP Server] Matched: Researcher Agent (score: 8)
```

### 2. 检查Agent Cards

确保cards文件格式正确：
```bash
# 验证JSON格式
python3 -m json.tool real_ecosystem/cards/researcher.json
```

### 3. 测试单个查询

```python
# 在Python中测试
import asyncio
from yinqing.core.mcp_client import init_session, find_agent

async def test():
    async with init_session("localhost", 10000, "sse") as session:
        result = await find_agent(session, "研究历史")
        print(result.content[0].text)

asyncio.run(test())
```

## 📝 常见问题

### Q1: 仍然出现JSON解析错误？

**检查**：
1. MCP Server是否已重启
2. cards文件是否存在且格式正确
3. 查看MCP Server的控制台输出

### Q2: 匹配不准确？

**解决**：
1. 在`keyword_mapping`中添加更多关键词
2. 调整评分权重
3. 在Agent cards中添加更多中文标签

### Q3: 所有查询都匹配到Researcher Agent？

**原因**：这是默认行为（当没有更好的匹配时）

**改进**：
- 在cards中添加更多中文描述和标签
- 优化关键词映射

## 🎯 预期效果

修复后：
- ✅ 不再出现JSON解析错误
- ✅ 中文查询能正确匹配Agent
- ✅ 即使没有完美匹配也能返回合理的默认Agent
- ✅ 系统更加健壮和容错

---

**修复时间**: 2025-12-15  
**修复人**: Kiro AI Assistant  
**状态**: ✅ 已测试
