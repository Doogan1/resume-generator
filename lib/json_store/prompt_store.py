from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from .base import JsonFile


DEFAULT_PROMPTS = {
    "project_extra_instruction": "",
    "resume_extra_instruction": "",
    "cover_letter_extra_instruction": "",
}


class PromptStore:
    def __init__(self, path):
        self.store = JsonFile(path)
        self._ensure_defaults()

    def _ensure_defaults(self):
        data = self.store.read()
        if not data:
            self.store.write(DEFAULT_PROMPTS)
            return
        updated = False
        for key, value in DEFAULT_PROMPTS.items():
            if key not in data:
                data[key] = value
                updated = True
        if updated:
            self.store.write(data)

    def get_prompts(self) -> Dict[str, str]:
        data = self.store.read()
        merged = {**DEFAULT_PROMPTS, **(data or {})}
        return deepcopy(merged)

    def update_prompts(self, updates: Dict[str, Any]) -> Dict[str, str]:
        current = self.get_prompts()
        for key, value in updates.items():
            if key in DEFAULT_PROMPTS and isinstance(value, str):
                current[key] = value
        self.store.write(current)
        return deepcopy(current)

