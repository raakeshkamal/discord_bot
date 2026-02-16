# Telegram Bot with Nanobot AI and MCP Integration

A Telegram bot powered by **nanobot**, an ultra-lightweight AI assistant framework, using Model Context Protocol (MCP) for tool integration. Features include weight tracking, interactive programming tutorials (Rust, C++, Python), and history queries.

## Features

- **Telegram Bot**: Powered by nanobot's built-in Telegram channel
- **Gradio Web UI**: Web-based chat interface for testing without Telegram
- **Multiple Personas**: Auto-detected based on trigger words in messages:
  - **General**: General queries, weather, and history
  - **Weight Tracker**: Track and visualize weight loss progress
  - **Rust Tutor**: Interactive Rust programming lessons
  - **C++ Tutor**: Interactive C++ programming lessons
  - **Python Tutor**: Interactive Python programming lessons
- **Skills System**: Personas defined via SKILL.md files for easy customization
- **MCP Tools**: Integration with FastMCP server for data persistence
- **Observability**: Arize Phoenix integration for tracing and monitoring

## Architecture

The project uses **nanobot**, an AI assistant framework that provides:
- Built-in Telegram gateway (`nanobot gateway`)
- Multi-provider LLM support (OpenRouter, OpenAI, Anthropic, etc.)
- Skills-based persona system
- Native MCP client support

```
┌─────────────────────────────────────────────────────────┐
│                    SYSTEM ARCHITECTURE                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   Telegram/Gradio ──► nanobot gateway                   │
│                           │                             │
│           ┌───────────────┼───────────────┐            │
│           ▼               ▼               ▼            │
│      LLM Provider     Skills          MCP Tools        │
│      (OpenRouter)     (SKILL.md)      (FastMCP/SSE)    │
│                                                         │
│      Config           Workspace      MongoDB           │
│      (~/.nanobot)     (/app/workspace) (Data)          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Getting Started

### Prerequisites

- Docker and Docker Compose
- OpenRouter API Key (get one at https://openrouter.ai)
- Telegram Bot Token (get one from @BotFather)

### Setup

1. **Clone and configure:**
   ```bash
   git clone <repo-url>
   cd discord_bot
   ```

2. **Create a `.env` file:**
   ```env
   TELEGRAM_TOKEN=your_telegram_bot_token
   OPENROUTER_API_KEY=your_openrouter_key
   OPENROUTER_MODEL=google/gemini-2.0-flash-lite-preview-02-05:free
   TELEGRAM_CHAT_ID=your_chat_id_for_daily_messages
   ```

3. **Build and run:**
   ```bash
   docker-compose up --build
   ```

4. **Access services:**
   - Telegram Bot: Message your bot on Telegram
   - Web UI: http://localhost:7860
   - Phoenix UI: http://localhost:6006 (observability)

## Project Structure

```
discord_bot/
├── nanobot_config/                 # nanobot configuration
│   ├── config.json                # Main configuration
│   └── skills/                    # Skill definitions
│       ├── general/SKILL.md
│       ├── weight/SKILL.md
│       ├── rust/SKILL.md
│       ├── cpp/SKILL.md
│       └── python/SKILL.md
├── discord-bot/                    # Main bot application
│   ├── Dockerfile                 # nanobot container
│   └── gradio_ui.py               # Web UI
├── mcp-server/                     # MCP server
│   ├── server.py                  # FastMCP server (SSE transport)
│   ├── data/                      # Curriculum JSON files
│   └── requirements.txt
├── docker-compose.yml             # Docker orchestration
└── README.md                      # This file
```

## How It Works

Unlike traditional bot architectures, this setup uses **nanobot as a standalone application**:

### Telegram Bot
- Runs via `nanobot gateway` command
- Configuration in `nanobot_config/config.json`
- Automatically connects to MCP server for tools
- Skills auto-detect based on message content

### Skills System
Skills are defined in markdown files with frontmatter:

```markdown
---
name: rust
description: Rust programming tutor. Triggers on: rust, cargo, rustlang
---

# Rust Programming Tutor

Teach Rust concepts step by step...
```

**Trigger words** in the description tell nanobot when to activate each skill.

### Example Interactions

- **"What is the weather in London?"** → General skill + get_current_weather_london tool
- **"I weigh 75 kg"** → Weight skill + record_weight tool
- **"Teach me about Rust"** → Rust skill + get_rust_topic tool
- **"Tell me about C++ classes"** → C++ skill + curriculum tools

## Customizing Personas

### Editing Existing Skills

Edit the SKILL.md files in `nanobot_config/skills/`:

```bash
# Edit Rust tutor
nano nanobot_config/skills/rust/SKILL.md

