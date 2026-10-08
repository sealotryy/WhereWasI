"""Gemini-powered categorization for WhereWasI.

Takes sanitized app/window-title records from the activity database, sends them
to Gemini with a structured-output request, validates the response, and returns
suggested categories per app.

The Gemini API key is read from the environment. If it is missing, a clear
error is raised so the API endpoint can return a helpful message to the
dashboard.
"""

import os

# Gemini SDK is imported lazily inside _client() so the API still loads
# even when google-genai is not installed. The endpoint only fails when
# the user actually triggers a categorization request.

# Fixed category list so the model does not invent new ones.
ALLOWED_CATEGORIES = [
    "Development",
    "School",
    "Work",
    "Finance",
    "Shopping",
    "Communication",
    "Entertainment",
    "News",
    "Travel",
    "Health",
    "Social",
    "Reading",
    "Other",
]

MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

PROMPT = f"""You categorize computer application usage using privacy-minimized metadata.

Return valid JSON only. Use exactly this structure:
{{
  "classifications": [
    {{
      "app": "<app name exactly as provided>",
      "category": "<one of the allowed categories>",
      "confidence": <number 0 to 1>,
      "reason": "<short explanation, max 20 words>"
    }}
  ]
}}

Allowed categories: {", ".join(ALLOWED_CATEGORIES)}.

Rules:
- Use the app name and window title to pick the best category.
- Do not infer sensitive personal attributes.
- If the metadata is ambiguous, use "Other" with low confidence.
- confidence must be a number from 0.0 to 1.0.
- reason must be a short string, at most 20 words.
- Classify each unique app once. If the same app appears multiple times, use the most representative title.

Activity records:
"""


class GeminiConfigError(Exception):
    """Raised when the Gemini API key is not configured."""


def _client():
    """Create a Gemini client or raise a clear error if the key is missing."""

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if not api_key:
        raise GeminiConfigError(
            "GEMINI_API_KEY is not set. Add it to .env or your environment."
        )

    try:
        from google import genai
        from google.genai.types import HttpOptions
    except ImportError as exc:
        raise GeminiConfigError(
            "google-genai package is not installed. Run: pip install google-genai"
        ) from exc

    return genai.Client(api_key=api_key, http_options=HttpOptions(timeout=60_000))


def categorize_apps(records: list[dict]) -> list[dict]:
    """Send sanitized activity records to Gemini and return classifications.

    Each record in `records` should have: app, title, duration_seconds.
    Returns a list of {app, category, confidence, reason} dicts.

    Raises GeminiConfigError if the API key is missing, or a RuntimeError
    if the model response cannot be parsed.
    """

    if not records:
        return []

    client = _client()

    try:
        from google.genai.types import GenerateContentConfig
    except ImportError as exc:
        raise GeminiConfigError(
            "google-genai package is not installed. Run: pip install google-genai"
        ) from exc

    # Deduplicate by app name, keeping the longest title (most informative).
    best_per_app: dict[str, dict] = {}
    for record in records:
        app = record["app"]
        if app not in best_per_app or len(record["title"]) > len(best_per_app[app]["title"]):
            best_per_app[app] = record

    payload = [
        {
            "app": r["app"],
            "title": r["title"],
            "duration_seconds": r["duration_seconds"],
        }
        for r in best_per_app.values()
    ]

    full_prompt = PROMPT + _format_activity(payload)

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=full_prompt,
        config=GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "classifications": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "app": {"type": "string"},
                                "category": {"type": "string"},
                                "confidence": {"type": "number"},
                                "reason": {"type": "string"},
                            },
                            "required": ["app", "category", "confidence", "reason"],
                        },
                    }
                },
                "required": ["classifications"],
            },
        ),
    )

    text = response.text or ""

    import json

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini response was not valid JSON: {exc}") from exc

    classifications = data.get("classifications", [])

    # Validate each classification against the allowed category list.
    valid = []
    for item in classifications:
        category = item.get("category", "Other")
        if category not in ALLOWED_CATEGORIES:
            category = "Other"

        confidence = item.get("confidence", 0.5)
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence = 0.5

        valid.append(
            {
                "app": item.get("app", ""),
                "category": category,
                "confidence": confidence,
                "reason": item.get("reason", "")[:160],
            }
        )

    return valid


def _format_activity(payload: list[dict]) -> str:
    """Render the activity records as readable text for the prompt."""

    lines = []
    for item in payload:
        lines.append(
            f"app: {item['app']}\n"
            f"title: {item['title']}\n"
            f"duration_seconds: {item['duration_seconds']}"
        )
    return "\n\n".join(lines)
