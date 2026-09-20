"""Read and aggregate tracked activity.

Every function here takes an open connection and returns plain Python data
(dicts, lists, strings, floats) that is JSON-serializable as is. Nothing in
this module prints, so the CLI viewer, an HTTP API, and any future dashboard
can all share it without one of them dragging in the others' concerns.

Durations are seconds (float). Timestamps are returned both as raw epoch
floats, for clients that want to do their own math, and as ISO 8601 local
strings, for clients that just want to display them.
"""

from datetime import datetime, timedelta

import db

# Sessions shorter than this are noise from tabbing through apps. They stay in
# the database and still count toward totals; callers may hide them from lists.
MIN_DISPLAY_SECONDS = 2


def _iso(timestamp):
    return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")


def today():
    return datetime.now().strftime("%Y-%m-%d")


def describe(app, window_title):
    """Human-readable label for a session."""

    if app == db.IDLE_APP:
        return "Idle"

    return f"{app} - {window_title}" if window_title else app


def category_map(connection):
    """Every known app mapped to its category."""

    return dict(connection.execute("SELECT app, category FROM app_categories"))


def uncategorized_apps(connection):
    """Apps that need classifying.

    Covers both apps explicitly marked Uncategorized and apps that appear in
    activities without any app_categories row at all. The second case happens
    for data recorded before the app was registered, and those rows would
    otherwise be stuck as Uncategorized forever because nothing ever offered
    them up to be named.
    """

    rows = connection.execute("""
        SELECT DISTINCT a.app
        FROM activities a
        LEFT JOIN app_categories c ON c.app = a.app
        WHERE a.app != ?
          AND (c.category IS NULL OR c.category = ?)

        UNION

        SELECT app
        FROM app_categories
        WHERE category = ? AND app != ?

        ORDER BY 1
    """, (db.IDLE_APP, db.DEFAULT_CATEGORY, db.DEFAULT_CATEGORY, db.IDLE_APP))

    return [row[0] for row in rows]


def set_category(connection, app, category):
    """Classify an app. Also registers it if the tracker has not seen it yet."""

    connection.execute(
        """INSERT INTO app_categories (app, category) VALUES (?, ?)
           ON CONFLICT(app) DO UPDATE SET category = excluded.category""",
        (app, category)
    )
    connection.commit()


def tracked_days(connection):
    """Dates that have any recorded activity, newest first."""

    rows = connection.execute("""
        SELECT DISTINCT DATE(start_time, 'unixepoch', 'localtime') AS day
        FROM activities
        ORDER BY day DESC
    """)

    return [row[0] for row in rows]


def timeline(connection, day=None, min_seconds=0):
    """Ordered sessions for a single day."""

    day = day or today()
    categories = category_map(connection)

    rows = connection.execute("""
        SELECT app, window_title, start_time, end_time, duration
        FROM activities
        WHERE DATE(start_time, 'unixepoch', 'localtime') = ?
          AND duration >= ?
        ORDER BY start_time
    """, (day, min_seconds))

    return [
        {
            "app": app,
            "window_title": window_title or "",
            "label": describe(app, window_title),
            "category": categories.get(app, db.DEFAULT_CATEGORY),
            "is_idle": app == db.IDLE_APP,
            "start": _iso(start_time),
            "end": _iso(end_time),
            "start_time": start_time,
            "end_time": end_time,
            "seconds": duration,
        }
        for app, window_title, start_time, end_time, duration in rows
    ]


def _share(part, whole):
    return round((part / whole) * 100, 1) if whole else 0.0


