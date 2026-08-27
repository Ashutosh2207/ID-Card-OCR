# AI-Based ID Card OCR & Information Extraction

A modular Python project that reads Indian identity-card images with Tesseract OCR and extracts structured information for Aadhaar, PAN, Driving Licence, and Voter ID cards. It has a Streamlit user interface and an optional Flask API, both powered by the same extraction pipeline.

> **Privacy note:** Identity documents contain sensitive personal data. This project processes uploads in memory, does not save them by default, masks Aadhaar numbers in the UI/API by default, and should only be used with appropriate user consent.

## Features

- Supports Aadhaar, PAN, Driving Licence, and Voter ID cards; safely falls back to `Unknown`.
- Uses OpenCV preprocessing selectively: RGB/BGR conversion, controlled upscaling, contrast enhancement, sharpening, median filtering/adaptive thresholding for low contrast, and modest deskewing.
- Detects Aadhaar QR-code polygons with OpenCV and masks only that small area before OCR.
- Runs Tesseract on original, upscaled, and preprocessed variants, then selects the most useful result instead of concatenating duplicate OCR text.
- Uses document-specific extractors and validation for Aadhaar, PAN, EPIC, driving-licence, mobile, DOB, gender, name, and address fields.
- Preserves useful punctuation and numbers in addresses.
- Provides a Streamlit download button and an optional `POST /extract` endpoint.
- Includes unit tests for key extraction rules, document detection, preprocessing, and invalid image input.

## Technologies

- Python 3.10+
- Tesseract OCR + `pytesseract`
- OpenCV, Pillow, NumPy
- Regular expressions and contextual scoring
- Streamlit
- Flask

## Architecture

```text
Image upload
    -> conservative preprocessing
    -> QR detection and local masking
    -> Tesseract OCR (best of image variants)
    -> text cleanup
    -> document-type detection
    -> document-specific extraction + field validation
    -> privacy masking
    -> Streamlit / Flask JSON response
```

The public entry points call `src.service.extract_from_bytes()`. This is important: `app.py` and `api.py` do not contain duplicate extraction logic.

## Folder structure

```text
ID-Card-OCR/
├── app.py
├── api.py
├── test_api.py
├── requirements.txt
├── README.md
├── .gitignore
├── .env.example
├── config/
│   ├── __init__.py
│   └── settings.py
├── src/
│   ├── __init__.py
│   ├── service.py
│   ├── ocr_engine.py
│   ├── preprocessing.py
│   ├── text_cleaner.py
│   ├── document_detector.py
│   ├── utils.py
│   └── extractors/
│       ├── __init__.py
│       ├── base_extractor.py
│       ├── aadhaar_extractor.py
│       ├── pan_extractor.py
│       ├── driving_license_extractor.py
│       └── voter_id_extractor.py
├── tests/
│   ├── __init__.py
│   ├── test_ocr.py
│   ├── test_extractors.py
│   └── test_document_detector.py
├── uploads/.gitkeep
└── sample_outputs/.gitkeep
```

## Installation

### 1. Install Tesseract OCR (required separately)

`pytesseract` is only the Python wrapper; it does **not** install the Tesseract executable.

On Windows, install Tesseract OCR, commonly to:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

After installation, either add that directory to your system `PATH`, or configure the path in this project as shown below. Reopen PowerShell after changing your `PATH`.

### 2. Create and activate a virtual environment

Run these commands from the project root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Tesseract

Copy `.env.example` to `.env`, then set the installed executable path:

```powershell
Copy-Item .env.example .env
```

Example `.env`:

```dotenv
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
TESSERACT_LANGUAGE=eng
TESSERACT_PSM=6
```

The actual `.env` is ignored by Git. Do not put secrets or real identity-card information in it.

## Run the Streamlit application

```powershell
streamlit run app.py
```

Open the local URL shown by Streamlit, upload a JPG/JPEG/PNG ID-card image, and select **Extract Information**. Aadhaar, PAN, and Driving Licence IDs are masked by default (for example, `XXXX XXXX 5075`, `XXXXX1234F`, or `XXXXXXXXXXX2345`) unless the user explicitly ticks **Show full ID number**.

## Run and test the API

Start Flask in one terminal:

```powershell
python api.py
```

In a second terminal, send an image without adding another dependency:

```powershell
python test_api.py path\to\id_card.jpg
```

Or call it with curl:

```powershell
curl.exe -X POST -F "image=@path\to\id_card.jpg" http://127.0.0.1:5000/extract
```

Expected response shape:

```json
{
  "status": "success",
  "data": {
    "document_type": "Aadhaar",
    "name": "Example Name",
    "date_of_birth": "24/07/2003",
    "gender": "Male",
    "mobile": "Not detected",
    "id_number": "XXXX XXXX 5075",
    "address": "House 1, Example Road, Pune, Maharashtra 411001"
  }
}
```

