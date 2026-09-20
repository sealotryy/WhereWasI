"""Command-line view of tracked activity.

This is only presentation. All reading and aggregation lives in queries.py so
the same numbers can be served over HTTP later without duplicating the logic.

Usage:
    python view_data.py                 # today
    python view_data.py 2026-09-19      # a specific day
    python view_data.py --week          # last 7 days
    python view_data.py --days          # which days have data
"""

import sys

import db
import queries

TITLES_PER_APP = 5


def format_duration(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    remainder = seconds % 60

    if hours:
        return f"{hours}h {minutes}m"

    return f"{minutes}m {remainder:.1f}s"


def prompt_for_categories(connection):
    pending = queries.uncategorized_apps(connection)

    if not pending:
        return

    print(f"{len(pending)} app(s) still need a category. Press Enter to skip any.")

    for app in pending:
        category = input(f"What category should {app} belong to? ").strip()

        if category:
            queries.set_category(connection, app, category)

    print()


def print_timeline(connection, day):
    sessions = queries.timeline(connection, day)
    shown = [s for s in sessions if s["seconds"] >= queries.MIN_DISPLAY_SECONDS]

    print("===== TIMELINE =====")

    if not sessions:
        print("(nothing recorded)")
        return

    for session in shown:
        start = session["start"][11:19]
        end = session["end"][11:19]

        print(
            f"{start} → {end}  "
            f"{format_duration(session['seconds']):>12}  "
            f"{session['label']}  [{session['category']}]"
        )

    hidden = len(sessions) - len(shown)

    if hidden:
        print(f"({hidden} session(s) under {queries.MIN_DISPLAY_SECONDS}s hidden)")


def print_summary(connection, day):
    summary = queries.daily_summary(connection, day, titles_per_app=TITLES_PER_APP)

    if not summary["active_seconds"]:
        print("\nNo active time recorded for this day.")

        if summary["idle_seconds"]:
            print(f"Idle: {format_duration(summary['idle_seconds'])}")

        return

    print("\n===== TOTAL TIME BY APP =====")

    for app in summary["apps"]:
        print(
            f"{app['app']}: {format_duration(app['seconds'])} "
            f"({app['share']}%) - {app['category']}"
        )

        ## window titles are what make an app's time interpretable
        for title in app["titles"]:
            print(
                f"    {title['title']}: {format_duration(title['seconds'])} "
                f"({title['share_of_app']:.0f}%)"
            )

    print("\n===== TOTAL TIME BY CATEGORY =====")

    for category in summary["categories"]:
        print(
            f"{category['category']}: {format_duration(category['seconds'])} "
            f"({category['share']}%)"
        )

    print(f"\nActive time: {format_duration(summary['active_seconds'])}")

    if summary["idle_seconds"]:
        share = (summary["idle_seconds"] / summary["tracked_seconds"]) * 100
        print(
            f"Idle time:   {format_duration(summary['idle_seconds'])} "
            f"({share:.1f}% of {format_duration(summary['tracked_seconds'])} tracked)"
        )


def print_week(connection):
    totals = queries.daily_totals(connection, days=7)
    categories = queries.category_totals(connection, days=7)

    print("===== LAST 7 DAYS =====")

    busiest = max((day["active_seconds"] for day in totals), default=0)

    for day in totals:
        # Simple inline bar so trends are visible without a charting library.
        width = int((day["active_seconds"] / busiest) * 30) if busiest else 0
        bar = "#" * width

        print(f"{day['date']}  {format_duration(day['active_seconds']):>10}  {bar}")

    if categories["active_seconds"]:
        print("\n===== CATEGORIES THIS WEEK =====")

        for category in categories["categories"]:
            print(
                f"{category['category']}: {format_duration(category['seconds'])} "
                f"({category['share']}%)"
            )

        print(f"\nTotal active: {format_duration(categories['active_seconds'])}")


def main(argv):
    connection = db.connect()

    try:
        if "--days" in argv:
            days = queries.tracked_days(connection)
            print("Days with recorded activity:")

            for day in days or []:
                print(" ", day)

            if not days:
                print("  (none yet)")

            return

        prompt_for_categories(connection)

        if "--week" in argv:
            print_week(connection)
            return

        day = next((arg for arg in argv if not arg.startswith("-")), queries.today())

        print(f"Activity for {day}\n")
        print_timeline(connection, day)
        print_summary(connection, day)
    finally:
        connection.close()


if __name__ == "__main__":
    main(sys.argv[1:])
