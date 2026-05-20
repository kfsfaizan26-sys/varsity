# Varsity Onboarding Service

Python backend that scans admission documents (PDF, scanned PDF, images, Excel), extracts text, structures student profile data with **Google Gemini**, validates the result, and returns JSON for the frontend.

## Pipeline

1. Receive uploaded document  
2. Detect type: `pdf_text` | `pdf_scanned` | `image` | `excel`  
3. Extract text (OCR for scans/images; PyMuPDF / pandas for others)  
4. Send text + schema to Gemini  
5. Validate with Pydantic + business rules  
6. Return JSON to frontend  

## Environment setup (your machine)

| Item | Notes |
|------|--------|
| Python | 3.11+ recommended (3.9+ supported with `eval_type_backport`) |
| Virtual env | `python -m venv .venv` then `source .venv/bin/activate` |
| Pip packages | `pip install -r requirements.txt` |
| poppler | Scanned PDFs — `brew install poppler` (macOS) |
| tesseract | OCR — `brew install tesseract` (macOS) |
| Gemini key | Copy `.env.example` → `.env` and set `GEMINI_API_KEY` |

Get an API key from [Google AI Studio](https://aistudio.google.com/apikey). Never commit `.env`.

## Run the API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Health: `GET http://localhost:8000/health`  
- Extract: `POST http://localhost:8000/api/v1/documents/extract`  
- OpenAPI docs: `http://localhost:8000/docs`

### Example extract request

```bash
# Single admission form (one student)
curl -X POST "http://localhost:8000/api/v1/documents/extract?document_type=admission_form" \
  -F "file=@/path/to/admission-form.pdf"

# Class list / roster PDF or Excel (ALL students)
curl -X POST "http://localhost:8000/api/v1/documents/extract?document_type=student_list" \
  -F "file=@/path/to/student_list.pdf"
```

### Example response

**`data` is always an array** — one student per element (index 0, 1, 2, …).

```json
{
  "success": true,
  "data": [
    {
      "personal": { "full_name": "Aarav Kumar", "first_name": "Aarav", "last_name": "Kumar" },
      "contact": { "phone": "9876543210" },
      "guardians": [{ "name": "Ramesh Kumar" }],
      "academic": {},
      "identifiers": { "roll_number": "101" },
      "meta": { "detected_type": "pdf_text", "document_type": "student_list" }
    },
    {
      "personal": { "full_name": "Priya Singh" },
      "contact": { "phone": "9876543211" },
      "guardians": [],
      "academic": {},
      "identifiers": { "roll_number": "102" },
      "meta": { "detected_type": "pdf_text", "document_type": "student_list" }
    }
  ],
  "meta": {
    "student_count": 2,
    "detected_type": "pdf_text",
    "document_type": "student_list"
  }
}
```

- `admission_form` → `data` has **1** object  
- `student_list` → `data` has **one object per student row**

## CLI (local test)

```bash
python scripts/extract_cli.py /path/to/form.pdf
```

## Tests

```bash
pytest
```

Gemini is mocked in unit tests; no API key required for `pytest`.

## Project layout

```
app/
  main.py              # FastAPI app
  config.py            # Settings from .env
  api/v1/routes/       # health, documents
  schemas/             # StudentProfile, API responses
  extractors/          # PDF, image, Excel readers
  services/            # pipeline, Gemini, validator, OCR preprocess
scripts/extract_cli.py
tests/
```

## Configuration

See [`.env.example`](.env.example):

- `GEMINI_API_KEY` — required for `/extract`  
- `GEMINI_MODEL` — default `gemini-2.0-flash`  
- `MAX_UPLOAD_MB` — default `25`  
- `CORS_ORIGINS` — comma-separated frontend URLs  
