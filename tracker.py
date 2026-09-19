import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime

# How often we poll the frontmost application, in seconds.
POLL_INTERVAL = 1

# How often we write the in-progress session to the database, in seconds.
# This is what stops a long uninterrupted block from being lost if the
# tracker is killed or the machine sleeps before the next app switch.
FLUSH_INTERVAL = 30

# Category assigned to apps we have not classified yet. The tracker never
# blocks to ask; categorization happens later in the viewer/dashboard.
DEFAULT_CATEGORY = "Uncategorized"


connection = sqlite3.connect("activity.db")
cursor = connection.cursor()


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


## register an app we have not seen before so the dashboard can
## offer it up for categorization later
def ensure_app_known(app):
    cursor.execute(
        "INSERT OR IGNORE INTO app_categories (app, category) VALUES (?, ?)",
        (app, DEFAULT_CATEGORY)
    )
    connection.commit()


## look up an app's category without ever prompting
def get_category(app):
    cursor.execute(
        "SELECT category FROM app_categories WHERE app = ?",
        (app,)
    )

    result = cursor.fetchone()

    return result[0] if result else DEFAULT_CATEGORY


## open a new session row and return its id, so we can keep
## updating it in place while the app stays in the foreground
def open_session(app, start_time):
    cursor.execute(
        "INSERT INTO activities (app, start_time, end_time, duration) VALUES (?, ?, ?, ?)",
        (app, start_time, start_time, 0.0)
    )
    connection.commit()

    return cursor.lastrowid


## bring an open session row up to date with the current wall clock
def update_session(session_id, start_time, end_time):
    cursor.execute(
        "UPDATE activities SET end_time = ?, duration = ? WHERE id = ?",
        (end_time, end_time - start_time, session_id)
    )
    connection.commit()


def format_session(app, start_time, end_time, category):
    start_readable = datetime.fromtimestamp(start_time)
    end_readable = datetime.fromtimestamp(end_time)
    duration = end_time - start_time

    return (
        f"{app}: "
        f"{start_readable.strftime('%I:%M:%S %p')} → "
        f"{end_readable.strftime('%I:%M:%S %p')} "
        f"({duration:.2f} seconds) - {category}"
    )


previous_app = get_current_app()
start_time = time.time()
last_flush = start_time

ensure_app_known(previous_app)
session_id = open_session(previous_app, start_time)

print("Started tracking:", previous_app)


## make sure a Ctrl-C or a shutdown signal still records the
## session that is currently in progress
def handle_exit(signum, frame):
    end_time = time.time()
    update_session(session_id, start_time, end_time)

    print()
    print(format_session(previous_app, start_time, end_time, get_category(previous_app)))
    print("Stopped tracking.")

    connection.close()
    sys.exit(0)


signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)


while True:
    current_app = get_current_app()

    # osascript can briefly return nothing (for example during a
    # Spaces switch). Treat that as "no change" rather than a new app.
    if not current_app:
        time.sleep(POLL_INTERVAL)
        continue

    if current_app != previous_app:
        # Stamp the end of the session before doing any other work, so
        # nothing that happens afterwards inflates the recorded duration.
        end_time = time.time()

        update_session(session_id, start_time, end_time)

        print(format_session(previous_app, start_time, end_time, get_category(previous_app)))

        previous_app = current_app
        start_time = end_time
        last_flush = end_time

        ensure_app_known(current_app)
        session_id = open_session(current_app, start_time)

    elif time.time() - last_flush >= FLUSH_INTERVAL:
        # Same app still in the foreground: keep the open row current so
        # a long session survives an unexpected exit.
        now = time.time()
        update_session(session_id, start_time, now)
        last_flush = now

    time.sleep(POLL_INTERVAL)
