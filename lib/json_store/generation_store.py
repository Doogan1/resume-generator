from __future__ import annotations

import datetime as dt
import pathlib
import shutil
from copy import deepcopy
from typing import Any, Dict, List, Optional

from .base import JsonFile, ensure_unique_id


class GenerationStore:
    """Persist AI-generated resumes/cover letters with file-backed assets."""

    def __init__(self, path, files_root: pathlib.Path):
        self.store = JsonFile(path)
        self.files_root = pathlib.Path(files_root)
        self.files_root.mkdir(parents=True, exist_ok=True)
        self._ensure_root()

    def _ensure_root(self):
        data = self.store.read()
        if not data:
            self.store.write({"items": []})

    def _read(self):
        return self.store.read()

    def _write(self, data):
        self.store.write(data)

    def list_items(self) -> List[Dict[str, Any]]:
        data = self._read()
        items = data.get("items", [])
        summaries = []
        for item in items:
            summaries.append(
                {
                    "id": item["id"],
                    "job_title": item.get("job_title", ""),
                    "created_at": item.get("created_at"),
                    "reasoning_effort": item.get("reasoning_effort"),
                    "verbosity": item.get("verbosity"),
                }
            )
        summaries.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return summaries

    def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        data = self._read()
        for item in data.get("items", []):
            if item.get("id") == item_id:
                return self._hydrate_record(item)
        return None

    def create_item(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = self._read()
        items = data.setdefault("items", [])
        existing_ids = {item["id"] for item in items}
        item_id = ensure_unique_id(payload.get("job_title", "resume"), existing_ids)
        now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

        record = {
            "id": item_id,
            "job_title": payload.get("job_title", ""),
            "created_at": now,
            "job_ad": payload.get("job_ad", ""),
            "summary": payload.get("summary", ""),
            "experience_ids": payload.get("experience_ids", []),
            "project_ids": payload.get("project_ids", []),
            "skill_labels": payload.get("skill_labels", []),
            "reasoning_effort": payload.get("reasoning_effort"),
            "verbosity": payload.get("verbosity"),
            "resume_token_count": payload.get("resume_token_count"),
            "cover_letter_token_count": payload.get("cover_letter_token_count"),
            "experience_plan": payload.get("experience_plan", []),
            "project_plan": payload.get("project_plan", []),
            "skills_plan": payload.get("skills_plan", []),
            "resume_path": self._resume_rel_path(item_id),
            "cover_letter_path": self._cover_rel_path(item_id),
            "resume_pdf_path": None,
            "cover_letter_pdf_path": None,
        }

        self._write_resume_html(item_id, payload.get("resume_html", ""))
        self._write_cover_letter(item_id, payload.get("cover_letter", ""))

        items.append(record)
        self._write(data)
        return self._hydrate_record(record)

    def delete_item(self, item_id: str) -> bool:
        data = self._read()
        items = data.get("items", [])
        filtered = [item for item in items if item.get("id") != item_id]
        if len(filtered) == len(items):
            return False
        data["items"] = filtered
        self._write(data)
        asset_dir = self._asset_dir(item_id)
        if asset_dir.exists():
            shutil.rmtree(asset_dir, ignore_errors=True)
        return True

    def update_item(self, item_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        data = self._read()
        items = data.get("items", [])
        for item in items:
            if item.get("id") == item_id:
                if "resume_html" in updates:
                    self._write_resume_html(item_id, updates["resume_html"])
                    item.setdefault("resume_path", self._resume_rel_path(item_id))
                if "cover_letter" in updates:
                    self._write_cover_letter(item_id, updates["cover_letter"])
                    item.setdefault("cover_letter_path", self._cover_rel_path(item_id))
                item.update({k: v for k, v in updates.items() if k not in {"resume_html", "cover_letter"}})
                self._write(data)
                return self._hydrate_record(item)
        return None

    def resume_pdf_paths(self, item_id: str) -> tuple[str, pathlib.Path]:
        rel = self._resume_pdf_rel_path(item_id)
        return rel, self.files_root / rel

    def cover_letter_pdf_paths(self, item_id: str) -> tuple[str, pathlib.Path]:
        rel = self._cover_pdf_rel_path(item_id)
        return rel, self.files_root / rel

    def _asset_dir(self, item_id: str) -> pathlib.Path:
        return self.files_root / item_id

    def _resume_rel_path(self, item_id: str) -> str:
        return f"{item_id}/resume.html"

    def _cover_rel_path(self, item_id: str) -> str:
        return f"{item_id}/cover_letter.txt"

    def _resume_pdf_rel_path(self, item_id: str) -> str:
        return f"{item_id}/resume.pdf"

    def _cover_pdf_rel_path(self, item_id: str) -> str:
        return f"{item_id}/cover_letter.pdf"

    def _write_resume_html(self, item_id: str, html: Optional[str]):
        asset_dir = self._asset_dir(item_id)
        asset_dir.mkdir(parents=True, exist_ok=True)
        (asset_dir / "resume.html").write_text(html or "", encoding="utf-8")

    def _write_cover_letter(self, item_id: str, text: Optional[str]):
        asset_dir = self._asset_dir(item_id)
        asset_dir.mkdir(parents=True, exist_ok=True)
        (asset_dir / "cover_letter.txt").write_text(text or "", encoding="utf-8")

    def _read_resume_html(self, item_id: str, record: Dict[str, Any]) -> str:
        path_str = record.get("resume_path") or self._resume_rel_path(item_id)
        path = self.files_root / path_str
        if path.exists():
            return path.read_text(encoding="utf-8")
        return record.get("resume_html", "")

    def _read_cover_letter(self, item_id: str, record: Dict[str, Any]) -> str:
        path_str = record.get("cover_letter_path") or self._cover_rel_path(item_id)
        path = self.files_root / path_str
        if path.exists():
            return path.read_text(encoding="utf-8")
        return record.get("cover_letter", "")

    def _hydrate_record(self, item: Dict[str, Any]) -> Dict[str, Any]:
        record = deepcopy(item)
        item_id = record["id"]

        record["resume_path"] = record.get("resume_path") or self._resume_rel_path(item_id)
        record["cover_letter_path"] = record.get("cover_letter_path") or self._cover_rel_path(item_id)

        resume_pdf_rel = record.get("resume_pdf_path")
        if not resume_pdf_rel:
            rel = self._resume_pdf_rel_path(item_id)
            if (self.files_root / rel).exists():
                resume_pdf_rel = rel
        record["resume_pdf_path"] = resume_pdf_rel

        cover_pdf_rel = record.get("cover_letter_pdf_path")
        if not cover_pdf_rel:
            rel = self._cover_pdf_rel_path(item_id)
            if (self.files_root / rel).exists():
                cover_pdf_rel = rel
        record["cover_letter_pdf_path"] = cover_pdf_rel

        record["resume_html"] = self._read_resume_html(item_id, record)
        record["cover_letter"] = self._read_cover_letter(item_id, record)
        return record

