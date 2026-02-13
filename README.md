# Discord Bot with MCP Integration

This project is a Discord bot that uses Model Context Protocol (MCP) to interact with various tools, including weight tracking and Rust learning progress.

## Features
- **Discord Interface**: Interact with the bot on Discord.
- **Gradio Web UI**: A web-based chat interface for easier testing and development.
- **Multiple Personas**: Switch between General, Weight Tracker, and Rust Tutor modes.
- **MCP Tools**: Integration with a custom MCP server for data persistence and specialized tasks.

## Getting Started

### Prerequisites
- Docker and Docker Compose
- OpenRouter API Key
- Discord Bot Token

### Setup
1. Create a `.env` file in the root directory with the following:
   ```env
   DISCORD_TOKEN=your_discord_token
   OPENROUTER_API_KEY=your_openrouter_key
   OPENROUTER_MODEL=google/gemini-2.0-flash-lite-preview-02-05:free
   DISCORD_CHANNEL_ID=your_channel_id
   ```

2. Build and run the services:
   ```bash
   docker-compose up --build
   ```

### Accessing the Web UI
Once the containers are running, you can access the Gradio web interface at:
`http://localhost:7860`

## Project Structure
- `discord-bot/`: Bot logic and Gradio UI.
  - `bot.py`: Discord bot implementation.
  - `gradio_ui.py`: Gradio web interface.
  - `agent_logic.py`: Shared agent and tool definitions.
- `mcp-server/`: FastMCP server implementation.
