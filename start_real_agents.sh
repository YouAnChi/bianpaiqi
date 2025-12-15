#!/bin/bash

# Kill background processes on exit
trap "kill 0" EXIT

echo "Starting Real Agent Ecosystem..."

export PYTHONPATH=$PYTHONPATH:$(pwd)

# 1. Start MCP Server (Port 10000)
python3 real_ecosystem/mcp_server/server.py &
PID_MCP=$!
echo "✅ Started MCP Server (PID: $PID_MCP)"

# 2. Start Researcher Agent (Port 10001)
python3 real_ecosystem/agents/researcher.py &
PID_RES=$!
echo "✅ Started Researcher Agent (PID: $PID_RES)"

# 3. Start Writer Agent (Port 10002)
python3 real_ecosystem/agents/writer.py &
PID_WRI=$!
echo "✅ Started Writer Agent (PID: $PID_WRI)"

# 4. Start Coder Agent (Port 10003)
python3 real_ecosystem/agents/coder.py &
PID_COD=$!
echo "✅ Started Coder Agent (PID: $PID_COD)"

# 5. Start Data Analyst Agent (Port 10004)
python3 real_ecosystem/agents/data_analyst.py &
PID_DATA=$!
echo "✅ Started Data Analyst Agent (PID: $PID_DATA)"

# 6. Start Reviewer Agent (Port 10005)
python3 real_ecosystem/agents/reviewer.py &
PID_REV=$!
echo "✅ Started Reviewer Agent (PID: $PID_REV)"

# 7. Start Translator Agent (Port 10006)
python3 real_ecosystem/agents/translator.py &
PID_TRANS=$!
echo "✅ Started Translator Agent (PID: $PID_TRANS)"

# 8. Start Quality Reviewer Agent (Port 10007) - NEW
python3 real_ecosystem/agents/quality_reviewer.py &
PID_QUALITY=$!
echo "✅ Started Quality Reviewer Agent (PID: $PID_QUALITY)"

# Wait for servers to start
sleep 5

echo "---------------------------------------------------"
echo "🚀 Real Ecosystem Ready!"
echo "---------------------------------------------------"
echo "You can now run the orchestrator in another terminal:"
echo "  ./run_local.sh \"Write a python script to calculate fibonacci numbers\""
echo ""
echo "Press Ctrl+C to stop all servers."

wait
