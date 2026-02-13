from fastmcp import FastMCP
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("Weight Tracker MCP Server")

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongodb:27017/bot_db")
CURRICULUM_PATH = os.environ.get("CURRICULUM_PATH", "data/rust_curriculum.json")

# Initialize MongoDB client
# We use a lazy initialization or a global client
client = MongoClient(MONGO_URI)
db = client.get_database()
weights_col = db["weights"]
rust_progress_col = db["rust_progress"]


def init_db():
    try:
        # Initialize rust_progress if it doesn't exist
        if rust_progress_col.count_documents({"_id": "global_progress"}) == 0:
            rust_progress_col.insert_one({
                "_id": "global_progress",
                "current_topic_index": 0,
                "updated_at": datetime.utcnow()
            })
        logger.info("MongoDB collections initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB: {e}")


def load_curriculum() -> List[Dict[str, Any]]:
    """Load the Rust curriculum from JSON file."""
    try:
        with open(CURRICULUM_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []


init_db()


@mcp.tool
def record_weight(weight: float, unit: str = "kg") -> str:
    """Record a new weight entry for the user. Unit should be 'kg' or 'lbs'.

    Args:
        weight: The weight value to record
        unit: The unit of measurement (default: 'kg')

    Returns:
        Confirmation message with recorded weight
    """
    entry = {
        "weight": weight,
        "unit": unit,
        "timestamp": datetime.utcnow()
    }
    weights_col.insert_one(entry)
    return f"✅ Recorded: {weight} {unit}"


@mcp.tool
def get_weights() -> List[Dict[str, Any]]:
    """Get all weight records ordered by timestamp (most recent first).

    Returns:
        List of weight records with weight, unit, and timestamp
    """
    cursor = weights_col.find({}, {"_id": 0}).sort("timestamp", -1)
    results = list(cursor)
    for r in results:
        if isinstance(r.get("timestamp"), datetime):
            r["timestamp"] = r["timestamp"].isoformat()
    return results


@mcp.tool
def get_last_weight() -> Dict[str, Any]:
    """Get the most recent weight record.

    Returns:
        The last weight record with weight, unit, and timestamp
    """
    last = weights_col.find_one({}, {"_id": 0}, sort=[("timestamp", -1)])
    if last:
        if isinstance(last.get("timestamp"), datetime):
            last["timestamp"] = last["timestamp"].isoformat()
        return last
    return {"error": "No weight records found"}


@mcp.tool
def delete_all_weights() -> str:
    """Delete all weight records. Use with caution!

    Returns:
        Confirmation message with number of deleted records
    """
    result = weights_col.delete_many({})
    return f"Deleted {result.deleted_count} records"


@mcp.tool
def get_rust_topic() -> Dict[str, Any]:
    """Get the current Rust topic the user is learning.

    Returns:
        The current topic details including index, section, title, explanation, and hint.
        Also includes progress information (current topic number and total topics).
    """
    curriculum = load_curriculum()
    if not curriculum:
        return {"error": "Curriculum not found"}

    progress = rust_progress_col.find_one({"_id": "global_progress"})
    current_index = progress["current_topic_index"] if progress else 0

    if current_index >= len(curriculum):
        return {
            "error": "All topics completed",
            "current_index": current_index,
            "total_topics": len(curriculum)
        }

    topic = curriculum[current_index]
    return {
        "index": topic["index"],
        "section": topic["section"],
        "exercise": topic["exercise"],
        "title": topic["title"],
        "explanation": topic["explanation"],
        "hint": topic["hint"],
        "current_index": current_index + 1,  # 1-indexed for display
        "total_topics": len(curriculum)
    }


@mcp.tool
def advance_rust_topic() -> Dict[str, Any]:
    """Advance to the next Rust topic and return it.

    Returns:
        The next topic details including index, section, title, explanation, and hint.
        Also includes progress information.
    """
    curriculum = load_curriculum()
    if not curriculum:
        return {"error": "Curriculum not found"}

    progress = rust_progress_col.find_one({"_id": "global_progress"})
    current_index = progress["current_topic_index"] if progress else 0

    # Check if already at end
    if current_index >= len(curriculum):
        return {
            "error": "All topics completed",
            "current_index": current_index,
            "total_topics": len(curriculum)
        }

    # Advance to next topic
    new_index = current_index + 1
    rust_progress_col.update_one(
        {"_id": "global_progress"},
        {"$set": {"current_topic_index": new_index, "updated_at": datetime.utcnow()}}
    )

    # Get the new topic
    if new_index >= len(curriculum):
        return {
            "message": "Congratulations! You've completed all topics!",
            "current_index": new_index,
            "total_topics": len(curriculum)
        }

    topic = curriculum[new_index]
    return {
        "index": topic["index"],
        "section": topic["section"],
        "exercise": topic["exercise"],
        "title": topic["title"],
        "explanation": topic["explanation"],
        "hint": topic["hint"],
        "current_index": new_index + 1,  # 1-indexed for display
        "total_topics": len(curriculum)
    }


@mcp.tool
def reset_rust_progress() -> str:
    """Reset Rust learning progress to start from topic 0.

    Returns:
        Confirmation message.
    """
    rust_progress_col.update_one(
        {"_id": "global_progress"},
        {"$set": {"current_topic_index": 0, "updated_at": datetime.utcnow()}}
    )
    return "Rust progress successfully reset to Topic 1. Ready to start fresh!"


@mcp.tool
def get_history_today() -> str:
    """Get interesting historical events that happened on this day in history.

    Scrapes Wikipedia's "On this day" page to find events, births, and deaths.

    Returns:
        A formatted summary of historical events for today with emojis
    """
    url = "https://en.wikipedia.org/wiki/Wikipedia:On_this_day/Today"

    try:
        # Add User-Agent header to avoid being blocked
        headers = {
            "User-Agent": "DiscordBot/1.0 (https://github.com/discord/discordpy; version 1.0)"
        }

        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        facts = []

        # Find the main content area
        content = soup.find("div", class_="mw-parser-output")
        if not content:
            return "facing difficulties"

        # Get first <ul> for events (5 items)
        events_ul = None
        for ul in content.find_all("ul", recursive=False):
            if ul.find("li"):
                # Make sure this is the events list (not the navigation links)
                first_li = ul.find("li")
                if first_li:
                    events_ul = ul
                    break

        if events_ul:
            for item in events_ul.find_all("li", limit=5):
                text = item.get_text().strip()
                facts.append(f"📅 {text}")

        # Find hlist div for births/deaths
        hlist_divs = content.find_all("div", class_="hlist")

        # Extract births and deaths (2 each)
        births = []
        deaths = []

        for hlist_div in hlist_divs:
            for li in hlist_div.find_all("li"):
                text = li.get_text().strip()
                if "b." in text or "born" in text.lower():
                    if len(births) < 2:
                        births.append(text)
                elif "d." in text or "died" in text.lower():
                    if len(deaths) < 2:
                        deaths.append(text)

        # Add to facts
        for birth in births:
            facts.append(f"👶 {birth}")
        for death in deaths:
            facts.append(f"🕯️ {death}")

        if facts:
            return "\n".join(facts)
        else:
            return "facing difficulties"

    except Exception as e:
        return "facing difficulties"


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
