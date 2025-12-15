#!/bin/bash

echo "🛑 停止 MCP Server..."
pkill -f "real_ecosystem/mcp_server/server.py"

sleep 2

echo "✅ MCP Server 已停止"
echo ""
echo "🚀 重新启动 MCP Server..."
echo ""

export PYTHONPATH=$PYTHONPATH:$(pwd)

# 启动MCP Server
python3 real_ecosystem/mcp_server/server.py &
PID_MCP=$!
echo "✅ Started MCP Server (PID: $PID_MCP)"

sleep 3

echo ""
echo "---------------------------------------------------"
echo "🚀 MCP Server 已重启!"
echo "---------------------------------------------------"
echo "端口: 10000"
echo "PID: $PID_MCP"
echo ""
echo "测试连接:"
echo "  python3 test_mcp_find_agent.py"
echo ""
