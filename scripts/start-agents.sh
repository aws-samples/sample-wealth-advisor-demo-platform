#!/bin/bash
# Start all advisor chat agents in background with log files
set -e
cd "$(dirname "$0")/../packages/advisor_chat"

LOG_DIR="/tmp/wmp-agents"
mkdir -p "$LOG_DIR"

echo "Starting agents (logs in $LOG_DIR/)..."

PORT=9001 uv run python -m wealth_management_portal_advisor_chat.database_agent.main        > "$LOG_DIR/database.log" 2>&1 &
PORT=9002 uv run python -m wealth_management_portal_advisor_chat.stock_data_agent.main      > "$LOG_DIR/stock-data.log" 2>&1 &
PORT=9004 uv run python -m wealth_management_portal_advisor_chat.web_search_agent.main      > "$LOG_DIR/web-search.log" 2>&1 &
PORT=9005 uv run python -m wealth_management_portal_advisor_chat.voice_gateway.main         > "$LOG_DIR/voice-gateway.log" 2>&1 &

echo "Waiting for agents to start..."
sleep 10

echo "--- Health checks ---"
for p in 9001 9002 9004; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$p/ping 2>/dev/null || echo "000")
  echo "Port $p (/ping): $STATUS"
done
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9005/health 2>/dev/null || echo "000")
echo "Port 9005 (/health): $STATUS"

echo ""
echo "To view logs:  tail -f $LOG_DIR/*.log"
echo "To stop all:   kill \$(lsof -ti:9001,9002,9004,9005)"
