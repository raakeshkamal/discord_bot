from fastmcp import FastMCP
import sqlite3
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup

mcp = FastMCP("Weight Tracker MCP Server")

DB_PATH = os.environ.get("DB_PATH", "data/weight.db")
CURRICULUM_PATH = os.environ.get("CURRICULUM_PATH", "data/rust_curriculum.json")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS weights
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  weight REAL NOT NULL,
                  unit TEXT NOT NULL,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS rust_progress
                 (id INTEGER PRIMARY KEY CHECK (id = 1),
                  current_topic_index INTEGER DEFAULT 0,
                  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    # Initialize progress row if it doesn't exist
    c.execute("INSERT OR IGNORE INTO rust_progress (id, current_topic_index) VALUES (1, 0)")
    conn.commit()
    conn.close()


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
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO weights (weight, unit) VALUES (?, ?)", (weight, unit))
    record_id = c.lastrowid
    conn.commit()
    conn.close()

    return f"✅ Recorded: {weight} {unit}"


@mcp.tool
def get_weights() -> List[Dict[str, Any]]:
    """Get all weight records ordered by timestamp (most recent first).

    Returns:
        List of weight records with id, weight, unit, and timestamp
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, weight, unit, timestamp FROM weights ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()

    return [dict(row) for row in rows]


@mcp.tool
def get_last_weight() -> Dict[str, Any]:
    """Get the most recent weight record.

    Returns:
        The last weight record with id, weight, unit, and timestamp
    """
    weights = get_weights()
    if weights:
        return weights[0]
    return {"error": "No weight records found"}


@mcp.tool
def delete_all_weights() -> str:
    """Delete all weight records. Use with caution!

    Returns:
        Confirmation message with number of deleted records
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM weights")
    deleted_count = c.rowcount
    conn.commit()
    conn.close()
    return f"Deleted {deleted_count} records"


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

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT current_topic_index FROM rust_progress WHERE id = 1")
    row = c.fetchone()
    conn.close()

    current_index = row["current_topic_index"] if row else 0

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

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Get current index
    c.execute("SELECT current_topic_index FROM rust_progress WHERE id = 1")
    row = c.fetchone()
    current_index = row["current_topic_index"] if row else 0

    # Check if already at end
    if current_index >= len(curriculum):
        conn.close()
        return {
            "error": "All topics completed",
            "current_index": current_index,
            "total_topics": len(curriculum)
        }

    # Advance to next topic
    new_index = current_index + 1
    c.execute(
        "UPDATE rust_progress SET current_topic_index = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
        (new_index,)
    )
    conn.commit()

    # Get the new topic
    if new_index >= len(curriculum):
        conn.close()
        return {
            "message": "Congratulations! You've completed all topics!",
            "current_index": new_index,
            "total_topics": len(curriculum)
        }

    topic = curriculum[new_index]
    conn.close()

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
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO rust_progress (id, current_topic_index, updated_at) VALUES (1, 0, CURRENT_TIMESTAMP)")
    conn.commit()

    # Verify reset
    c.execute("SELECT current_topic_index FROM rust_progress WHERE id = 1")
    row = c.fetchone()
    if row and row[0] == 0:
        msg = "Rust progress successfully reset to Topic 1. Ready to start fresh! (v2)"
    else:
        msg = f"Reset attempted but current index is {row[0] if row else 'None'}. Please check logs."
    
    conn.close()
    return msg


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
