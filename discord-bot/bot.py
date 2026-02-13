import discord
from discord.ext import commands, tasks
import aiohttp
import os
import io
import json
import plotly.graph_objects as go
import plotly.io as pio
import pandas as pd
import re
import logging
from fastmcp import Client

# Import from agent_logic
from agent_logic import personas, initialize_personas, get_london_weather, logger

# Configure logging
# logging.basicConfig(level=logging.INFO) # Already configured in agent_logic if needed, but let's keep it here for bot.py specific
logger.setLevel(logging.INFO)

# Environment variables
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
CHANNEL_ID = int(os.environ.get("DISCORD_CHANNEL_ID", "0"))

# Weather code to human-readable description mapping
WEATHER_CODES = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "dense freezing drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "heavy freezing rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}

# Setup Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- User Mode Management ---
user_modes = {}  # Format: {user_id: persona_name}
DEFAULT_PERSONA = "general"

@bot.command()
async def mode(ctx, persona_name: str = None):
    """Switch your interaction mode (general, weight, rust)."""
    if not persona_name:
        current = user_modes.get(ctx.author.id, DEFAULT_PERSONA)
        # Handle cases where current mode might not be in personas (e.g. if we remove one)
        if current not in personas:
            current = DEFAULT_PERSONA
        
        await ctx.send(f"Current mode: **{current}**. Available modes: {', '.join(personas.keys())}.")
        return

    persona_name = persona_name.lower()
    if persona_name in personas:
        user_modes[ctx.author.id] = persona_name
        
        # Send a welcome message from the new persona
        await ctx.send(f"Switched to **{personas[persona_name].name}** mode. {personas[persona_name].description}")
    else:
        await ctx.send(f"Unknown mode '{persona_name}'. Available modes: {', '.join(personas.keys())}")

@bot.command()
async def modes(ctx):
    """List all available personas."""
    msg = "**Available Modes:**\n"
    for p_id, p in personas.items():
        msg += f"• **{p_id}**: {p.description}\n"
    msg += "\nUse `!mode <name>` to switch."
    await ctx.send(msg)

# Global state for startup
has_fired_startup_check = False

@bot.event
async def on_ready():
    global has_fired_startup_check
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    
    # Initialize personas (load MCP tools)
    await initialize_personas()
    
    if not daily_check.is_running():
        logger.info("Starting daily check-in loop...")
        daily_check.start()


@tasks.loop(hours=24)
async def daily_check():
    """Send daily check-in message."""
    logger.info(f"Executing daily_check. CHANNEL_ID: {CHANNEL_ID}")
    if CHANNEL_ID:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            logger.info(f"Found channel: {channel.name} (ID: {channel.id})")
            weather = await get_london_weather()
            if weather:
                temp = weather.get("temperature", "N/A")
                code = weather.get("weathercode", 0)
                condition = WEATHER_CODES.get(code, "unknown conditions")
                is_day = weather.get("is_day", 1)
                sun_emoji = "🌞" if is_day else "🌙"
                weather_msg = f"{sun_emoji} It's {temp}°C and {condition} in London."
            else:
                logger.warning("Failed to fetch weather data.")
                weather_msg = "Good morning!"

            log_msg = f"{weather_msg} Feel free to ask me for help with anything today!"
            logger.info(f"Sending message: {log_msg}")
            try:
                await channel.send(log_msg)
                logger.info(f"Successfully sent daily check to {channel}")
            except Exception as e:
                logger.error(f"Failed to send message to channel: {e}")
        else:
            logger.error(f"Could not find channel with ID: {CHANNEL_ID}. Make sure the bot has access to this channel.")
    else:
        logger.warning("CHANNEL_ID is not set (0). Skipping daily check-in.")


@daily_check.before_loop
async def before_daily_check():
    await bot.wait_until_ready()


@bot.command()
async def weight(ctx, value: float, unit: str = "kg"):
    """Explicitly record weight via command."""
    response = await call_mcp_tool("record_weight", {"weight": value, "unit": unit})
    if response:
        log_msg = str(response)
        logger.info(f"Sent to {ctx.channel}: {log_msg}")
        await ctx.send(log_msg)
    else:
        log_msg = "❌ Failed to record weight. Is the database running?"
        logger.info(f"Sent to {ctx.channel}: {log_msg}")
        await ctx.send(log_msg)


@bot.command()
async def last(ctx):
    """Show the last recorded weight."""
    data = await call_mcp_tool("get_last_weight", {})
    if data and "error" not in str(data):
        # Extract weight data from response
        if hasattr(data, "content"):
            # It's a TextContent object
            import json

            try:
                weight_data = json.loads(
                    data.content[0].text
                    if isinstance(data.content, list)
                    else data.content
                )
            except:
                weight_data = data
        else:
            weight_data = data

        if isinstance(weight_data, dict) and "weight" in weight_data:
            log_msg = f"📅 Last recorded weight: **{weight_data['weight']} {weight_data['unit']}** on {weight_data['timestamp']}"
        else:
            log_msg = "No weight records found."
    else:
        log_msg = "No weight records found."

    logger.info(f"Sent to {ctx.channel}: {log_msg}")
    await ctx.send(log_msg)


