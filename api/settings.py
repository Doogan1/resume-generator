from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass

from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parents[1]

load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    responses_model: str = os.getenv("OPENAI_RESPONSES_MODEL", "gpt-4.1-mini")
    responses_temperature: float = float(os.getenv("OPENAI_RESPONSES_TEMPERATURE", "0.4"))
    wkhtmltopdf_path: str | None = os.getenv("WKHTMLTOPDF_PATH")


settings = Settings()