# Edit Weight tracker  
nano nanobot_config/skills/weight/SKILL.md
```

Changes take effect after rebuilding the Docker image.

### Adding a New Skill

1. Create a new directory:
   ```bash
   mkdir nanobot_config/skills/newskill
   ```

2. Create SKILL.md:
   ```markdown
   ---
   name: newskill
   description: What this skill does. Triggers on: keyword1, keyword2
   ---
   
   # New Skill
   
   Instructions for the AI...
   ```

3. Rebuild and restart:
   ```bash
   docker-compose up --build
   ```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_TOKEN` | Your Telegram bot token | Required |
| `OPENROUTER_API_KEY` | OpenRouter API key | Required |
| `OPENROUTER_MODEL` | LLM model to use | `google/gemini-2.0-flash-lite-preview-02-05:free` |
| `TELEGRAM_CHAT_ID` | Chat ID for daily check-ins | Optional |

## Services

The Docker Compose setup includes:

- **nanobot**: Telegram bot gateway (nanobot's built-in channel)
- **web-ui**: Gradio web interface (port 7860)
- **mcp-server**: FastMCP tool server with SSE transport (port 8000)
- **mongodb**: Data persistence (port 27117)
- **phoenix**: Arize Phoenix observability (port 6006)

## Development

### Running Locally (without Docker)

```bash
# Install nanobot
pip install nanobot-ai

# Set up config directory
mkdir -p ~/.nanobot
ln -s $(pwd)/nanobot_config/config.json ~/.nanobot/config.json
ln -s $(pwd)/nanobot_config/skills ~/.nanobot/skills

# Run Telegram gateway
export OPENROUTER_API_KEY=your_key
export TELEGRAM_TOKEN=your_token
nanobot gateway
```

### Testing Web UI Only

```bash
cd discord-bot
pip install gradio nanobot-ai
python gradio_ui.py
```

## Available Tools

The MCP server provides these tools that skills can use:

### Weight Tracking
- `record_weight(weight, unit)` - Record a weight entry
- `get_weights()` - Get all weight records
- `get_last_weight()` - Get most recent weight
- `delete_all_weights()` - Delete all records

### Programming Tutorials
- `get_rust_topic()` / `advance_rust_topic()` / `reset_rust_progress()`
- `get_cpp_topic()` / `advance_cpp_topic()` / `reset_cpp_progress()`
- `get_python_topic()` / `advance_python_topic()` / `reset_python_progress()`

### General
- `get_current_weather_london()` - Get London weather
- `get_history_today()` - Wikipedia historical events
- `get_history_britannica()` - Britannica historical events
- `get_history_on_this_day()` - OnThisDay.com events

## Troubleshooting

### Bot not responding
- Check `TELEGRAM_TOKEN` is correct in `.env`
- Check nanobot container logs: `docker-compose logs nanobot`
- Verify config.json has valid JSON

### MCP tools not working
- Check MCP server is running: `docker-compose ps mcp-server`
- Check SSE endpoint: `curl http://localhost:8000/sse`
- Check MongoDB is running: `docker-compose ps mongodb`

### Skills not loading
- Check nanobot_config/skills/ directory structure
- Verify SKILL.md files have proper frontmatter (between `---`)
- Rebuild Docker image after skill changes

### Web UI not working
- Check web-ui container logs: `docker-compose logs web-ui`
- Verify OPENROUTER_API_KEY is set
- Check port 7860 is not in use

## Migration Notes

This project was refactored to use nanobot correctly as a **standalone CLI application** rather than trying to import it as a library. This is the recommended approach per nanobot's design philosophy.

Key changes:
- Uses `nanobot gateway` for Telegram instead of custom bot.py
- Uses `nanobot agent` in Gradio UI instead of programmatic API
- Configuration via `nanobot_config/config.json` mounted to `~/.nanobot/`
- MCP server uses SSE transport for better compatibility

## License

[Your License Here]

## Acknowledgments

- [nanobot](https://github.com/HKUDS/nanobot) - Ultra-lightweight AI assistant framework
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP server framework
- [Arize Phoenix](https://github.com/Arize-ai/phoenix) - Observability