@bot.command()
async def plot(ctx):
    """Show last 10 readings and progress graph."""
    data = await call_mcp_tool("get_weights", {})
    if not data:
        log_msg = "No records found."
        logger.info(f"Sent to {ctx.channel}: {log_msg}")
        await ctx.send(log_msg)
        return

    await send_full_report(ctx, data)


@bot.command()
async def reset(ctx):
    """Delete all records."""
    log_msg = "⚠️ Are you sure you want to delete ALL data? Reply with `yes` to confirm."
    logger.info(f"Sent to {ctx.channel}: {log_msg}")
    await ctx.send(log_msg)

    def check(m):
        return (
            m.author == ctx.author
            and m.channel == ctx.channel
            and m.content.lower() == "yes"
        )

    try:
        await bot.wait_for("message", check=check, timeout=30.0)
    except TimeoutError:
        log_msg = "Operations cancelled."
        logger.info(f"Sent to {ctx.channel}: {log_msg}")
        await ctx.send(log_msg)
        return

    response = await call_mcp_tool("delete_all_weights", {})
    if response:
        log_msg = str(response)
        logger.info(f"Sent to {ctx.channel}: {log_msg}")
        await ctx.send(log_msg)
    else:
        log_msg = "❌ Failed to delete records."
        logger.info(f"Sent to {ctx.channel}: {log_msg}")
        await ctx.send(log_msg)


@bot.group()
async def rust(ctx):
    """Rust learning commands."""
    if ctx.invoked_subcommand is None:
        # Show current progress by default
        data = await call_mcp_tool("get_rust_topic", {})
        if data and "error" not in str(data):
            # Parse the response
            if hasattr(data, "content"):
                try:
                    topic_data = json.loads(
                        data.content[0].text
                        if isinstance(data.content, list)
                        else data.content
                    )
                except:
                    topic_data = {}
            else:
                topic_data = data if isinstance(data, dict) else {}

            if topic_data.get("title"):
                msg = f"🦀 You're on **Topic {topic_data.get('current_index', '?')} of {topic_data.get('total_topics', '?')}**: {topic_data.get('title')}\n"
                msg += f"Section: {topic_data.get('section', 'unknown')}\n"
                msg += "Say 'teach me some rust' to learn!"
            else:
                msg = "Use `!rust progress` to see your current topic, or `teach me some rust` to start learning!"
        else:
            msg = "Use `!rust progress` to see your current topic, or `teach me some rust` to start learning!"
        logger.info(f"Sent to {ctx.channel}: {msg}")
        await ctx.send(msg)


@rust.command()
async def progress(ctx):
    """Show current Rust learning progress."""
    data = await call_mcp_tool("get_rust_topic", {})
    if data:
        # Parse the response
        if hasattr(data, "content"):
            try:
                topic_data = json.loads(
                    data.content[0].text
                    if isinstance(data.content, list)
                    else data.content
                )
            except:
                topic_data = {}
        else:
            topic_data = data if isinstance(data, dict) else {}

        if topic_data.get("error") == "All topics completed":
            msg = "🎉 Congratulations! You've completed all Rust topics!"
        elif topic_data.get("title"):
            msg = f"🦀 **Topic {topic_data.get('current_index', '?')} of {topic_data.get('total_topics', '?')}**\n"
            msg += f"**{topic_data.get('title')}** ({topic_data.get('section', 'unknown')})\n"
            msg += f"Exercise: `{topic_data.get('exercise', 'unknown')}`"
        else:
            msg = "Could not retrieve progress. Try saying 'teach me some rust'!"
    else:
        msg = "❌ Could not retrieve progress."
    logger.info(f"Sent to {ctx.channel}: {msg}")
    await ctx.send(msg)


@rust.command()
async def restart(ctx):
    """Reset Rust learning progress to start over."""
    log_msg = "⚠️ Are you sure you want to reset your Rust progress? Reply with `yes` to confirm."
    logger.info(f"Sent to {ctx.channel}: {log_msg}")
    await ctx.send(log_msg)

    def check(m):
        return (
            m.author == ctx.author
            and m.channel == ctx.channel
            and m.content.lower() == "yes"
        )

    try:
        await bot.wait_for("message", check=check, timeout=30.0)
    except TimeoutError:
        log_msg = "Reset cancelled."
        logger.info(f"Sent to {ctx.channel}: {log_msg}")
        await ctx.send(log_msg)
        return

    response = await call_mcp_tool("reset_rust_progress", {})
    if response:
        log_msg = f"🦀 {str(response)}"
        logger.info(f"Sent to {ctx.channel}: {log_msg}")
        await ctx.send(log_msg)
    else:
        log_msg = "❌ Failed to reset progress."
        logger.info(f"Sent to {ctx.channel}: {log_msg}")
        await ctx.send(log_msg)


