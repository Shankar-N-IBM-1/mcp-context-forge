#!/bin/bash
# Test script to verify ServerMonitor plugin logs are visible

cd /Users/shankarn/Github/Personal/mcp-context-forge
source /Users/shankarn/.venv/mcpgateway/bin/activate

echo "Starting server with LOG_LEVEL=INFO..."
echo "Watch for 'Initializing ServerMonitorPlugin' message..."
echo "Server will log every 60 seconds. Press Ctrl+C to stop."
echo ""

# Set log level and start server
export LOG_LEVEL=INFO
uvicorn mcpgateway.main:app --host 0.0.0.0 --port 8000 --log-level info

# Made with Bob
