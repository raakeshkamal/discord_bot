"""
Gradio Web UI for nanobot AI Agent
===================================
Simple interface to chat with nanobot agent via command line interface.
Since nanobot is a standalone CLI tool, this UI wraps the `nanobot agent` command.
"""

import gradio as gr
import subprocess
import os
import re
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.environ.get(
    "OPENROUTER_MODEL", "google/gemini-2.0-flash-lite-preview-02-05:free"
)
NANOBOT_WORKSPACE = "/root/.nanobot"


def clean_markdown(text):
    """Clean markdown formatting for display."""
    if not text:
        return text
    # Remove common markdown artifacts that might cause issues
    text = text.replace("\\n", "\n")
    return text


def run_nanobot_agent(message, history, persona_name):
    """
    Run nanobot agent CLI with a message.

    This uses subprocess to call `nanobot agent -m "message"`.
    """
    if not OPENROUTER_API_KEY:
        return "Error: OPENROUTER_API_KEY not set. Please configure the API key."

    # Build environment with API key
    env = os.environ.copy()
    env["OPENROUTER_API_KEY"] = OPENROUTER_API_KEY

    # If a specific persona/skill is selected, we could potentially
    # pass it as context or use it in the prompt
    # For now, nanobot will auto-detect based on trigger words in skills

    try:
        # Build the command
        cmd = [
            "nanobot",
            "agent",
            "-m",
            message,
            "--no-markdown",  # Get plain text for better Gradio display
        ]

        # Run nanobot agent
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,  # 60 second timeout
            env=env,
            cwd=NANOBOT_WORKSPACE,
        )

        if result.returncode == 0:
            response = clean_markdown(result.stdout.strip())
            return response if response else "(No response received)"
        else:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            return f"Error: {error_msg}"

    except subprocess.TimeoutExpired:
        return "Request timed out. The agent took too long to respond."
    except FileNotFoundError:
        return "Error: nanobot CLI not found. Please ensure nanobot-ai is installed."
    except Exception as e:
        return f"Error: {str(e)}"


# Get available skills/personas
AVAILABLE_PERSONAS = ["general", "weight", "rust", "cpp", "python"]

# Create Gradio Interface
with gr.Blocks(title="Nanobot AI Interface") as demo:
    gr.Markdown("# Nanobot AI Interface")
    gr.Markdown("Chat with the nanobot AI assistant.")
    gr.Markdown(
        "The agent will automatically detect which skill to use based on your message."
    )

    with gr.Row():
        persona_selector = gr.Dropdown(
            choices=AVAILABLE_PERSONAS,
            value="general",
            label="Active Skill (informational)",
            interactive=True,
        )

    # Chat interface using Gradio's ChatInterface
    chatbot = gr.ChatInterface(
        fn=run_nanobot_agent,
        additional_inputs=[persona_selector],
        examples=[
            ["What is the weather in London?", "general"],
            ["I weigh 75 kg", "weight"],
            ["Teach me about Rust", "rust"],
            ["What is object-oriented programming in C++?", "cpp"],
            ["How do I use lists in Python?", "python"],
            ["What happened today in history?", "general"],
        ],
        cache_examples=False,
    )

    gr.Markdown("---")
    gr.Markdown("### How it works")
    gr.Markdown("""
    - Messages are processed by the nanobot CLI (`nanobot agent`)
    - The agent automatically selects the appropriate skill based on keywords
    - Weight tracking, Rust, C++, and Python tutors are available
    - MCP tools (MongoDB, weather, history) are accessible
    """)

if __name__ == "__main__":
    port = int(os.environ.get("GRADIO_PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port, theme=gr.themes.Soft())
