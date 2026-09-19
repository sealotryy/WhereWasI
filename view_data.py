import sqlite3
from datetime import datetime

DEFAULT_CATEGORY = "Uncategorized"


connection = sqlite3.connect("activity.db")
cursor = connection.cursor()


def format_duration(seconds):
    minutes = int(seconds // 60)
    remainder = seconds % 60

    return f"{minutes}m {remainder:.1f}s"


## the tracker no longer blocks to ask for categories, so this is where
## anything it recorded as Uncategorized gets classified
def categorize_pending_apps():
    cursor.execute(
        "SELECT app FROM app_categories WHERE category = ? ORDER BY app",
        (DEFAULT_CATEGORY,)
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
            "UPDATE app_categories SET category = ? WHERE app = ?",
            (category, app)
        )
        connection.commit()

    print()


def load_category_map():
    cursor.execute("SELECT app, category FROM app_categories")

    return dict(cursor.fetchall())


def print_timeline(category_map):
    cursor.execute("SELECT app, start_time, end_time, duration FROM activities ORDER BY start_time")

    print("===== TIMELINE =====")

    for app, start_time, end_time, duration in cursor.fetchall():
        start_readable = datetime.fromtimestamp(start_time)
        end_readable = datetime.fromtimestamp(end_time)

        print(
            f"{app}: "
            f"{start_readable.strftime('%I:%M:%S %p')} → "
            f"{end_readable.strftime('%I:%M:%S %p')} "
            f"({duration:.2f} seconds) - {category_map.get(app, DEFAULT_CATEGORY)}"
        )


def print_daily_summary(category_map):
    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT app, SUM(duration)
        FROM activities
        WHERE DATE(start_time, 'unixepoch', 'localtime') = ?
        GROUP BY app
        ORDER BY SUM(duration) DESC
    """, (today,))

    summary = cursor.fetchall()

    total_time = sum(duration for _, duration in summary)

    # Guard against a fresh database or a day with no recorded activity,
    # which would otherwise divide by zero below.
    if not total_time:
        print(f"\nNo activity recorded for {today} yet.")
        return

    category_totals = {}

    print("\n===== TOTAL TIME BY APP =====")

    ## finds total time by app
    for app, total_duration in summary:
        category = category_map.get(app, DEFAULT_CATEGORY)
        category_totals[category] = category_totals.get(category, 0) + total_duration
        percentage = (total_duration / total_time) * 100

        print(f"{app}: {format_duration(total_duration)} ({percentage:.1f}%) - {category}")

    print("\n===== TOTAL TIME BY CATEGORY =====")

    ## finds total time by category
    for category, total_duration in sorted(
        category_totals.items(), key=lambda item: item[1], reverse=True
    ):
        percentage = (total_duration / total_time) * 100

        print(f"{category}: {format_duration(total_duration)} ({percentage:.1f}%)")

    print(f"\nTotal tracked today: {format_duration(total_time)}")


categorize_pending_apps()

category_map = load_category_map()

print_timeline(category_map)
print_daily_summary(category_map)

connection.close()
