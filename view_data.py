import sqlite3
from datetime import datetime

## connect to database 
connection = sqlite3.connect("activity.db")

cursor = connection.cursor()

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
    SELECT app, SUM(duration)
    FROM activities
    GROUP BY app
""")

summary = cursor.fetchall()

print("\n===== TOTAL TIME BY APP =====")

for app, total_duration in summary:
    print(f"{app}: {total_duration:.2f} seconds")

connection.close()