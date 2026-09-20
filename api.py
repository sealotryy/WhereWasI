"""Local HTTP API over the tracked activity.

Deliberately local-first: this binds to 127.0.0.1 only. The data is a minute
by minute record of what you were doing, so it should not be reachable from
the network, and there is no auth layer precisely because nothing outside this
machine can connect.

Run with:
    uvicorn api:app --reload --port 8000

Interactive docs at http://127.0.0.1:8000/docs
"""

from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import db
import queries

# Vite and Create React App defaults, so the dashboard can call the API during
# development while it is served from its own dev server.
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# A session is treated as still in progress if its end time is within this many
# seconds of now, which must stay above the tracker's FLUSH_INTERVAL.
LIVE_SESSION_WINDOW = 45


app = FastAPI(
    title="WhereWasI",
    description="Local API over tracked application activity.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=DEV_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_connection():
    """One connection per request.

    SQLite connections cannot be shared across threads, and uvicorn serves
    requests from a thread pool, so a single module-level connection would
    intermittently raise.
    """

    connection = db.connect()

    try:
        yield connection
    finally:
        connection.close()


def valid_day(value):
    """Reject anything that is not YYYY-MM-DD before it reaches a query."""

    if value is None:
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=422, detail=f"date must be YYYY-MM-DD, got {value!r}"
        )


class CategoryUpdate(BaseModel):
    category: str = Field(min_length=1, max_length=50)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/summary")
def summary(
    date: str = Query(None, description="YYYY-MM-DD, defaults to today"),
    titles_per_app: int = Query(5, ge=1, le=50),
    connection=Depends(get_connection),
):
    """Totals for one day, by app, window title, and category."""

    return queries.daily_summary(
        connection, valid_day(date), titles_per_app=titles_per_app
    )


@app.get("/api/timeline")
def timeline(
    date: str = Query(None, description="YYYY-MM-DD, defaults to today"),
    min_seconds: float = Query(0, ge=0, description="hide sessions shorter than this"),
    connection=Depends(get_connection),
):
    """Ordered sessions for one day."""

    sessions = queries.timeline(connection, valid_day(date), min_seconds=min_seconds)

    return {"date": valid_day(date) or queries.today(), "sessions": sessions}


@app.get("/api/trend")
def trend(
    days: int = Query(7, ge=1, le=365),
    start: str = Query(None, description="YYYY-MM-DD"),
    end: str = Query(None, description="YYYY-MM-DD"),
    connection=Depends(get_connection),
):
    """Active and idle seconds per day, padded so no day is missing."""

    return {
        "days": queries.daily_totals(
            connection, valid_day(start), valid_day(end), days=days
        )
    }


@app.get("/api/category-totals")
def category_totals(
    days: int = Query(7, ge=1, le=365),
    start: str = Query(None, description="YYYY-MM-DD"),
    end: str = Query(None, description="YYYY-MM-DD"),
    connection=Depends(get_connection),
):
    """Seconds per category across a date range."""

    return queries.category_totals(
        connection, valid_day(start), valid_day(end), days=days
    )


@app.get("/api/categories")
def categories(connection=Depends(get_connection)):
    """Every known app with its category, plus the ones still needing one.

    `uncategorized` is what the dashboard should surface for triage, since the
    tracker never blocks to ask.
    """

    mapping = queries.category_map(connection)
    pending = queries.uncategorized_apps(connection)

    return {
        "apps": [
            {"app": app_name, "category": category}
            for app_name, category in sorted(mapping.items())
            if app_name != db.IDLE_APP
        ],
        "categories": sorted(
            {
                category for app_name, category in mapping.items()
                if app_name != db.IDLE_APP and category != db.DEFAULT_CATEGORY
            }
        ),
        "uncategorized": pending,
    }


@app.put("/api/categories/{app_name}")
def set_category(
    app_name: str,
    update: CategoryUpdate,
    connection=Depends(get_connection),
):
    """Classify an app. Creates the mapping if it does not exist yet."""

    if app_name == db.IDLE_APP:
        raise HTTPException(status_code=400, detail="cannot recategorize idle time")

    category = update.category.strip()

    if not category:
        raise HTTPException(status_code=422, detail="category cannot be blank")

    queries.set_category(connection, app_name, category)

    return {"app": app_name, "category": category}


@app.get("/api/days")
def days(connection=Depends(get_connection)):
    """Dates that have recorded activity, newest first."""

    return {"days": queries.tracked_days(connection)}


@app.get("/api/status")
def status(connection=Depends(get_connection)):
    """What is being tracked right now, if anything.

    Lets the dashboard show a live indicator and, more usefully, warn when the
    tracker is not running so an empty chart is not mistaken for an idle day.
    """

    row = connection.execute("""
        SELECT app, window_title, start_time, end_time, duration
        FROM activities
        ORDER BY end_time DESC
        LIMIT 1
    """).fetchone()

    if row is None:
        return {"tracking": False, "current": None, "last_seen": None}

    app_name, window_title, start_time, end_time, duration = row
    age = datetime.now().timestamp() - end_time
    live = age <= LIVE_SESSION_WINDOW

    current = {
        "app": app_name,
        "window_title": window_title or "",
        "label": queries.describe(app_name, window_title),
        "category": queries.category_map(connection).get(
            app_name, db.DEFAULT_CATEGORY
        ),
        "is_idle": app_name == db.IDLE_APP,
        "seconds": duration,
        "start": datetime.fromtimestamp(start_time).isoformat(timespec="seconds"),
    }

    return {
        "tracking": live,
        "current": current if live else None,
        "last_seen": datetime.fromtimestamp(end_time).isoformat(timespec="seconds"),
        "seconds_since_last_write": round(age, 1),
    }
