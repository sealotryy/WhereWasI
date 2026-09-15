import time
import subprocess
import sqlite3

connection = sqlite3.connect("activity.db")


connection.commit()

def get_current_app():
    result = subprocess.run(
        [
            "osascript",
            "-e",
            'tell application "System Events" to get name of first application process whose frontmost is true'
        ],
        capture_output=True,
        text=True
    )

    return result.stdout.strip()


# DATABASE SETUP
connection = sqlite3.connect("activity.db")

connection.execute("""
CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app TEXT,
    start_time REAL,
    end_time REAL,
    duration REAL
)
""")

connection.commit()

previous_app = get_current_app()
start_time = time.time()


print("Started tracking:", previous_app)

while True:
    current_app = get_current_app()

    if current_app != previous_app:
        end_time = time.time()

        duration = end_time - start_time

        connection.execute(
        "INSERT INTO activities (app, start_time, end_time, duration) VALUES (?, ?, ?, ?)",
        (previous_app, start_time, end_time, duration)
    )

        connection.commit()

        print(
            f"{previous_app} → {current_app} "
            f"({duration:.2f} seconds)"
        )

        previous_app = current_app
        start_time = end_time

    time.sleep(1)




