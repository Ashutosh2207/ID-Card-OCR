"""Optional Flask API that reuses the exact Streamlit extraction pipeline."""

from __future__ import annotations

from flask import Flask, jsonify, request

from config import get_settings
from src.service import ExtractionError, extract_from_bytes


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = get_settings().max_upload_size_mb * 1024 * 1024


@app.post("/extract")
def extract():
    """Extract fields from multipart form field ``image`` without saving it."""
    if "image" not in request.files:
        return jsonify({"status": "error", "message": "Use multipart/form-data with an image field named 'image'."}), 400
    upload = request.files["image"]
    if not upload.filename:
        return jsonify({"status": "error", "message": "No image file was selected."}), 400
    if upload.mimetype and upload.mimetype.lower() not in {"image/jpeg", "image/png", "image/jpg"}:
        return jsonify({"status": "error", "message": "Only JPG, JPEG, and PNG images are supported."}), 400
    # By default Aadhaar, PAN and Driving Licence values are masked. Callers must
    # explicitly opt in to full values in an authorised, secure environment.
    show_full_id = request.form.get("show_full_id", "false").lower() in {"true", "1", "yes"}
    try:
        result = extract_from_bytes(upload.read(), show_full_id=show_full_id)
        return jsonify({"status": result["status"], "data": result["data"]}), 200
    except ExtractionError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 422


@app.errorhandler(413)
def file_too_large(_error):
    return jsonify({"status": "error", "message": "Image is too large. Maximum size is 10 MB."}), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
