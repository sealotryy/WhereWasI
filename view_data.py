import sqlite3
from datetime import datetime

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

connection.close()