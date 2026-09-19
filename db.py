"""Shared database access for the tracker and the viewer.

Keeping the schema in one place means the tracker, the viewer, and anything
added later (an API, a dashboard) all agree on the shape of the data and all
apply the same migrations on startup.
"""

import sqlite3

DB_PATH = "activity.db"

# Category assigned to apps we have not classified yet. The tracker never
# blocks to ask; categorization happens in the viewer.
DEFAULT_CATEGORY = "Uncategorized"

# Recorded in the `app` column for stretches where the machine was idle.
IDLE_APP = "__idle__"
IDLE_CATEGORY = "Idle"


def connect(path=DB_PATH):
    connection = sqlite3.connect(path)
    ensure_schema(connection)

    return connection


def _columns(connection, table):
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def ensure_schema(connection):
    connection.execute("""
    CREATE TABLE IF NOT EXISTS activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        app TEXT,
        start_time REAL,
        end_time REAL,
        duration REAL
    )
    """)

    connection.execute("""
    CREATE TABLE IF NOT EXISTS app_categories (
        app TEXT PRIMARY KEY,
        category TEXT
    )
    """)

    # Migration: window_title was added after the first databases were
    # created, so add it in place rather than requiring a rebuild. Existing
    # rows keep NULL, which the viewer renders as "(no title)".
    if "window_title" not in _columns(connection, "activities"):
        connection.execute("ALTER TABLE activities ADD COLUMN window_title TEXT")

    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_activities_start_time ON activities (start_time)"
    )

    # Idle stretches are stored as ordinary rows under a reserved app name,
    # so make sure they always resolve to a sensible category.
    connection.execute(
        "INSERT OR IGNORE INTO app_categories (app, category) VALUES (?, ?)",
        (IDLE_APP, IDLE_CATEGORY)
    )

    connection.commit()
