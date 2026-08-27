"""Small standard-library client for testing a running local Flask API."""
# cd "C:\Users\dwive\Documents\Codex\2026-08-11\build-a-complete-production-style-id\outputs\ID-Card-OCR"
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
# .\.venv\Scripts\Activate.ps1
from __future__ import annotations

import json
import mimetypes
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def multipart_body(field_name: str, file_path: Path) -> tuple[bytes, str]:
    boundary = f"----IDCardOCR{uuid.uuid4().hex}"
    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{file_path.name}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode()
    body = header + file_path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    return body, boundary


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python test_api.py path/to/id_card.jpg")
        raise SystemExit(1)
    image_path = Path(sys.argv[1])
    if not image_path.is_file():
        print(f"Image not found: {image_path}")
        raise SystemExit(1)
    body, boundary = multipart_body("image", image_path)
    request = Request(
        "http://127.0.0.1:5000/extract",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urlopen(request, timeout=60) as response:
            payload = response.read().decode("utf-8")
            print("Status Code:")
            print(response.status)
            print("\nJSON Response:")
            print(json.dumps(json.loads(payload), indent=2))
    except HTTPError as error:
        print("Status Code:")
        print(error.code)
        print("\nJSON Response:")
        print(error.read().decode("utf-8"))
    except URLError:
        print("Could not reach the API. Start it first with: python api.py")


if __name__ == "__main__":
    main()
