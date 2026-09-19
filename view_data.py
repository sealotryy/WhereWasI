from datetime import datetime

import db

# Glancing at an app for a moment is noise in the timeline. Short sessions are
# still stored and still counted in the totals; they are just not listed.
MIN_DISPLAY_SECONDS = 2

# How many window titles to list per app in the detail breakdown.
TITLES_PER_APP = 5


connection = db.connect()
cursor = connection.cursor()


def format_duration(seconds):
    minutes = int(seconds // 60)
    remainder = seconds % 60

    return f"{minutes}m {remainder:.1f}s"


def describe(app, window_title):
    if app == db.IDLE_APP:
        return "Idle"

    return f"{app} - {window_title}" if window_title else app


## the tracker no longer blocks to ask for categories, so this is where
## anything it recorded as Uncategorized gets classified
def categorize_pending_apps():
    cursor.execute(
        "SELECT app FROM app_categories WHERE category = ? AND app != ? ORDER BY app",
        (db.DEFAULT_CATEGORY, db.IDLE_APP)
    )

    pending = [row[0] for row in cursor.fetchall()]

    if not pending:
        return

    print(f"{len(pending)} app(s) still need a category. Press Enter to skip any.")

    for app in pending:
        category = input(f"What category should {app} belong to? ").strip()

        if not category:
            continue

        cursor.execute(
            "UPDATE app_categories SET category = ? WHERE app = ?", (category, app)
        )
        connection.commit()

    print()


def load_category_map():
    cursor.execute("SELECT app, category FROM app_categories")

    return dict(cursor.fetchall())


def rows_for_day(day):
    cursor.execute("""
        SELECT app, window_title, start_time, end_time, duration
        FROM activities
        WHERE DATE(start_time, 'unixepoch', 'localtime') = ?
        ORDER BY start_time
    """, (day,))

    return cursor.fetchall()


def print_timeline(rows, category_map):
    print("===== TIMELINE =====")

    hidden = 0

    for app, window_title, start_time, end_time, duration in rows:
        if duration < MIN_DISPLAY_SECONDS:
            hidden += 1
            continue

        start_readable = datetime.fromtimestamp(start_time)
        end_readable = datetime.fromtimestamp(end_time)

        print(
            f"{describe(app, window_title)}: "
            f"{start_readable.strftime('%I:%M:%S %p')} → "
            f"{end_readable.strftime('%I:%M:%S %p')} "
            f"({format_duration(duration)}) - "
            f"{category_map.get(app, db.DEFAULT_CATEGORY)}"
        )

    if hidden:
        print(f"({hidden} session(s) under {MIN_DISPLAY_SECONDS}s hidden)")


def print_summary(rows, category_map):
    active = [row for row in rows if row[0] != db.IDLE_APP]
    idle_total = sum(row[4] for row in rows if row[0] == db.IDLE_APP)
    active_total = sum(row[4] for row in active)

    if not active_total:
        print("\nNo active time recorded for this day yet.")

        if idle_total:
            print(f"Idle: {format_duration(idle_total)}")

        return

    app_totals = {}
    title_totals = {}
    category_totals = {}

    for app, window_title, _, _, duration in active:
        app_totals[app] = app_totals.get(app, 0) + duration

        key = (app, window_title or "(no title)")
        title_totals[key] = title_totals.get(key, 0) + duration

        category = category_map.get(app, db.DEFAULT_CATEGORY)
        category_totals[category] = category_totals.get(category, 0) + duration

    def by_value(totals):
        return sorted(totals.items(), key=lambda item: item[1], reverse=True)

    print("\n===== TOTAL TIME BY APP =====")

    ## finds total time by app
    for app, total_duration in by_value(app_totals):
        percentage = (total_duration / active_total) * 100
        category = category_map.get(app, db.DEFAULT_CATEGORY)

        print(f"{app}: {format_duration(total_duration)} ({percentage:.1f}%) - {category}")

        ## the window titles are what make an app's time interpretable,
        ## so break each app down by what was actually on screen
        titles = [
            (title, duration)
            for (title_app, title), duration in by_value(title_totals)
            if title_app == app
        ][:TITLES_PER_APP]

        for title, duration in titles:
            share = (duration / total_duration) * 100
            print(f"    {title}: {format_duration(duration)} ({share:.0f}%)")

    print("\n===== TOTAL TIME BY CATEGORY =====")

    ## finds total time by category
    for category, total_duration in by_value(category_totals):
        percentage = (total_duration / active_total) * 100

        print(f"{category}: {format_duration(total_duration)} ({percentage:.1f}%)")

    print(f"\nActive time: {format_duration(active_total)}")

    if idle_total:
        tracked = active_total + idle_total
        print(
            f"Idle time:   {format_duration(idle_total)} "
            f"({(idle_total / tracked) * 100:.1f}% of {format_duration(tracked)} tracked)"
        )


categorize_pending_apps()

category_map = load_category_map()
today = datetime.now().strftime("%Y-%m-%d")
rows = rows_for_day(today)

print(f"Activity for {today}\n")

print_timeline(rows, category_map)
print_summary(rows, category_map)

connection.close()
