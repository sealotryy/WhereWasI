import signal
import sys
import time
from datetime import datetime

import db
import macos

# How often we poll the frontmost application, in seconds.
POLL_INTERVAL = 1

# How often we write the in-progress session to the database, in seconds.
# This is what stops a long uninterrupted block from being lost if the
# tracker is killed or the machine sleeps before the next app switch.
FLUSH_INTERVAL = 30

# How long without input before we stop crediting time to the foreground app.
# Two minutes is long enough to read a page without being marked away.
IDLE_THRESHOLD = 120


connection = db.connect()
cursor = connection.cursor()


## register an app we have not seen before so the viewer can
## offer it up for categorization later
def ensure_app_known(app):
    cursor.execute(
        "INSERT OR IGNORE INTO app_categories (app, category) VALUES (?, ?)",
        (app, db.DEFAULT_CATEGORY)
    )
    connection.commit()


## look up an app's category without ever prompting
def get_category(app):
    cursor.execute("SELECT category FROM app_categories WHERE app = ?", (app,))
    result = cursor.fetchone()

    return result[0] if result else db.DEFAULT_CATEGORY


## open a new session row and return its id, so we can keep
## updating it in place while the session stays current
def open_session(app, window_title, start_time):
    cursor.execute(
        """INSERT INTO activities (app, window_title, start_time, end_time, duration)
           VALUES (?, ?, ?, ?, ?)""",
        (app, window_title, start_time, start_time, 0.0)
    )
    connection.commit()

    return cursor.lastrowid


## bring an open session row up to date with the current wall clock
def update_session(session_id, start_time, end_time):
    # end_time can never precede start_time, which matters when we retroactively
    # close a session at the moment input stopped.
    end_time = max(end_time, start_time)

    cursor.execute(
        "UPDATE activities SET end_time = ?, duration = ? WHERE id = ?",
        (end_time, end_time - start_time, session_id)
    )
    connection.commit()


def describe(app, window_title):
    if app == db.IDLE_APP:
        return "Idle"

    return f"{app} - {window_title}" if window_title else app


def format_session(app, window_title, start_time, end_time, category):
    start_readable = datetime.fromtimestamp(start_time)
    end_readable = datetime.fromtimestamp(max(end_time, start_time))
    duration = max(end_time - start_time, 0)

    return (
        f"{describe(app, window_title)}: "
        f"{start_readable.strftime('%I:%M:%S %p')} → "
        f"{end_readable.strftime('%I:%M:%S %p')} "
        f"({duration:.2f} seconds) - {category}"
    )


class Tracker:
    def __init__(self):
        self.app = None
        self.window_title = ""
        self.start_time = None
        self.session_id = None
        self.last_flush = None

    def start_session(self, app, window_title, start_time):
        if app != db.IDLE_APP:
            ensure_app_known(app)

        self.app = app
        self.window_title = window_title
        self.start_time = start_time
        self.session_id = open_session(app, window_title, start_time)
        self.last_flush = start_time

    def close_session(self, end_time, announce=True):
        if self.session_id is None:
            return

        update_session(self.session_id, self.start_time, end_time)

        if announce:
            print(format_session(
                self.app, self.window_title,
                self.start_time, end_time,
                get_category(self.app)
            ))

        self.session_id = None

    def flush(self, now):
        if self.session_id is None:
            return

        update_session(self.session_id, self.start_time, now)
        self.last_flush = now

    def is_current(self, app, window_title):
        return self.session_id is not None and (self.app, self.window_title) == (app, window_title)


tracker = Tracker()

app, window_title = macos.get_frontmost()

if app:
    tracker.start_session(app, window_title, time.time())
    print("Started tracking:", describe(app, window_title))
else:
    # Could not read the foreground app at all. Almost always a missing
    # Accessibility permission, so say so instead of looping silently.
    print("Could not read the frontmost application.")
    print("Grant Accessibility permission in System Settings > Privacy & Security.")
    print("Waiting for the foreground app to become readable...")


## make sure a Ctrl-C or a shutdown signal still records the
## session that is currently in progress
def handle_exit(signum, frame):
    tracker.close_session(time.time())

    print()
    print("Stopped tracking.")

    connection.close()
    sys.exit(0)


signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)


while True:
    now = time.time()
    idle_seconds = macos.get_idle_seconds()

    if idle_seconds >= IDLE_THRESHOLD:
        # The user stopped interacting roughly `idle_seconds` ago, so the
        # active session ended then, not now. Without this, leaving the
        # laptop open on an editor would record hours of "Coding".
        if tracker.app != db.IDLE_APP:
            tracker.close_session(now - idle_seconds)
            tracker.start_session(db.IDLE_APP, "", now - idle_seconds)
        elif now - tracker.last_flush >= FLUSH_INTERVAL:
            tracker.flush(now)

        time.sleep(POLL_INTERVAL)
        continue

    app, window_title = macos.get_frontmost()

    # osascript can briefly return nothing, for example during a Spaces
    # switch. Treat that as "no change" rather than as a new app.
    if not app:
        time.sleep(POLL_INTERVAL)
        continue

    if tracker.app == db.IDLE_APP:
        # Input resumed. End the idle stretch now so the gap is accounted
        # for, and start crediting the foreground app again.
        tracker.close_session(now)
        tracker.start_session(app, window_title, now)

    elif not tracker.is_current(app, window_title):
        # Stamp the end of the session before doing any other work, so
        # nothing that happens afterwards inflates the recorded duration.
        tracker.close_session(now)
        tracker.start_session(app, window_title, now)

    elif now - tracker.last_flush >= FLUSH_INTERVAL:
        # Same session still current: keep the open row up to date so a long
        # stretch survives an unexpected exit.
        tracker.flush(now)

    time.sleep(POLL_INTERVAL)
