# Work Report OCR (Django + Gemini API)

Handwritten work-report sheets → structured DB rows (SR, Bus No, Mech, Work Done).

## Why this approach

Your sheets are handwritten, mix Gujarati/Hindi/English, have multiple writers, and use
inconsistent table layouts. Classic OCR (PaddleOCR's recognition models, TrOCR) segments
characters/words independently and has no way to use context to resolve messy strokes —
that's why PaddleOCR failed on your handwriting.

This project uses **Gemini 2.5 Flash** (Google's vision-language model) via its free API.
Local inference was tried first, but the dev machine only has Intel UHD integrated graphics
(no dedicated GPU), which makes local VLM inference on CPU impractically slow. Gemini's
free tier requires no credit card and is fast + strong at OCR/handwriting.

Instead of raw OCR text, the model is prompted to directly return structured JSON matching
your table columns, which Django then saves straight into rows.

## Step 1 — Get a free Gemini API key

1. Go to https://aistudio.google.com/apikey
2. Sign in with a Google account, click "Create API key" — no credit card needed
3. Copy the key

Set it as an environment variable (don't hardcode it in settings.py or commit it):

**Windows (PowerShell), each new terminal session:**
```powershell
$env:GEMINI_API_KEY="your-key-here"
```
**Windows, permanently (one-time):**
```powershell
setx GEMINI_API_KEY "your-key-here"
```
(then open a fresh terminal for it to take effect)

**Mac/Linux:**
```bash
export GEMINI_API_KEY="your-key-here"
```

## Step 2 — Set up the Django project

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install django pillow requests
python3 manage.py migrate
python3 manage.py createsuperuser   # optional, for /admin/
python3 manage.py runserver
```

Visit `http://localhost:8000/` — upload an image, it'll process (should take a few
seconds, not minutes, since this is now a cloud call) and show you the extracted
table next to the source image.

## Free tier limits to know

Gemini Flash free tier (as of mid-2026): roughly 10-15 requests/minute and a few
hundred requests/day, no credit card required. Fine for a project like this uploading
sheets one at a time. If you hit a 429 error, it's the rate limit — wait a minute (RPM
limit) or until the next day (RPD limit) and retry. The app will show you this clearly
via the error message rather than a silent failure.

## Step 3 — Iterate on accuracy

The prompt lives in `extractor/services.py` (`SYSTEM_PROMPT`). If extraction misses
columns or mis-splits fields on your specific templates:

1. Open a report's detail page — the raw model JSON is in the "Raw model output" box.
2. Adjust the prompt wording (e.g. add a rule about a column you noticed it's missing).
3. Hit "Re-run extraction" on that report to test the change without re-uploading.

Because prompts are text, you can add few-shot examples straight into `SYSTEM_PROMPT`
if certain layouts (e.g. your Vadaj-style sheet vs. the Paldi/Memco tabular sheets) keep
getting confused — show the model one example row transcription of each.

## Production notes (when you're past testing)

- **Never commit your API key.** It's read from the `GEMINI_API_KEY` environment
  variable, not hardcoded — keep it that way.
- **Add row-level confidence flags.** Extend the prompt to also return a
  `confidence: "low"|"high"` per row and highlight low-confidence rows for human review —
  this handwriting is genuinely hard even for a strong model.
- **Validate `bus_no` against a known vehicle list**, if you have one, as a
  post-processing fuzzy-match step to catch e.g. a scrawled "TAM17" read as "TAM77".
- **Move processing off the request/response cycle** once you have real concurrent
  users — wrap `extract_structured_data()` in a Celery task instead of calling it
  synchronously in the view.

## Project structure

```
ocr_project/
├── config/                # Django project settings/urls
├── extractor/
│   ├── models.py          # WorkReport, WorkReportRow
│   ├── services.py        # Gemini API call + JSON parsing (the core logic)
│   ├── views.py            # upload / process / detail
│   ├── forms.py
│   ├── urls.py
│   ├── admin.py
│   └── templates/extractor/
│       ├── upload.html
│       └── detail.html
└── manage.py
```
