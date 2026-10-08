"""Gemini-powered categorization for WhereWasI.

Takes sanitized activity records (app + window title + duration) from the
activity database, sends them to Gemini with a structured-output request,
validates the response, and returns suggested categories per record.

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

MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

# Maximum records sent to Gemini in a single request. Larger days are
# batched to stay within token limits and keep response times reasonable.
MAX_BATCH_SIZE = 40

PROMPT = f"""You categorize computer activity by window title using privacy-minimized metadata.

Return valid JSON only. Use exactly this structure:
{{
  "classifications": [
    {{
      "id": <integer, matching the input id>,
      "category": "<one of the allowed categories>",
      "confidence": <number 0.0 to 1.0>,
      "reason": "<short explanation, max 20 words>"
    }}
  ]
}}

Allowed categories: {", ".join(ALLOWED_CATEGORIES)}.

Rules:
- Use the app name and window title to pick the best category for each record.
- Do not infer sensitive personal attributes.
- If the metadata is ambiguous, use "Other" with low confidence.
- confidence must be a number from 0.0 to 1.0.
- reason must be a short string, at most 20 words.
- Classify every record by its id. Do not skip any.

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


def categorize_activities(records: list[dict]) -> list[dict]:
    """Send sanitized activity records to Gemini and return classifications.

    Each record should have: id, app, title, duration_seconds.
    Returns a list of {id, app, category, confidence, reason} dicts.

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

    all_results = []

    # Process in batches to stay within token limits.
    for batch_start in range(0, len(records), MAX_BATCH_SIZE):
        batch = records[batch_start : batch_start + MAX_BATCH_SIZE]

        payload = [
            {
                "id": r["id"],
                "app": r["app"],
                "title": r["title"],
                "duration_seconds": r["duration_seconds"],
            }
            for r in batch
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
                                    "id": {"type": "integer"},
                                    "category": {"type": "string"},
                                    "confidence": {"type": "number"},
                                    "reason": {"type": "string"},
                                },
                                "required": ["id", "category", "confidence", "reason"],
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

        # Build a lookup from the batch so we can attach the app name.
        id_to_record = {r["id"]: r for r in batch}

        for item in classifications:
            record_id = item.get("id")
            record = id_to_record.get(record_id)

            category = item.get("category", "Other")
            if category not in ALLOWED_CATEGORIES:
                category = "Other"

            confidence = item.get("confidence", 0.5)
            try:
                confidence = max(0.0, min(1.0, float(confidence)))
            except (TypeError, ValueError):
                confidence = 0.5

            all_results.append(
                {
                    "id": record_id,
                    "app": record["app"] if record else "",
                    "title": record["title"] if record else "",
                    "category": category,
                    "confidence": confidence,
                    "reason": item.get("reason", "")[:160],
                }
            )

    return all_results


def _format_activity(payload: list[dict]) -> str:
    """Render the activity records as readable text for the prompt."""

    lines = []
    for item in payload:
        lines.append(
            f"id: {item['id']}\n"
            f"app: {item['app']}\n"
            f"title: {item['title']}\n"
            f"duration_seconds: {item['duration_seconds']}"
        )
    return "\n\n".join(lines)
