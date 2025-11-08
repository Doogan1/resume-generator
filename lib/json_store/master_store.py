from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any, Dict, List

from .base import JsonFile, ensure_unique_id


class MasterStore:
    """Wrapper around data/master.json providing structured operations."""

    def __init__(self, path):
        self.store = JsonFile(path)
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Schema management
    # ------------------------------------------------------------------
    def _ensure_schema(self):
        data = self.store.read()
        if not data:
            return

        mutated = False

        # Experience IDs
        experience = data.get("experience", [])
        exp_ids = set()
        for item in experience:
            if not item.get("id"):
                item["id"] = ensure_unique_id(item.get("company", "experience"), exp_ids)
                mutated = True
            exp_ids.add(item["id"])

        # Project defaults and IDs
        projects = data.get("projects", [])
        project_ids = set()
        for project in projects:
            if not project.get("id"):
                project["id"] = ensure_unique_id(project.get("name", "project"), project_ids)
                mutated = True
            project_ids.add(project["id"])

            if "description_short" not in project:
                project["description_short"] = ""
                mutated = True
            if "skills_used" not in project:
                project["skills_used"] = []
                mutated = True
            if "linked_experience" not in project:
                project["linked_experience"] = []
                mutated = True

        # Skills normalization
        skills = data.get("skills", {})
        for category, entries in skills.items():
            normalized: List[Dict[str, Any]] = []
            seen_ids = set()
            for entry in entries:
                if isinstance(entry, dict):
                    skill_id = entry.get("id") or ensure_unique_id(entry.get("label", "skill"), seen_ids)
                    label = entry.get("label", "").strip()
                else:
                    label = str(entry).strip()
                    skill_id = ensure_unique_id(label or "skill", seen_ids)
                normalized.append({"id": skill_id, "label": label})
                seen_ids.add(skill_id)
                if isinstance(entry, dict) and entry.get("id") == skill_id and entry.get("label", "").strip() == label:
                    continue
                mutated = True
            skills[category] = normalized

        if mutated:
            self.store.write(data)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _read(self):
        return self.store.read()

    def _write(self, data):
        self.store.write(data)

    def _find_project_index(self, data, project_id):
        for idx, project in enumerate(data.get("projects", [])):
            if project.get("id") == project_id:
                return idx
        return None

    def _find_experience_index(self, data, experience_id):
        for idx, exp in enumerate(data.get("experience", [])):
            if exp.get("id") == experience_id:
                return idx
        return None

    @staticmethod
    def _normalize_bullets(values) -> List[str]:
        if values is None:
            return []
        if isinstance(values, str):
            parts = [line.strip() for line in values.splitlines()]
            return [p for p in parts if p]
        bullets = []
        for value in values:
            text = str(value).strip()
            if text:
                bullets.append(text)
        return bullets

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------
    def list_projects(self) -> List[Dict[str, Any]]:
        data = self._read()
        return deepcopy(data.get("projects", []))

    def create_project(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = self._read()
        projects = data.setdefault("projects", [])
        existing_ids = {p.get("id") for p in projects if p.get("id")}
        project_id = ensure_unique_id(payload.get("name", "project"), existing_ids)
        project = {
            "id": project_id,
            "name": payload.get("name", "").strip(),
            "year": str(payload.get("year", "")).strip(),
            "description_short": payload.get("description_short", "").strip(),
            "bullets": self._normalize_bullets(payload.get("bullets", [])),
            "skills_used": list(dict.fromkeys(payload.get("skills_used", []))),
            "linked_experience": list(dict.fromkeys(payload.get("linked_experience", []))),
        }
        projects.append(project)
        self._write(data)
        return deepcopy(project)

    def update_project(self, project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = self._read()
        idx = self._find_project_index(data, project_id)
        if idx is None:
            raise KeyError(f"Project '{project_id}' not found")
        project = data["projects"][idx]

        if "name" in payload:
            project["name"] = payload["name"].strip()
        if "year" in payload:
            project["year"] = str(payload["year"]).strip()
        if "description_short" in payload:
            project["description_short"] = payload["description_short"].strip()
        if "bullets" in payload:
            project["bullets"] = self._normalize_bullets(payload["bullets"])
        if "skills_used" in payload:
            project["skills_used"] = list(dict.fromkeys(payload["skills_used"]))
        if "linked_experience" in payload:
            project["linked_experience"] = list(dict.fromkeys(payload["linked_experience"]))

        self._write(data)
        return deepcopy(project)

    def delete_project(self, project_id: str):
        data = self._read()
        projects = data.get("projects", [])
        filtered = [p for p in projects if p.get("id") != project_id]
        if len(filtered) == len(projects):
            raise KeyError(f"Project '{project_id}' not found")
        data["projects"] = filtered
        self._write(data)
        return {"deleted": project_id}

    # ------------------------------------------------------------------
    # Skills
    # ------------------------------------------------------------------
    def list_skills(self, include_usage: bool = False):
        data = self._read()
        skills = deepcopy(data.get("skills", {}))
        if not include_usage:
            return skills

        usage_map = defaultdict(list)
        for project in data.get("projects", []):
            for skill_id in project.get("skills_used", []):
                usage_map[skill_id].append(
                    {"project_id": project.get("id"), "project_name": project.get("name")}
                )

        for category, entries in skills.items():
            for entry in entries:
                entry["usage"] = usage_map.get(entry["id"], [])

        return skills

    def add_skill(self, category: str, label: str) -> Dict[str, Any]:
        category = category.strip()
        label = label.strip()
        if not category or not label:
            raise ValueError("Category and label are required")

        data = self._read()
        skills = data.setdefault("skills", {})
        entries = skills.setdefault(category, [])
        existing_ids = {entry.get("id") for entry in entries if entry.get("id")}
        skill_id = ensure_unique_id(label, existing_ids)
        entry = {"id": skill_id, "label": label}
        entries.append(entry)
        self._write(data)
        return deepcopy(entry)

    def update_skill(self, category: str, skill_id: str, label: str) -> Dict[str, Any]:
        data = self._read()
        entries = data.get("skills", {}).get(category)
        if entries is None:
            raise KeyError(f"Category '{category}' not found")

        for entry in entries:
            if entry.get("id") == skill_id:
                entry["label"] = label.strip()
                self._write(data)
                return deepcopy(entry)
        raise KeyError(f"Skill '{skill_id}' not found in '{category}'")

    def delete_skill(self, category: str, skill_id: str):
        data = self._read()
        entries = data.get("skills", {}).get(category)
        if entries is None:
            raise KeyError(f"Category '{category}' not found")
        filtered = [entry for entry in entries if entry.get("id") != skill_id]
        if len(filtered) == len(entries):
            raise KeyError(f"Skill '{skill_id}' not found in '{category}'")
        data["skills"][category] = filtered

        # Remove skill references from projects
        for project in data.get("projects", []):
            if skill_id in project.get("skills_used", []):
                project["skills_used"] = [sid for sid in project["skills_used"] if sid != skill_id]

        self._write(data)
        return {"deleted": skill_id, "category": category}

    # ------------------------------------------------------------------
    # Experience
    # ------------------------------------------------------------------
    def list_experience(self) -> List[Dict[str, Any]]:
        data = self._read()
        return deepcopy(data.get("experience", []))

    def create_experience(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = self._read()
        experience = data.setdefault("experience", [])
        existing_ids = {item.get("id") for item in experience if item.get("id")}
        exp_id = ensure_unique_id(payload.get("company", "experience"), existing_ids)

        item = {
            "id": exp_id,
            "company": payload.get("company", "").strip(),
            "title": payload.get("title", "").strip(),
            "dates": payload.get("dates", "").strip(),
            "bullets": self._normalize_bullets(payload.get("bullets", [])),
        }
        experience.append(item)
        self._write(data)
        return deepcopy(item)

    def update_experience(self, experience_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = self._read()
        idx = self._find_experience_index(data, experience_id)
        if idx is None:
            raise KeyError(f"Experience '{experience_id}' not found")
        item = data["experience"][idx]

        if "company" in payload:
            item["company"] = payload["company"].strip()
        if "title" in payload:
            item["title"] = payload["title"].strip()
        if "dates" in payload:
            item["dates"] = payload["dates"].strip()
        if "bullets" in payload:
            item["bullets"] = self._normalize_bullets(payload["bullets"])

        self._write(data)
        return deepcopy(item)

    def delete_experience(self, experience_id: str):
        data = self._read()
        experience = data.get("experience", [])
        filtered = [item for item in experience if item.get("id") != experience_id]
        if len(filtered) == len(experience):
            raise KeyError(f"Experience '{experience_id}' not found")
        data["experience"] = filtered

        # Remove links from projects
        for project in data.get("projects", []):
            if experience_id in project.get("linked_experience", []):
                project["linked_experience"] = [
                    eid for eid in project["linked_experience"] if eid != experience_id
                ]

        self._write(data)
        return {"deleted": experience_id}

    # ------------------------------------------------------------------
    # Summaries / metadata
    # ------------------------------------------------------------------
    def list_summary_keys(self) -> List[str]:
        data = self._read()
        return list(data.get("summary", {}).keys())

    def get_master_snapshot(self) -> Dict[str, Any]:
        """Return a copy of the full master file."""
        return deepcopy(self._read())

