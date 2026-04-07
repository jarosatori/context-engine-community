#!/bin/sh
# Start both OAuth server and Context Engine MCP server
# OAuth runs on internal port 9000, MCP server on $PORT (Railway-assigned)

# Init DB if needed
python -c 'from context_engine.db import init_db; init_db()'

# Start OAuth server in background
python -m context_engine.oauth_server &
OAUTH_PID=$!
echo "OAuth server started (PID: $OAUTH_PID) on port 9000"

# Give OAuth server time to start
sleep 2

# Start MCP server (foreground)
echo "Starting MCP server on port ${PORT:-8000}"
exec python -m context_engine.server --sse
