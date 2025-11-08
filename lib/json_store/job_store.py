from __future__ import annotations

import json
import pathlib
from copy import deepcopy
from typing import Any, Dict, List

from .base import slugify


class JobConfigStore:
    """Manage jobs/*.json files."""

    def __init__(self, directory: pathlib.Path, template_path: pathlib.Path | None = None):
        self.directory = pathlib.Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.template_path = template_path or (self.directory / "template.json")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _path_for(self, slug: str) -> pathlib.Path:
        safe_slug = slugify(slug)
        return self.directory / f"{safe_slug}.json"

    def _read(self, path: pathlib.Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write(self, path: pathlib.Path, data: Dict[str, Any]):
        payload = json.dumps(data, indent=2, ensure_ascii=False)
        tmp_path = path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")
        tmp_path.replace(path)

    def _load_template(self) -> Dict[str, Any]:
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template not found: {self.template_path}")
        with self.template_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def list_configs(self) -> List[Dict[str, Any]]:
        items = []
        for path in sorted(self.directory.glob("*.json")):
            if path.name == self.template_path.name:
                continue
            data = self._read(path)
            items.append(
                {
                    "slug": path.stem,
                    "title": data.get("title", ""),
                    "summary_key": data.get("summary_key", ""),
                    "selected_projects": data.get("selected_projects", []),
                }
            )
        return items

    def get_config(self, slug: str) -> Dict[str, Any]:
        path = self._path_for(slug)
        if not path.exists():
            raise FileNotFoundError(f"Job config '{slug}' not found")
        return deepcopy(self._read(path))

    def create_config(self, slug: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        path = self._path_for(slug)
        if path.exists():
            raise FileExistsError(f"Job config '{slug}' already exists")
        data = self._load_template()
        data["title"] = payload.get("title", data.get("title", ""))
        if "summary_key" in payload:
            data["summary_key"] = payload["summary_key"]
        if "selected_projects" in payload:
            data["selected_projects"] = payload["selected_projects"]
        if "show_freelance" in payload:
            data["show_freelance"] = bool(payload["show_freelance"])
        if "skills_order" in payload:
            data["skills_order"] = payload["skills_order"]
        if "skills_label_map" in payload:
            data["skills_label_map"] = payload["skills_label_map"]
        self._write(path, data)
        return deepcopy(data | {"slug": path.stem})

    def update_config(self, slug: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        path = self._path_for(slug)
        if not path.exists():
            raise FileNotFoundError(f"Job config '{slug}' not found")
        data = self._read(path)

        for key in ["title", "summary_key", "selected_projects", "skills_order", "skills_label_map"]:
            if key in payload:
                data[key] = payload[key]
        if "show_freelance" in payload:
            data["show_freelance"] = bool(payload["show_freelance"])

        self._write(path, data)
        return deepcopy(data | {"slug": path.stem})

    def delete_config(self, slug: str):
        path = self._path_for(slug)
        if not path.exists():
            raise FileNotFoundError(f"Job config '{slug}' not found")
        path.unlink()
        return {"deleted": slug}

