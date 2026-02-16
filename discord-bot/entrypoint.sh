#!/bin/bash

# Set defaults if not provided
if [ -z "$OPENROUTER_MODEL" ]; then
    export OPENROUTER_MODEL="google/gemini-2.0-flash-lite-preview-02-05:free"
fi

# Generate nanobot config.json with environment variable values
cat > /root/.nanobot/config.json << EOF
{
  "providers": {
    "openrouter": {
      "apiKey": "${OPENROUTER_API_KEY}"
    }
  },
  "agents": {
    "defaults": {
      "model": "${OPENROUTER_MODEL}",
      "workspace": "/root/.nanobot/workspace"
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "${TELEGRAM_TOKEN}",
      "allowFrom": []
    }
  },
  "tools": {
    "mcpServers": {
      "tools": {
        "url": "http://mcp-server:8000/sse"
      }
    }
  }
}
EOF

# Now run the actual command
exec "$@"