async def send_full_report(channel, data=None):
    """Send weight progress report with graph."""
    if data is None:
        data = await call_mcp_tool("get_weights", {})

    if not data:
        log_msg = "No data to report!"
        logger.info(f"Sent to {channel}: {log_msg}")
        await channel.send(log_msg)
        return

    # Parse data if it's a tool result
    if hasattr(data, "content"):
        import json

        try:
            weights_data = json.loads(
                data.content[0].text if isinstance(data.content, list) else data.content
            )
        except:
            weights_data = data
    else:
        weights_data = data

    if isinstance(weights_data, list):
        recent_data = weights_data[:10]
    else:
        recent_data = []

    msg_lines = ["**Last 10 Readings:**"]
    for record in recent_data:
        if isinstance(record, dict):
            try:
                ts = pd.to_datetime(record["timestamp"])
                date_str = ts.strftime("%Y-%m-%d %H:%M")
            except:
                date_str = record.get("timestamp", "unknown")
            msg_lines.append(
                f"• {record.get('weight', 'N/A')} {record.get('unit', 'kg')} on {date_str}"
            )

    await channel.send("\n".join(msg_lines))

    # Create Plot - only if we have valid data
    if weights_data and isinstance(weights_data, list):
        try:
            df = pd.DataFrame(weights_data)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp")

            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=df["timestamp"],
                    y=df["weight"],
                    mode="lines+markers",
                    name="Weight",
                    line=dict(color="#00F0FF", width=4),
                    marker=dict(
                        size=10, color="#FFFFFF", line=dict(width=2, color="#00F0FF")
                    ),
                    fill="tozeroy",
                    fillcolor="rgba(0, 240, 255, 0.1)",
                )
            )

            fig.update_layout(
                title="<b>Weight Loss Journey</b>",
                title_font=dict(size=24, color="white", family="Arial"),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="#1a1a1a",
                xaxis=dict(
                    showgrid=True,
                    gridcolor="#333333",
                    tickfont=dict(color="#AAAAAA"),
                    linecolor="#333333",
                ),
                yaxis=dict(
                    showgrid=True,
                    gridcolor="#333333",
                    tickfont=dict(color="#AAAAAA"),
                    linecolor="#333333",
                    zeroline=False,
                ),
                margin=dict(l=40, r=40, t=60, b=40),
                showlegend=False,
            )

            img_bytes = pio.to_image(fig, format="png", width=1000, height=600, scale=2)
            buf = io.BytesIO(img_bytes)
            buf.seek(0)

            logger.info(f"Sent graph to {channel}")
            await channel.send(file=discord.File(buf, filename="progress.png"))
        except Exception as e:
            logger.error(f"Failed to create graph: {e}")

    log_msg = "Keep it up! 💪"
    logger.info(f"Sent to {channel}: {log_msg}")
    await channel.send(log_msg)


async def send_long_message(channel, content: str, max_length: int = 2000):
    """Send a message, splitting it if it exceeds Discord's character limit."""
    if len(content) <= max_length:
        await channel.send(content)
        return

    # Split by newlines first, then by space if needed
    lines = content.split('\n')
    chunks = []
    current_chunk = ""

    for line in lines:
        # If adding this line would exceed limit
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""

            # If a single line is too long, split by words
            if len(line) > max_length:
                words = line.split(' ')
                for word in words:
                    if len(current_chunk) + len(word) + 1 > max_length:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = word
                    else:
                        current_chunk = current_chunk + " " + word if current_chunk else word
            else:
                current_chunk = line
        else:
            current_chunk = current_chunk + "\n" + line if current_chunk else line

    if current_chunk:
        chunks.append(current_chunk)

    for chunk in chunks:
        await channel.send(chunk)


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    logger.info(f"Received message: {message.content} from {message.author}")

    # Process commands first
    await bot.process_commands(message)
    if message.content.startswith("!"):
        return

    # Determine user's persona
    user_persona_name = user_modes.get(message.author.id, DEFAULT_PERSONA)
    # Check if persona exists, otherwise fallback to default
    if user_persona_name not in personas:
        user_persona_name = DEFAULT_PERSONA
    
    user_agent_executor = personas[user_persona_name].executor

    # Use LangChain Agent
    try:
        response = await user_agent_executor.ainvoke({"input": message.content})
        output = response.get("output")
        if output:
            await send_long_message(message.channel, output)
    except Exception as e:
        logger.error(f"Agent error for persona {user_persona_name}: {e}")
        await message.channel.send(
            "I'm having a bit of trouble thinking right now. Please try again."
        )


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not found.")
    else:
        bot.run(DISCORD_TOKEN)