To show a full Aadhaar, PAN, or Driving Licence number through the API, explicitly send `show_full_id=true` in the multipart form. Use that option only in an authorised, secure environment.

## Run tests

The included unit tests do not invoke Tesseract, so they can run before installing it:

```powershell
python -m unittest discover -s tests -v
```

The tests cover Aadhaar number formatting and VID rejection, PAN extraction, DOB/year-of-birth rules, gender boundaries, Indian mobile validation, name validation, document detection, QR/preprocessing helpers, and invalid image bytes.

## Supported documents and fields

| Document | Extracted fields |
| --- | --- |
| Aadhaar | Name, DOB/YOB, gender, mobile, Aadhaar number, address |
| PAN | Name, father's name, DOB, PAN number |
| Driving Licence | Name, DOB, licence number, address, validity, vehicle class |
| Voter ID | Name, relation name, DOB/age, gender, EPIC number, address |

Every unavailable value is returned as `"Not detected"`, rather than `null`.

## How the pipeline works

1. Pillow reads the image in memory and converts it to RGB; OpenCV uses a BGR working copy.
2. `remove_qr_code()` uses `QRCodeDetector` to find each QR polygon and whites out only the detected polygon with a small 3% margin.
3. The OCR module compares original, upscaled, and conservatively preprocessed versions. It ranks the outputs instead of blindly merging duplicate lines.
4. Text cleaning normalises whitespace and control artifacts while retaining address-safe punctuation.
5. The detector scores keywords and patterns across all supported document types.
6. The selected extractor applies its own validations. For example, Aadhaar candidates are 12 digits and never returned from a `VID` context; mobile candidates must be ten digits starting with 6–9; an unlabelled year is not treated as a DOB.
7. The service applies Aadhaar masking before returning the public UI/API result.

## Limitations

- OCR quality depends heavily on focus, lighting, glare, rotation, language, font, and source resolution.
- This project is English-first. Install Tesseract language data and set `TESSERACT_LANGUAGE` if your use case requires an additional language.
- Indian document layouts and driving-licence formats vary by issuer/state; no rule-based extractor can guarantee every field from every layout.
- Extraction is assistive, not identity verification. Always review critical values manually.
- It intentionally does not use a machine-learning document classifier; keyword/pattern rules are easier to inspect and extend for a beginner project.

## Common errors and fixes

| Symptom | Likely cause / fix |
| --- | --- |
| `Tesseract OCR is not installed` | Install Tesseract and set `TESSERACT_PATH` in `.env`, or add its installation folder to `PATH`. |
| `Tesseract was not found at TESSERACT_PATH` | Confirm the full path ends in `tesseract.exe`; do not point to the containing folder. |
| `No text was detected` | Use a clearer, flatter image with better lighting; crop excessive background and avoid glare. |
| Fields show `Not detected` | OCR may have misread the text or that field may not be printed on this document. Check Raw OCR Text and improve the image. |
| API returns 400 | Send `multipart/form-data` with the field name `image` and a JPG/JPEG/PNG file. |
| API returns 413 | Reduce the image below 10 MB. |

## Privacy and security

- Uploads are decoded from bytes and never written to `uploads/` by application code.
- The API does not log full OCR output or identity numbers.
- Aadhaar, PAN, and Driving Licence IDs are masked by default; full display requires an explicit opt-in.
- `.gitignore` excludes `.env`, logs, and runtime upload/output directories.
- Do not commit real ID cards, production `.env` files, or extracted results to GitHub.
- Add authentication, HTTPS, encrypted storage (only if truly needed), retention policies, and access auditing before deploying this publicly.

## GitHub setup

```powershell
git init
git add .
git commit -m "Build modular ID card OCR extractor"
git branch -M main
git remote add origin https://github.com/YOUR-USER/ID-Card-OCR.git
git push -u origin main
```

Review `git status` before each commit and verify that no real document images, `.env`, or extracted data are staged.

## Screenshots

Add Streamlit screenshots here after running the application. Use mock/redacted cards only.

## Interview explanation

“I built a rule-based OCR extraction system for Indian identity cards. The main design decision was separating the work into stages: image preprocessing, QR masking, Tesseract OCR, text cleanup, document classification, and one extractor per card type. This avoids a giant file and lets me add new documents without changing the UI or API. I used contextual scoring for names and IDs because OCR text is noisy; for example, Aadhaar extraction ignores 16-digit VID values, a mobile must begin with 6–9, and a date must be labelled or be a valid birth date. The Streamlit UI and Flask API use one shared service function, and the project masks Aadhaar values by default because the data is sensitive.”

## Future improvements

- Add OCR confidence per word/field and visually highlight uncertain values.
- Add Hindi and other language packs, document orientation detection, and layout-aware regions of interest.
- Add redacted demo fixtures and regression tests for more document layouts.
- Add authenticated API access, rate limiting, encrypted short-lived storage only when necessary, and audit logging that excludes sensitive values.
- Add optional user correction feedback to improve document-specific extraction rules.