def daily_summary(connection, day=None, titles_per_app=None):
    """Totals for a single day, broken down by app, window title, and category.

    Idle time is reported separately and excluded from `active_seconds`, so
    percentages describe how focused time was split rather than how the
    wall clock was split.
    """

    day = day or today()
    categories = category_map(connection)

    rows = connection.execute("""
        SELECT app, window_title, SUM(duration)
        FROM activities
        WHERE DATE(start_time, 'unixepoch', 'localtime') = ?
        GROUP BY app, window_title
    """, (day,))

    idle_seconds = 0.0
    app_seconds = {}
    title_seconds = {}
    category_seconds = {}

    for app, window_title, seconds in rows:
        if app == db.IDLE_APP:
            idle_seconds += seconds
            continue

        app_seconds[app] = app_seconds.get(app, 0.0) + seconds

        key = (app, window_title or "(no title)")
        title_seconds[key] = title_seconds.get(key, 0.0) + seconds

        category = categories.get(app, db.DEFAULT_CATEGORY)
        category_seconds[category] = category_seconds.get(category, 0.0) + seconds

    active_seconds = sum(app_seconds.values())

    def ranked(totals):
        return sorted(totals.items(), key=lambda item: item[1], reverse=True)

    apps = []

    for app, seconds in ranked(app_seconds):
        titles = [
            {
                "title": title,
                "seconds": title_sec,
                "share_of_app": _share(title_sec, seconds),
            }
            for (title_app, title), title_sec in ranked(title_seconds)
            if title_app == app
        ]

        apps.append({
            "app": app,
            "category": categories.get(app, db.DEFAULT_CATEGORY),
            "seconds": seconds,
            "share": _share(seconds, active_seconds),
            "titles": titles if titles_per_app is None else titles[:titles_per_app],
        })

    return {
        "date": day,
        "active_seconds": active_seconds,
        "idle_seconds": idle_seconds,
        "tracked_seconds": active_seconds + idle_seconds,
        "apps": apps,
        "categories": [
            {
                "category": category,
                "seconds": seconds,
                "share": _share(seconds, active_seconds),
            }
            for category, seconds in ranked(category_seconds)
        ],
    }


def daily_totals(connection, start_day=None, end_day=None, days=7):
    """Active and idle seconds per day, for trend charts.

    Days with no activity are included with zeroes so a chart does not
    silently skip them.
    """

    end_day = end_day or today()

    if start_day is None:
        end_date = datetime.strptime(end_day, "%Y-%m-%d")
        start_day = (end_date - timedelta(days=days - 1)).strftime("%Y-%m-%d")

    rows = connection.execute("""
        SELECT DATE(start_time, 'unixepoch', 'localtime') AS day,
               SUM(CASE WHEN app = ? THEN 0 ELSE duration END),
               SUM(CASE WHEN app = ? THEN duration ELSE 0 END)
        FROM activities
        WHERE day BETWEEN ? AND ?
        GROUP BY day
    """, (db.IDLE_APP, db.IDLE_APP, start_day, end_day))

    found = {
        day: {"active_seconds": active or 0.0, "idle_seconds": idle or 0.0}
        for day, active, idle in rows
    }

    results = []
    cursor_date = datetime.strptime(start_day, "%Y-%m-%d")
    last_date = datetime.strptime(end_day, "%Y-%m-%d")

    while cursor_date <= last_date:
        day = cursor_date.strftime("%Y-%m-%d")
        totals = found.get(day, {"active_seconds": 0.0, "idle_seconds": 0.0})

        results.append({"date": day, **totals})
        cursor_date += timedelta(days=1)

    return results


def category_totals(connection, start_day=None, end_day=None, days=7):
    """Seconds per category across a date range."""

    end_day = end_day or today()

    if start_day is None:
        end_date = datetime.strptime(end_day, "%Y-%m-%d")
        start_day = (end_date - timedelta(days=days - 1)).strftime("%Y-%m-%d")

    rows = connection.execute("""
        SELECT COALESCE(c.category, ?), SUM(a.duration)
        FROM activities a
        LEFT JOIN app_categories c ON c.app = a.app
        WHERE DATE(a.start_time, 'unixepoch', 'localtime') BETWEEN ? AND ?
          AND a.app != ?
        GROUP BY 1
        ORDER BY 2 DESC
    """, (db.DEFAULT_CATEGORY, start_day, end_day, db.IDLE_APP))

    totals = [{"category": category, "seconds": seconds} for category, seconds in rows]
    overall = sum(item["seconds"] for item in totals)

    for item in totals:
        item["share"] = _share(item["seconds"], overall)

    return {
        "start_date": start_day,
        "end_date": end_day,
        "active_seconds": overall,
        "categories": totals,
    }
