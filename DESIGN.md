# DESIGN.md --- OCR Work-Report Extraction

## 1. What I built

This project is a Django-based OCR/document extraction application for
handwritten work-report sheets.

The input documents can contain Gujarati, Hindi, and English
handwriting, multiple handwriting styles, and inconsistent table
layouts. The goal is not only to recognize text, but to convert each
report into structured database rows containing:

-   `SR`
-   `Bus No`
-   `Mech`
-   `Work Done`

The application uses Gemini 2.5 Flash as a vision-language model.
Instead of first producing raw OCR text and then trying to reconstruct
the table, the model is prompted to directly return structured JSON
matching the required columns. Django parses that output and saves the
extracted information into database rows.

The core model/API logic is implemented in `extractor/services.py`,
while Django handles upload, processing, detail views, and persistence.

## 2. Why I chose this architecture

I initially considered local OCR/model-based inference. The main
limitation was the development machine: it has Intel UHD integrated
graphics and no dedicated GPU, making local VLM inference on CPU
impractically slow for this use case.

Traditional OCR approaches were also not sufficient for the target
documents. The reports contain difficult handwriting, mixed languages,
multiple writers, and inconsistent layouts. Character/word-level OCR can
struggle when the visual context is needed to interpret ambiguous
strokes.

Gemini 2.5 Flash was therefore selected because it can reason over the
whole document image and return the desired structured representation
directly. The project uses the Gemini free API tier.

## 3. Processing flow

``` text
Handwritten report image
        |
        v
Django upload
        |
        v
extract_structured_data()
        |
        v
Gemini 2.5 Flash vision-language model
        |
        |  Prompt requests structured JSON
        v
JSON parsing / extraction handling
        |
        v
Django models
        |
        v
WorkReport + WorkReportRow
        |
        v
Structured table shown beside source image
```

The current application processes the image during the Django request
flow. For the current testing scale this keeps the implementation
simple, but it is not the architecture I would keep for a larger
production workload.

## 4. Baseline vs. optimized approach

The key optimization is changing the task from:

``` text
Image → raw OCR text → application-side reconstruction → structured fields
```

to:

``` text
Image → vision-language model → structured JSON → database rows
```

The second approach reduces the amount of application-side
reconstruction required and gives the model the complete visual/table
context while extracting the fields that the application actually needs.

For prompt iteration, the application exposes the raw model output on a
report detail page. This makes it possible to identify extraction
failures, update `SYSTEM_PROMPT`, and re-run extraction without
uploading the image again.

Few-shot examples can also be added to the prompt for recurring layouts
such as Vadaj-style sheets or Paldi/Memco tabular sheets.

## 5. Cost and accuracy measurement

The benchmark should be treated as an empirical measurement rather than
an assumed number.

For each evaluated document, I use manually verified ground truth and
compare the extracted structured fields against it. The important
metrics are:

-   document/row extraction accuracy
-   field-level accuracy
-   input/output token usage where available
-   cost per document
-   baseline vs. optimized cost
-   baseline vs. optimized accuracy

**Important:** I have not inserted numerical benchmark claims into this
design document because the supplied project README does not contain the
final benchmark numbers. The final measured values should be taken
directly from the benchmark/token-cost logs in the repository rather
than estimated here.

## 6. Where it breaks

The main failure modes are inherent to the input data:

1.  **Very ambiguous handwriting**\
    Some characters or numbers can be visually similar, especially when
    strokes are unclear.

2.  **Multiple handwriting styles**\
    The model has to generalize across different writers.

3.  **Inconsistent table layouts**\
    The same logical fields may appear in different visual arrangements.

4.  **Mixed Gujarati/Hindi/English content**\
    Language switching increases the difficulty of interpreting short
    handwritten values.

5.  **Bus-number ambiguity**\
    A visually unclear bus number can be interpreted incorrectly. A
    known vehicle list and post-processing fuzzy matching would reduce
    this risk.

6.  **Model output is not ground truth**\
    Even a strong vision-language model can make confident mistakes.
    This is why human review and validation are important for production
    use.

7.  **API rate limits and dependency**\
    The current solution depends on the Gemini API and its free-tier
    limits. The README notes that the free tier has request limits and
    that 429 responses can occur.

## 7. What I would do with another week

### A. Add confidence-aware human review

I would modify the extraction schema so every row/field can include a
confidence level. Low-confidence values would be highlighted for human
verification instead of being treated as equally reliable.

### B. Build a stronger evaluation set

I would create a larger, representative ground-truth dataset covering:

-   different handwriting styles
-   different report templates
-   Gujarati/Hindi/English combinations
-   difficult numeric fields
-   empty/missing fields
-   common bus-number patterns

Then I would report field-level precision/recall or exact-match accuracy
alongside document-level accuracy.

### C. Improve bus-number validation

If a trusted vehicle list is available, I would add fuzzy matching as a
post-processing step to catch OCR/model errors such as confusing similar
digits or characters.

### D. Move processing to background jobs

For production usage with concurrent users, I would move
`extract_structured_data()` into a Celery task rather than processing
synchronously inside the Django request/response cycle.

### E. Improve reliability and observability

I would add structured logging for:

-   request/document ID
-   model
-   prompt/version
-   latency
-   token usage
-   cost
-   extraction result
-   validation failures
-   retry/error status

This would make model and prompt changes measurable instead of relying
only on visual inspection.

## 8. Security and operational considerations

The Gemini API key is read from the `GEMINI_API_KEY` environment
variable and should never be committed to source control.

The current architecture also depends on an external model API. A
production version would need explicit handling for API failures, rate
limits, retries, timeouts, and potentially a fallback strategy.

## 9. Project structure

``` text
ocr_project/
├── config/                # Django project settings/urls
├── extractor/
│   ├── models.py          # WorkReport, WorkReportRow
│   ├── services.py        # Gemini API call + JSON parsing
│   ├── views.py           # upload / process / detail
│   ├── forms.py
│   ├── urls.py
│   ├── admin.py
│   └── templates/extractor/
│       ├── upload.html
│       └── detail.html
└── manage.py
```

## 10. Ownership and AI assistance

The project implementation, integration, debugging, evaluation approach,
and engineering decisions are my work.

AI tools were used as development assistance for tasks such as
brainstorming, code assistance, and iteration. The resulting
implementation was reviewed and integrated into the project rather than
treating generated output as a substitute for engineering decisions.

## 11. Current stopping point

The current version demonstrates the core end-to-end path:

**handwritten image → vision-language extraction → structured JSON →
Django database rows → UI**

I intentionally consider the system a working prototype rather than a
production-ready OCR platform. The biggest remaining work is robust
evaluation, confidence-aware human review, stronger validation,
asynchronous processing, and deeper cost/accuracy optimization.
