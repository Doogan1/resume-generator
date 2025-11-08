from __future__ import annotations

import json
import pathlib
import re
import threading
import uuid


class JsonFile:
    """Thread-safe JSON reader/writer for local files."""

    def __init__(self, path: pathlib.Path):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def read(self):
        with self._lock:
            if not self.path.exists():
                return {}
            with self.path.open("r", encoding="utf-8") as handle:
                return json.load(handle)

    def write(self, data):
        payload = json.dumps(data, indent=2, ensure_ascii=False)
        with self._lock:
            tmp_path = self.path.with_suffix(".tmp")
            with tmp_path.open("w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.write("\n")
            tmp_path.replace(self.path)


def slugify(value: str) -> str:
    """Basic slug generator suitable for IDs."""
    if not value:
        return str(uuid.uuid4())
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\s-]", "", value)
    value = re.sub(r"[\s\-]+", "-", value)
    value = value.strip("-")
    return value or str(uuid.uuid4())


def ensure_unique_id(base: str, existing: set[str]) -> str:
    slug = slugify(base)
    if slug not in existing:
        return slug
    idx = 2
    while f"{slug}-{idx}" in existing:
        idx += 1
    return f"{slug}-{idx}"

