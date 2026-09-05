import json

import httpx

from app.core.config import settings

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent"


def _build_prompt(raw_text: str) -> str:
    return (
        "Extract the company name, role title, application stage, and any "
        "deadline mentioned in the email below. Return null for anything "
        "not present in the text.\n\n"
        f"Email:\n{raw_text}"
    )


def extract_email_details(raw_text: str) -> dict:
    response = httpx.post(
        f"{GEMINI_ENDPOINT}?key={settings.gemini_api_key}",
        json={
            "contents": [
                {"parts": [{"text": _build_prompt(raw_text)}]}
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "response_schema": {
                    "type": "OBJECT",
                    "properties": {
                        "company_name": {"type": "STRING", "nullable": True},
                        "role_title": {"type": "STRING", "nullable": True},
                        "stage": {"type": "STRING", "nullable": True},
                        "deadline": {"type": "STRING", "nullable": True},
                    },
                },
            },
        },
        timeout=15.0,
    )
    response.raise_for_status()
    result = response.json()
    raw_json_text = result["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(raw_json_text)