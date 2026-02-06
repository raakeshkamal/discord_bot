from fastmcp import FastMCP
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any

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


if __name__ == "__main__":
    mcp.run(transport="http", port=8000)
