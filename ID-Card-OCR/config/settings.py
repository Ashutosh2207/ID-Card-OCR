"""Centralised, dependency-free application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv_file(path: Path) -> None:
    """Load simple KEY=VALUE pairs without requiring python-dotenv."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    """Runtime settings used by both the web UI and the API."""

    tesseract_path: str | None
    tesseract_language: str = "eng"
    tesseract_psm: int = 6
    max_upload_size_mb: int = 10


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_dotenv_file(PROJECT_ROOT / ".env")
    path = os.getenv("TESSERACT_PATH", "").strip() or None
    language = os.getenv("TESSERACT_LANGUAGE", "eng").strip() or "eng"
    psm_value = os.getenv("TESSERACT_PSM", "6").strip()
    try:
        psm = int(psm_value)
    except ValueError:
        psm = 6
    return Settings(tesseract_path=path, tesseract_language=language, tesseract_psm=psm)
