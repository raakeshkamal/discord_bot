from fastmcp import FastMCP
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup

mcp = FastMCP("Weight Tracker MCP Server")

DB_PATH = os.environ.get("DB_PATH", "data/weight.db")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS weights
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  weight REAL NOT NULL,
                  unit TEXT NOT NULL,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit()
    conn.close()


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
