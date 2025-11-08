from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI

from api.settings import settings
from lib.json_store.master_store import MasterStore


class AIProjectError(RuntimeError):
    pass


logger = logging.getLogger("career_console.ai_projects")


PROJECT_SCHEMA = {
    "name": "project_schema",
    "schema": {
        "type": "object",
        "properties": {
            "project": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "year": {"type": "string"},
                    "description_short": {"type": "string"},
                    "bullets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                    },
                    "skills": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "category": {"type": "string"},
                            },
                            "required": ["label"],
                        },
                        "minItems": 1,
                    },
                    "linked_experience": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["name", "year", "description_short", "bullets", "skills"],
            }
        },
        "required": ["project"],
    },
}


SYSTEM_PROMPT_TEMPLATE = """You assist with maintaining a JSON resume knowledge base.
Return structured JSON that matches the provided schema exactly.

Reuse existing skills when possible. The skills catalog is grouped by category:
{skills_catalog}

Experiences available (id — company — title):
{experience_catalog}

If you reference experience, use the id when possible or the company name.
Use concise, result-focused bullets. Keep the year field short (e.g., 2024).
Always respond with JSON only. Schema:
{schema_text}
"""


def _format_skills_catalog(master_store: MasterStore) -> str:
    skills = master_store.list_skills(include_usage=False)
    lines = []
    for category, entries in skills.items():
        labels = ", ".join(entry["label"] for entry in entries)
        lines.append(f"- {category}: {labels}")
    return "\n".join(lines) or "(no skills defined)"


def _format_experience(master_store: MasterStore) -> str:
    experience = master_store.list_experience()
    lines = []
    for item in experience:
        lines.append(f"- {item['id']} — {item['company']} — {item['title']}")
    return "\n".join(lines) or "(no experience entries)"


def _extract_json_text(response) -> str:
    # Responses API returns a list of content parts; extract first text block.
    output = getattr(response, "output", None)
    if output:
        for chunk in output:
            contents = getattr(chunk, "content", []) or []
            for content in contents:
                if getattr(content, "type", None) == "output_text":
                    return content.text
                text_value = getattr(content, "text", None)
                if text_value:
                    return text_value

    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text

    # Some responses expose a top-level `content` list
    content_list = getattr(response, "content", None)
    if content_list:
        for content in content_list:
            text_value = getattr(content, "text", None)
            if text_value:
                return text_value
            if isinstance(content, dict):
                text_value = content.get("text")
                if text_value:
                    return text_value

    raise AIProjectError("Could not extract text from AI response")


def generate_project_from_context(
    master_store: MasterStore,
    *,
    context: str,
    existing_project: Optional[Dict[str, Any]] = None,
    extra_instruction: str = "",
) -> Dict[str, Any]:
    if not settings.openai_api_key:
        raise AIProjectError("OpenAI API key not configured")

    client = OpenAI(api_key=settings.openai_api_key)

    instruction_block = SYSTEM_PROMPT_TEMPLATE
    if extra_instruction:
        instruction_block += "\n\nAdditional guidance:\n" + extra_instruction.strip()

    instructions = instruction_block.format(
        skills_catalog=_format_skills_catalog(master_store),
        experience_catalog=_format_experience(master_store),
        schema_text=json.dumps(PROJECT_SCHEMA["schema"], indent=2),
    )

    user_parts: List[Dict[str, Any]] = [
        {"type": "input_text", "text": context.strip()},
    ]

    if existing_project:
        user_parts.append(
            {
                "type": "input_text",
                "text": "Current project data (update and improve it):\n"
                + json.dumps(existing_project, indent=2),
            }
        )

    try:
        request_kwargs = {}
        model_lower = settings.responses_model.lower()
        if settings.responses_temperature is not None and "gpt-5" not in model_lower:
            request_kwargs["temperature"] = settings.responses_temperature

        response = client.responses.create(
            model=settings.responses_model,
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": instructions}]},
                {"role": "user", "content": user_parts},
            ],
            **request_kwargs,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("OpenAI request failed")
        raise AIProjectError(f"OpenAI request failed: {exc}") from exc

    try:
        text = _extract_json_text(response)
        data = json.loads(text)
    except Exception as exc:  # noqa: BLE001
        raw_dump = None
        try:
            raw_dump = response.model_dump()
        except Exception:  # noqa: BLE001
            raw_dump = str(response)
        logger.error("Failed to parse AI response", extra={"response_dump": raw_dump})
        raise AIProjectError(f"Failed to parse AI response: {exc}") from exc

    project = data.get("project")
    if not isinstance(project, dict):
        raise AIProjectError("AI did not return a project payload")

    return project

