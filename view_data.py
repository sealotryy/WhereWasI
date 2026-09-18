import sqlite3
from datetime import datetime

connection = sqlite3.connect("activity.db")
cursor = connection.cursor()

app_categories = {
    "Electron": "Coding",
    "Opera": "Entertainment",
    "Spotify": "Entertainment",
    "Obsidian": "School",
    "firefox": "Other",
    "Terminal": "Coding"
}

## connect to database 
connection = sqlite3.connect("activity.db")

cursor = connection.cursor()

cursor.execute("SELECT app, category FROM app_categories")

categories = cursor.fetchall()

category_map = dict(categories)

print(categories)

cursor.execute("SELECT app, start_time, end_time, duration FROM activities")

activities = cursor.fetchall()


for app, start_time, end_time, duration in activities:
    start_readable = datetime.fromtimestamp(start_time)
    end_readable = datetime.fromtimestamp(end_time)

    print(
        f"{app}: "
        f"{start_readable.strftime('%I:%M:%S %p')} → "
        f"{end_readable.strftime('%I:%M:%S %p')} "
        f"({duration:.2f} seconds)"
    )

cursor.execute("""
    SELECT app, start_time, DATE(start_time, 'unixepoch')
    FROM activities
""")

dates = cursor.fetchall()

for app, timestamp, date in dates:
    print(app, date)

today = datetime.now().strftime("%Y-%m-%d")

cursor.execute("""
    SELECT SUM(duration)
    FROM activities
    WHERE DATE(start_time, 'unixepoch', 'localtime') = ?
""", (today,))

total_time = cursor.fetchone()[0]

cursor.execute("""
    SELECT app, SUM(duration)
    FROM activities
    WHERE DATE(start_time, 'unixepoch', 'localtime') = ?
    GROUP BY app
""", (today,))

summary = cursor.fetchall()

category_totals = {}

print("\n===== TOTAL TIME BY APP =====")

## finds total time by app
for app, total_duration in summary:
    category = category_map.get(app, "Other")
    category_totals[category] = category_totals.get(category, 0) + total_duration
    minutes = int(total_duration // 60)
    seconds = int(total_duration % 60)

    percentage = (total_duration / total_time) * 100

    print(
        f"{app}: {minutes}m {seconds:.1f}s "
        f"({percentage:.1f}%) - {category}"
    )

print("\n===== TOTAL TIME BY CATEGORY =====")

## finds total time by category
for category, total_duration in category_totals.items():
    minutes = int(total_duration // 60)
    seconds = total_duration % 60
    percentage = (total_duration / total_time) * 100

    print(f"{category}: {minutes}m {seconds:.1f}s ({percentage:.1f}%)")

connection.close()