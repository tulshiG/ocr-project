import base64
import io
import json
import logging
import re

import requests
from django.conf import settings
from PIL import Image

logger = logging.getLogger(__name__)

GEMINI_API_KEY = getattr(settings, "GEMINI_API_KEY", "")
GEMINI_MODEL = getattr(settings, "GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
REQUEST_TIMEOUT = getattr(settings, "GEMINI_REQUEST_TIMEOUT", 60)

MAX_IMAGE_DIMENSION = 1600

SYSTEM_PROMPT = """You are a meticulous document transcriber specializing in handwritten \
Indian vehicle-maintenance work reports. The sheets mix English, Hindi, and Gujarati script, \
and are handwritten by multiple people in varying legibility.

Read the image and return ONLY a single JSON object matching this exact shape:

{
  "location_name": "<the location/depot header written on the sheet, e.g. Vadaj, Paldi, Memco. Empty string if unclear>",
  "report_date": "<the date exactly as written on the sheet, e.g. 7/6/26 or 08-06-2026>",
  "rows": [
    {
      "sr": "<serial number if present, else empty string>",
      "bus_no": "<vehicle/bus code, e.g. TAM17, TCM52, MAC31, TOM4. Transcribe exactly as written>",
      "mech": "<mechanic name if the sheet has a MECH column, else empty string>",
      "work_done": "<the work description, transcribed into readable text. If it's in Gujarati or Hindi script, transcribe it in that script's native text, do not force-translate to English>",
      "material": "<material used, only if the sheet has a MATERIAL column, else empty string>"
    }
  ]
}

Rules:
- One JSON row per table row / line item you can identify, in the order they appear top to bottom.
- If a value is illegible, use "[illegible]" rather than guessing.
- If the sheet has grouped sections under a person's name (e.g. "Kamlesh / Pathak" or "Hotesh / Nilesh"), \
put that name in the "mech" field for the rows under it.
- Do not translate Gujarati/Hindi work descriptions into English — transcribe the original script faithfully.
- Do not omit rows. Do not invent rows that aren't on the sheet.
- Return valid JSON only. No trailing commentary, no markdown fences.
"""


class OCRExtractionError(Exception):
    pass


def _encode_image(image_path: str) -> str:
    """Downscales large photos, then base64-encodes as JPEG."""
    img = Image.open(image_path)
    img = img.convert("RGB")

    if max(img.size) > MAX_IMAGE_DIMENSION:
        ratio = MAX_IMAGE_DIMENSION / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.LANCZOS)
        logger.info(f"Resized image to {new_size}")

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=90)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _call_gemini_vision(image_path: str) -> str:
    if not GEMINI_API_KEY:
        raise OCRExtractionError(
            "GEMINI_API_KEY is not set. Add it to config/settings.py or as an environment variable."
        )

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": SYSTEM_PROMPT},
                    {"inline_data": {"mime_type": "image/jpeg", "data": _encode_image(image_path)}},
                ],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",  # forces Gemini to return valid JSON directly
        },
    }

    try:
        resp = requests.post(
            GEMINI_ENDPOINT,
            params={"key": GEMINI_API_KEY},
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.ConnectionError as e:
        raise OCRExtractionError(f"Could not reach Gemini API — check your internet connection. ({e})")
    except requests.exceptions.Timeout:
        raise OCRExtractionError(f"Gemini request timed out after {REQUEST_TIMEOUT}s.")

    if resp.status_code == 429:
        raise OCRExtractionError(
            "Gemini free-tier rate limit hit (too many requests per minute/day). Wait a bit and retry."
        )
    if resp.status_code == 400:
        raise OCRExtractionError(f"Gemini rejected the request (bad API key or payload?): {resp.text[:500]}")
    if not resp.ok:
        raise OCRExtractionError(f"Gemini returned HTTP {resp.status_code}: {resp.text[:500]}")

    data = resp.json()

    try:
        candidates = data["candidates"]
        parts = candidates[0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError) as e:
        finish_reason = data.get("candidates", [{}])[0].get("finishReason", "unknown")
        raise OCRExtractionError(
            f"Unexpected Gemini response shape (finishReason={finish_reason}). Full payload: {data}"
        )

    if not text:
        raise OCRExtractionError(f"Empty response text from Gemini. Full payload: {data}")

    return text


def _extract_json_block(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text

    first_brace = candidate.find("{")
    last_brace = candidate.rfind("}")
    if first_brace == -1 or last_brace == -1:
        raise OCRExtractionError(f"No JSON object found in model output: {text[:500]}")

    candidate = candidate[first_brace : last_brace + 1]

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        raise OCRExtractionError(f"Model output wasn't valid JSON ({e}). Raw: {candidate[:500]}")


def extract_structured_data(image_path: str) -> dict:
    raw_output = _call_gemini_vision(image_path)
    parsed = _extract_json_block(raw_output)

    rows = parsed.get("rows", [])
    if not isinstance(rows, list):
        raise OCRExtractionError(f"'rows' was not a list: {rows}")

    normalized_rows = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        normalized_rows.append(
            {
                "sr": str(r.get("sr", "")).strip(),
                "bus_no": str(r.get("bus_no", "")).strip(),
                "mech": str(r.get("mech", "")).strip(),
                "work_done": str(r.get("work_done", "")).strip(),
                "material": str(r.get("material", "")).strip(),
            }
        )

    return {
        "location_name": str(parsed.get("location_name", "")).strip(),
        "report_date": str(parsed.get("report_date", "")).strip(),
        "rows": normalized_rows,
        "raw_output": raw_output,
    }