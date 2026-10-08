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

# Load .env before importing ai_categorizer so GEMINI_MODEL is read
# from the .env file, not from the environment before dotenv loads.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import db
import queries
import privacy
import ai_categorizer

# Vite and Create React App defaults, so the dashboard can call the API during
# development while it is served from its own dev server.
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]

# Hosted previews of the dashboard are served from a different origin and proxy
# their API calls back here, so they need to be allowed explicitly. Anchored at
# both ends so a lookalike domain cannot match.
PREVIEW_ORIGIN_PATTERN = r"https://[\w.-]+\.(pplx\.app|perplexity\.ai)"

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
    allow_origin_regex=PREVIEW_ORIGIN_PATTERN,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_connection():
    """One connection per request.

    SQLite connections cannot be shared across threads, and uvicorn serves
    requests from a thread pool, so a single module-level connection would
    intermittently raise. Setup and teardown of this dependency also land on
    different threadpool threads, which is why the thread check is relaxed —
    see `db.connect`.
    """

    connection = db.connect(same_thread_only=False)

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


class CategorizeRequest(BaseModel):
    date: str | None = Field(None, description="YYYY-MM-DD, defaults to today")


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


def _gather_day_activity(connection, day: str | None):
    """Collect and sanitize activity records for a day.

    Returns (records, skipped_count) where records is a list of dicts with
    id, app, title, and duration_seconds. Sensitive apps/titles are skipped.
    """

    rows = connection.execute(
        """
        SELECT id, app, window_title, duration
        FROM activities
        WHERE date(start_time, 'unixepoch', 'localtime') = ?
          AND app != ?
        ORDER BY duration DESC
        """,
        (day or queries.today(), db.IDLE_APP),
    ).fetchall()

    records = []
    skipped = 0

    for activity_id, app_name, window_title, duration in rows:
        safe = privacy.prepare_for_ai(app_name, window_title or "", duration or 0)
        if safe:
            records.append(
                {
                    "id": activity_id,
                    "app": safe["app"],
                    "title": safe["title"],
                    "duration_seconds": safe["duration_seconds"],
                }
            )
        else:
            skipped += 1

    return records, skipped


@app.post("/api/ai/preview")
def ai_preview(
    request: CategorizeRequest,
    connection=Depends(get_connection),
):
    """Preview what would be sent to Gemini without actually calling it.

    Returns the sanitized records and counts so the dashboard can show a
    confirmation dialog before the user approves the AI request.
    """

    day = valid_day(request.date)
    records, skipped = _gather_day_activity(connection, day)

    if not records:
        raise HTTPException(status_code=404, detail="no activity found for this date")

    # Return only a sample for the preview, plus the full count.
    sample = records[:5]

    return {
        "date": day or queries.today(),
        "total_records": len(records),
        "skipped_sensitive": skipped,
        "sample": [
            {
                "app": r["app"],
                "title": r["title"][:80],
                "duration_seconds": r["duration_seconds"],
            }
            for r in sample
        ],
    }


@app.post("/api/ai/categorize")
def ai_categorize(
    request: CategorizeRequest,
    connection=Depends(get_connection),
):
    """Categorize activity records for a day using Gemini.

    Sends only sanitized app names and window titles to Gemini. Returns
    suggested categories per record with confidence scores. Results are
    cached in ai_classifications so repeated calls don't re-query Gemini.
    """

    day = valid_day(request.date)
    records, skipped = _gather_day_activity(connection, day)

    if not records:
        raise HTTPException(status_code=404, detail="no activity found for this date")

    # Check the cache: which activity IDs already have a classification?
    # SQLite has a default limit of 999 bound parameters per query, so
    # chunk large days into batches of 500 IDs per lookup.
    cached = {}
    activity_ids = [r["id"] for r in records]
    CHUNK_SIZE = 500

    for i in range(0, len(activity_ids), CHUNK_SIZE):
        chunk = activity_ids[i : i + CHUNK_SIZE]
        placeholders = ",".join("?" * len(chunk))
        cached_rows = connection.execute(
            f"""
            SELECT ac.activity_id, ac.app, ac.title, ac.category, ac.confidence, ac.reason
            FROM ai_classifications ac
            WHERE ac.activity_id IN ({placeholders})
            """,
            chunk,
        ).fetchall()

        for activity_id, app, title, category, confidence, reason in cached_rows:
            cached[activity_id] = {
                "id": activity_id,
                "app": app,
                "title": title or "",
                "category": category,
                "confidence": confidence,
                "reason": reason,
                "source": "cache",
            }

    # Records not in the cache need to be sent to Gemini.
    uncached = [r for r in records if r["id"] not in cached]

    new_classifications = []

    if uncached:
        try:
            new_classifications = ai_categorizer.categorize_activities(uncached)

            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            for item in new_classifications:
                connection.execute(
                    """
                    INSERT INTO ai_classifications
                        (activity_id, app, title, category, confidence, reason, model_name, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(activity_id) DO UPDATE SET
                        category = excluded.category,
                        confidence = excluded.confidence,
                        reason = excluded.reason,
                        model_name = excluded.model_name,
                        created_at = excluded.created_at
                    """,
                    (
                        item["id"],
                        item["app"],
                        item["title"],
                        item["category"],
                        item["confidence"],
                        item["reason"],
                        ai_categorizer.MODEL_NAME,
                        now,
                    ),
                )
            connection.commit()
        except ai_categorizer.GeminiConfigError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502, detail=f"Gemini request failed: {exc}"
            ) from exc

    # Merge cached + new results.
    all_results = list(cached.values())
    for item in new_classifications:
        all_results.append(
            {
                "id": item["id"],
                "app": item["app"],
                "title": item["title"],
                "category": item["category"],
                "confidence": item["confidence"],
                "reason": item["reason"],
                "source": "gemini",
            }
        )

    return {
        "date": day or queries.today(),
        "results": all_results,
        "skipped_sensitive": skipped,
        "total_records": len(records),
    }


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
