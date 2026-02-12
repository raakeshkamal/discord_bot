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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.environ.get(
    "OPENROUTER_MODEL", "google/gemini-2.0-flash-lite-preview-02-05:free"
)
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://mcp-server:8000/mcp")
CHANNEL_ID = int(os.environ.get("DISCORD_CHANNEL_ID", "0"))

# --- LangChain Imports ---
try:
    import langchain

    print(f"DEBUG: langchain version: {langchain.__version__}")
    print(f"DEBUG: langchain path: {langchain.__file__}")
    import langchain.agents

    print(f"DEBUG: langchain.agents contents: {dir(langchain.agents)}")
except Exception as e:
    print(f"DEBUG: Error inspecting langchain: {e}")

from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate

# --- Tool Definitions ---


@tool
async def get_current_weather_london():
    """Get the current weather in London."""
    return await get_london_weather()


@tool
async def record_weight_tool(weight: float, unit: str):
    """Record the user's weight.

    Args:
        weight: The numerical weight value.
        unit: The unit of measurement ('kg' or 'lbs').
    """
    return await call_mcp_tool("record_weight", {"weight": weight, "unit": unit})


@tool
async def get_last_weight_tool():
    """Get the last recorded weight."""
    return await call_mcp_tool("get_last_weight", {})


@tool
async def get_weight_history_tool():
    """Get the recent weight history."""
    return await call_mcp_tool("get_weights", {})


@tool
async def delete_all_data_tool():
    """Delete all recorded weight data. Ask for confirmation before calling this."""
    # NOTE: In a real production app, we might want the agent to NOT have this power
    # without a specific human-in-the-loop confirmation step.
    # For now, we will allow it but the system prompt should encourage caution.
    return await call_mcp_tool("delete_all_weights", {})


@tool
async def get_rust_topic_tool():
    """Get the current Rust topic the user is learning. Use this when user asks about their Rust learning progress or wants to see their current topic."""
    return await call_mcp_tool("get_rust_topic", {})


@tool
async def next_rust_topic_tool():
    """Advance to the next Rust topic and return it. Use this when user wants to learn a new Rust topic, asks to be taught Rust, or says something like 'teach me some rust' or 'next topic'."""
    return await call_mcp_tool("advance_rust_topic", {})


@tool
async def get_history_today_tool():
    """Get interesting historical events that happened on this day in history."""
    return await call_mcp_tool("get_history_today", {})


# Setup Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


async def call_mcp_tool(tool_name: str, arguments: dict):
    """Call an MCP tool using FastMCP Client."""
    logger.debug(f"Calling MCP tool: {tool_name} with args: {arguments}")
    try:
        async with Client(MCP_SERVER_URL) as client:
            result = await client.call_tool(tool_name, arguments)
            logger.debug(f"MCP tool response: {result}")
            return result
    except Exception as e:
        logger.error(f"Failed to call MCP tool {tool_name}: {e}")
        return None


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


async def get_london_weather():
    """Fetch current weather for London from Open-Meteo API."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 51.5072,
        "longitude": -0.1276,
        "current_weather": "true",
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    text = await response.text()
                    logger.error(f"Weather API Error: {response.status} - {text}")
                    return None
                data = await response.json()
                return data.get("current_weather")
        except Exception as e:
            logger.error(f"Failed to fetch weather: {e}")
            return None


# --- Agent Setup ---

llm = ChatOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    model=OPENROUTER_MODEL,
    temperature=0,
)

tools = [
    get_current_weather_london,
    get_history_today_tool,
    record_weight_tool,
    get_last_weight_tool,
    get_weight_history_tool,
    delete_all_data_tool,
    get_rust_topic_tool,
    next_rust_topic_tool,
]

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful AI assistant. You can help with various tasks including weight tracking, checking the weather in London, Rust tutoring, and sharing historical events. "
            "When showing weight history, also mention that you can generate a graph if they use the !plot command explicitly (as I cannot generate images directly yet). "
            "When the user asks to learn Rust, be taught Rust, or says something like 'teach me some rust', use the next_rust_topic_tool to get their next topic and explain it clearly with examples. "
            "When they ask for the next topic or want to continue learning, use next_rust_topic_tool. "
            "When they ask about their Rust progress or what topic they're on, use get_rust_topic_tool. "
            "When users ask about today in history, use the get_history_today_tool to get interesting facts. "
            "Be encouraging and supportive, especially when teaching Rust concepts. "
            "Format Rust topics nicely with the crab emoji and clear sections.",
        ),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
)

agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    daily_check.start()


@tasks.loop(hours=24)
async def daily_check():
    """Send daily check-in message."""
    if CHANNEL_ID:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            weather = await get_london_weather()
            if weather:
                temp = weather.get("temperature", "N/A")
                code = weather.get("weathercode", 0)
                condition = WEATHER_CODES.get(code, "unknown conditions")
                is_day = weather.get("is_day", 1)
                sun_emoji = "🌞" if is_day else "🌙"
                weather_msg = f"{sun_emoji} It's {temp}°C and {condition} in London."
            else:
                weather_msg = "Good morning!"

            log_msg = f"{weather_msg} Feel free to ask me for help with anything today!"
            logger.info(f"Sent daily check to {channel}: {log_msg}")
            await channel.send(log_msg)


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

    # Use LangChain Agent for everything else
    try:
        response = await agent_executor.ainvoke({"input": message.content})
        output = response.get("output")
        if output:
            await send_long_message(message.channel, output)
    except Exception as e:
        logger.error(f"Agent error: {e}")
        await message.channel.send(
            "I'm having a bit of trouble thinking right now. Please try again."
        )


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not found.")
    else:
        bot.run(DISCORD_TOKEN)
