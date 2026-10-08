"""Privacy helpers for the AI categorization feature.

Before any window title or app name leaves the machine for Gemini, it passes
through here. The goal is to strip obviously sensitive information so that the
classification request contains only what is needed to categorize activity.

This is defense-in-depth, not a guarantee. The user must still opt in via the
dashboard button before anything is sent.
"""

import re

# App names or window titles containing these substrings are never sent to
# Gemini. This covers banking, email, password managers, cloud drives, health
# portals, government sites, and local/private addresses. Case-insensitive.
SENSITIVE_PATTERNS = [
    "bank",
    "chase",
    "wells fargo",
    "citibank",
    "american express",
    "paypal",
    "venmo",
    "zelle",
    "password",
    "1password",
    "lastpass",
    "bitwarden",
    "keeper",
    "dashlane",
    "gmail",
    "outlook",
    "protonmail",
    "icloud mail",
    "drive.google.com",
    "dropbox",
    "onedrive",
    "icloud drive",
    "box.com",
    "portal.hrsa",
    "health",
    "medical",
    "patient",
    "mychart",
    "epic",
    "cigna",
    "kaiser",
    "blue cross",
    "aetna",
    "medicare",
    "medicaid",
    "irs.gov",
    "ssa.gov",
    "dmv",
    "passport",
    "login",
    "signin",
    "sso",
    "oauth",
    "token",
    "auth",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "file://",
    "file:",
]

# Patterns to strip from window titles before sending. These remove URL
# query strings, fragments, and tracking parameters that might leak sensitive
# data embedded in a title bar.
_URL_QUERY_RE = re.compile(r"\?[^\s]*")
_URL_FRAGMENT_RE = re.compile(r"#[^\s]*")
_URL_WITH_CREDENTIALS_RE = re.compile(r"https?://[^/\s:]+:[^@\s]+@")

# Maximum length for a sanitized window title. Long titles are truncated to
# keep the Gemini request small and focused.
MAX_TITLE_LENGTH = 200


def is_sensitive(text: str) -> bool:
    """Return True if the text contains a sensitive substring."""

    lowered = text.lower()
    return any(pattern in lowered for pattern in SENSITIVE_PATTERNS)


def sanitize_title(title: str) -> str:
    """Strip query strings, fragments, and credentials from a window title.

    Truncates to MAX_TITLE_LENGTH so a very long title does not inflate the
    request. Returns the cleaned title, or an empty string if nothing safe
    remains.
    """

    if not title:
        return ""

    cleaned = _URL_WITH_CREDENTIALS_RE.sub("https://", title)
    cleaned = _URL_QUERY_RE.sub("", cleaned)
    cleaned = _URL_FRAGMENT_RE.sub("", cleaned)
    cleaned = cleaned.strip()

    if len(cleaned) > MAX_TITLE_LENGTH:
        cleaned = cleaned[:MAX_TITLE_LENGTH].rsplit(" ", 1)[0] or cleaned[:MAX_TITLE_LENGTH]

    return cleaned


def prepare_for_ai(app: str, window_title: str, duration: float) -> dict | None:
    """Build a privacy-safe record for Gemini, or None if it should be skipped.

    Returns a dict with app, title, and duration_seconds. Returns None if the
    app or title is flagged as sensitive.
    """

    combined = f"{app} {window_title or ''}"

    if is_sensitive(combined):
        return None

    sanitized = sanitize_title(window_title or "")

    return {
        "app": app,
        "title": sanitized,
        "duration_seconds": round(duration, 1),
    }
