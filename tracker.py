import time
import subprocess
import sqlite3
from datetime import datetime

connection = sqlite3.connect("activity.db")
cursor = connection.cursor()


## get the name of the current application 
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


connection.execute("""
CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app TEXT,
    start_time REAL,
    end_time REAL,
    duration REAL
)
""")

connection.execute("""
CREATE TABLE IF NOT EXISTS app_categories (
    app TEXT PRIMARY KEY,
    category TEXT
)
""")

connection.commit()

previous_app = get_current_app()
start_time = time.time()


print("Started tracking:", previous_app)

## function to ask user for app category if it doesn't exist yet
def get_category(app):
    cursor.execute(
        "SELECT category FROM app_categories WHERE app = ?",
        (app,)
    )

    result = cursor.fetchone()

    if result is None:
        category = input(f"What category should {app} belong to? ")

        cursor.execute(
            "INSERT INTO app_categories (app, category) VALUES (?, ?)",
            (app, category)
        )

        connection.commit()

        return category

    return result[0]

while True:
    current_app = get_current_app()

    if current_app != previous_app:
        category = get_category(previous_app)
        end_time = time.time()

    

        duration = end_time - start_time

        ## send instructions to SQL 
        connection.execute(
        "INSERT INTO activities (app, start_time, end_time, duration) VALUES (?, ?, ?, ?)",
        (previous_app, start_time, end_time, duration)
    )

        connection.commit()

        start_readable = datetime.fromtimestamp(start_time)
        end_readable = datetime.fromtimestamp(end_time)

        print(
            f"{previous_app}: "
            f"{start_readable.strftime('%I:%M:%S %p')} → "
            f"{end_readable.strftime('%I:%M:%S %p')} "
            f"({duration:.2f} seconds) - {category}"
        )

        previous_app = current_app
        start_time = end_time

    time.sleep(1)




