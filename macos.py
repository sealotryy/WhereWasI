"""macOS system probes: what is in the foreground, and how long the user has
been idle.

Both probes are best-effort. If the system refuses to answer (missing
Accessibility permission, an app with no windows, a Spaces transition) the
caller gets an empty title or zero idle time rather than an exception, so the
tracker keeps running instead of dying mid-session.
"""

import re
import subprocess

# One AppleScript call returns both the app name and its front window title.
# Doing it in two calls would spawn two processes per poll and could catch the
# system mid-switch, reporting a title that belongs to a different app.
_FRONTMOST_SCRIPT = """
tell application "System Events"
    set frontApp to first application process whose frontmost is true
    set appName to name of frontApp
    try
        set windowName to name of front window of frontApp
    on error
        set windowName to ""
    end try
end tell
return appName & linefeed & windowName
"""

_IDLE_PATTERN = re.compile(r'"HIDIdleTime"\s*=\s*(\d+)')

# Some apps report their own name as the window title when no document is
# open, which adds nothing over the app column itself.
_USELESS_TITLES = {"", "Window"}


def _run(command, timeout=5):
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout
        )
    except (subprocess.TimeoutExpired, OSError):
        return ""

    if result.returncode != 0:
        return ""

    return result.stdout


def get_frontmost():
    """Return (app_name, window_title). Either may be an empty string."""

    output = _run(["osascript", "-e", _FRONTMOST_SCRIPT])
    lines = output.splitlines()

    if not lines:
        return "", ""

    app = lines[0].strip()

    # A window title can itself contain newlines, so everything after the
    # first line belongs to the title.
    title = " ".join(part.strip() for part in lines[1:]).strip()

    if title in _USELESS_TITLES or title == app:
        title = ""

    return app, title


def get_idle_seconds():
    """Seconds since the last keyboard or mouse input.

    Returns 0.0 if idle time cannot be determined, which the tracker treats as
    "active" so an unreadable probe never silently discards real activity.
    """

    output = _run(["ioreg", "-c", "IOHIDSystem", "-d", "4"])
    match = _IDLE_PATTERN.search(output)

    if not match:
        return 0.0

    # HIDIdleTime is reported in nanoseconds.
    return int(match.group(1)) / 1_000_000_000
