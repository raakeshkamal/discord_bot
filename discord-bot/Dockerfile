FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install nanobot-ai and dependencies
RUN pip install nanobot-ai gradio python-dotenv

# Create nanobot workspace directory and copy skills
RUN mkdir -p /root/.nanobot/workspace
COPY discord-bot/skills /root/.nanobot/workspace/skills

# Copy Gradio UI from discord-bot directory
COPY discord-bot/gradio_ui.py .

# Copy entrypoint script
COPY discord-bot/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port for Gradio (if running web-ui service)
EXPOSE 7860

# Use entrypoint to generate config
ENTRYPOINT ["/entrypoint.sh"]
CMD ["nanobot", "gateway"]
