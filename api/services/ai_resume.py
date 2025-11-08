from __future__ import annotations

import json
import logging
import pathlib
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from api.settings import ROOT, settings
from lib.json_store.master_store import MasterStore

logger = logging.getLogger("career_console.ai_resume")


RESUME_SCHEMA = {
    "name": "resume_package",
    "schema": {
        "type": "object",
        "properties": {
            "job_title": {"type": "string"},
            "summary": {"type": "string"},
            "reasoning_effort": {
                "type": "string",
                "enum": ["minimal", "low", "medium", "high"],
            },
            "verbosity": {
                "type": "string",
                "enum": ["low", "medium", "high"],
            },
            "experience": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "bullets": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                        },
                        "notes": {"type": "string"},
                    },
                    "required": ["id"],
                },
            },
            "projects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "bullets": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "notes": {"type": "string"},
                    },
                    "required": ["id"],
                },
            },
            "skills": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "label": {"type": "string"},
                    },
                    "minProperties": 1,
                },
            },
        },
        "required": ["job_title", "summary", "experience", "projects", "skills"],
    },
}


THEME_CSS = (ROOT / "themes" / "default.css").read_text(encoding="utf-8")

RESUME_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>{css}</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <h1>{name}</h1>
      <div class="role">{role}</div>
    </div>
    <div class="contact">
      <div>{phone}</div>
      <div><a href="mailto:{email}">{email}</a></div>
      <div>{location}</div>
      <div>{links_html}</div>
    </div>
  </div>

  <div class="section">
    <h2>Summary</h2>
    <p>{summary}</p>
  </div>

  <div class="section">
    <h2>Experience</h2>
    {experience_html}
  </div>

  <div class="section">
    <h2>Selected Projects</h2>
    {projects_html}
  </div>

  <div class="section">
    <h2>Technical Skills</h2>
    <div class="skills">
      {skills_html}
    </div>
  </div>
</div>
</body>
</html>
"""


def links_html(contact: Dict[str, Any]) -> str:
    links = contact.get("links", [])
    return " &nbsp;•&nbsp; ".join([f'<a href="{link["url"]}">{link["label"]}</a>' for link in links])


def _format_master_context(master: Dict[str, Any]) -> str:
    sections = []
    sections.append(f"Name: {master['name']}")

    sections.append("Experience:")
    for exp in master.get("experience", []):
        bullets = "; ".join(exp.get("bullets", [])[:5])
        sections.append(f"- {exp['id']} — {exp['company']} — {exp['title']} — {exp['dates']} :: {bullets}")

    sections.append("Projects:")
    for proj in master.get("projects", []):
        bullets = "; ".join(proj.get("bullets", [])[:4])
        sections.append(f"- {proj['id']} — {proj['name']} ({proj['year']}) :: {bullets}")

    sections.append("Skills:")
    skills = master.get("skills", {})
    for category, entries in skills.items():
        labels = ", ".join(entry["label"] for entry in entries)
        sections.append(f"- {category}: {labels}")

    return "\n".join(sections)


SYSTEM_PROMPT = """You are an assistant that crafts tailored resumes.
Task requirements:
- Use only the provided experience, projects, and skills from the master data.
- Select at least two experience entries (3 preferred) that best match the job ad, and include refreshed bullet language referencing the role.
- Select at least two projects (3 preferred) with tailored bullets.
- Provide a concise, job-aligned summary sentence (2–3 sentences).
- Include a skill list referencing existing labels; reuse IDs when available.
- Populate the title with the target job title gleaned from the posting.
- Return JSON only, matching the provided schema exactly. Never return an empty array for experience or projects.
"""


def _find_by_id_or_slug(items: List[Dict[str, Any]], identifier: str, fallback_keys: Optional[List[str]] = None):
    identifier_lower = (identifier or "").lower()
    for item in items:
        if item.get("id") == identifier:
            return item
    if fallback_keys:
        for item in items:
            for key in fallback_keys:
                value = item.get(key, "")
                if isinstance(value, str) and value.lower() == identifier_lower:
                    return item
    return None


def _build_experience_html(master: Dict[str, Any], experience_plan: List[Dict[str, Any]]) -> List[str]:
    experience_lookup = {exp["id"]: exp for exp in master.get("experience", [])}
    blocks = []
    for plan in experience_plan:
        exp = experience_lookup.get(plan.get("id"))
        if not exp:
            continue
        bullets = plan.get("bullets") or exp.get("bullets", [])
        bullets_html = "".join(f"<li>{bullet}</li>" for bullet in bullets if bullet)
        blocks.append(
            f"""
        <div class="item">
          <div class="meta">
            <div class="left">{exp['company']} — {exp['title']}</div>
            <div class="right">{exp['dates']}</div>
          </div>
          <ul>{bullets_html}</ul>
        </div>
        """
        )
    return blocks


def _build_projects_html(master: Dict[str, Any], project_plan: List[Dict[str, Any]]) -> List[str]:
    project_lookup = {proj["id"]: proj for proj in master.get("projects", [])}
    blocks = []
    for plan in project_plan:
        proj = project_lookup.get(plan.get("id"))
        if not proj:
            continue
        bullets = plan.get("bullets") or proj.get("bullets", [])
        bullets_html = "".join(f"<li>{bullet}</li>" for bullet in bullets if bullet)
        blocks.append(
            f"""
        <div class="item">
          <div class="meta">
            <div class="left">{proj['name']}</div>
            <div class="right">{proj['year']}</div>
          </div>
          <ul>{bullets_html}</ul>
        </div>
        """
        )
    return blocks


def _build_skills_html(
    plan_skills: List[Dict[str, Any]],
    skill_lookup: Dict[str, str],
    category_lookup: Dict[str, List[str]],
    skill_to_category: Dict[str, str],
) -> str:
    category_entries: Dict[str, List[str]] = {key: [] for key in category_lookup.keys()}

    def resolve_category(skill_id: Optional[str], label: str) -> Optional[str]:
        if skill_id and skill_id in skill_to_category:
            return skill_to_category[skill_id]
        if label:
            for category, labels in category_lookup.items():
                if label in labels:
                    return category
                if label.lower() in [l.lower() for l in labels]:
                    return category
        return None

    for entry in plan_skills:
        if isinstance(entry, str):
            entry = {"label": entry}
        skill_id = entry.get("id")
        label = entry.get("label", "")
        resolved_label = None
        if skill_id and skill_id in skill_lookup:
            resolved_label = skill_lookup[skill_id]
        elif label and label.lower() in skill_lookup:
            resolved_label = skill_lookup[label.lower()]
        elif label:
            resolved_label = label

        category = resolve_category(skill_id, resolved_label or label)
        if not category:
            category = resolve_category(skill_id, label)
        if not category:
            category = "other"
            if category not in category_entries:
                category_entries[category] = []

        if resolved_label:
            if resolved_label not in category_entries.setdefault(category, []):
                category_entries[category].append(resolved_label)

    blocks = []
    for category, labels in category_entries.items():
        if not labels:
            continue
        display = category.replace("_", " ").title()
        items = "".join(f"<li>{label}</li>" for label in labels)
        blocks.append(
            f'<div class="skill-block"><div class="label">{display}</div><div class="list"><ul>{items}</ul></div></div>'
        )
    return "".join(blocks)


def build_resume_html(master: Dict[str, Any], package: Dict[str, Any]) -> str:
    contact = master.get("contact", {})
    experience_html = "\n".join(_build_experience_html(master, package.get("experience", [])))
    projects_html = "\n".join(_build_projects_html(master, package.get("projects", [])))
    skill_lookup, category_lookup, skill_to_category = _skill_label_maps(master)
    skills_html = _build_skills_html(
        package.get("skills", []), skill_lookup, category_lookup, skill_to_category
    )

    html = RESUME_TEMPLATE.format(
        title=f"{master['name']} – {package.get('job_title', 'Resume')}",
        css=THEME_CSS,
        name=master["name"],
        role=package.get("job_title", ""),
        phone=contact.get("phone", ""),
        email=contact.get("email", ""),
        location=contact.get("location", ""),
        links_html=links_html(contact),
        summary=package.get("summary", ""),
        experience_html=experience_html or "<p>No experience selected.</p>",
        projects_html=projects_html or "<p>No projects selected.</p>",
        skills_html=skills_html,
    )
    return html


def generate_resume_package(
    master_store: MasterStore, *, job_ad: str, extra_instruction: str = ""
) -> Dict[str, Any]:
    if not settings.openai_api_key:
        raise RuntimeError("OpenAI API key not configured")

    master = master_store.get_master_snapshot()
    client = OpenAI(api_key=settings.openai_api_key)

    context = _format_master_context(master)
    instructions = SYSTEM_PROMPT
    if extra_instruction:
        instructions += "\n\nAdditional guidance:\n" + extra_instruction.strip()
    instructions += "\n\nAvailable information:\n" + context + "\n\nJob ad follows."

    user_content = [
        {"type": "input_text", "text": "Job ad:\n" + job_ad.strip()},
    ]

    # GPT-5 prefers reasoning/verbosity over temperature
    request_kwargs: Dict[str, Any] = {}
    model_lower = settings.responses_model.lower()
    reasoning_effort = "minimal"
    verbosity = "medium"
    if "gpt-5" in model_lower:
        request_kwargs["reasoning"] = {"effort": reasoning_effort}
        request_kwargs["text"] = {"verbosity": verbosity}
    else:
        if settings.responses_temperature is not None:
            request_kwargs["temperature"] = settings.responses_temperature

    resume_resp, resume_data = _call_resume_generation(
        client,
        instructions,
        user_content,
        request_kwargs,
    )

    package = {
        "job_title": resume_data.get("job_title", "").strip(),
        "summary": resume_data.get("summary", "").strip(),
        "experience": _normalize_plan_list(resume_data.get("experience", [])),
        "projects": _normalize_plan_list(resume_data.get("projects", [])),
        "skills": _normalize_skills(resume_data.get("skills", [])),
        "cover_letter": "",  # placeholder until second call
        "reasoning_effort": resume_data.get("reasoning_effort", reasoning_effort),
        "verbosity": resume_data.get("verbosity", verbosity),
    }

    if not package["experience"]:
        package["experience"] = [{"id": exp["id"], "bullets": exp.get("bullets", [])[:4]} for exp in master.get("experience", [])[:2]]

    if not package["projects"]:
        package["projects"] = [{"id": proj["id"], "bullets": proj.get("bullets", [])[:3]} for proj in master.get("projects", [])[:3]]

    if not package["skills"]:
        defaults = []
        for category, entries in master.get("skills", {}).items():
            for skill in entries:
                defaults.append({"id": skill["id"], "label": skill["label"]})
                if len(defaults) >= 6:
                    break
            if len(defaults) >= 6:
                break
        package["skills"] = defaults

    if not package["summary"]:
        package["summary"] = "Data and automation specialist aligning analytics, AI workflows, and modern web tooling to deliver measurable improvements."

    if not package["job_title"]:
        package["job_title"] = "Target Role"

    resume_html = build_resume_html(master, package)

    experience_ids = [entry.get("id") for entry in package["experience"] if entry.get("id")]
    project_ids = [entry.get("id") for entry in package["projects"] if entry.get("id")]
    skill_lookup, category_lookup, skill_to_category = _skill_label_maps(master)
    skill_labels = []
    for entry in package["skills"]:
        label = entry.get("label")
        if label:
            skill_labels.append(label)
        elif entry.get("id"):
            resolved = skill_lookup.get(entry["id"])
            if not resolved:
                category = skill_to_category.get(entry["id"])
                if category and category in category_lookup:
                    resolved = ", ".join(category_lookup[category])
            skill_labels.append(resolved or entry["id"])

    return {
        "package": package,
        "resume_html": resume_html,
        "experience_ids": experience_ids,
        "project_ids": project_ids,
        "skill_labels": skill_labels,
        "resume_token_count": _usage_output_tokens(resume_resp),
    }


def _extract_response_text(response) -> str:
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
    raise RuntimeError("Could not extract text from AI response")


def _normalize_plan_list(items: List[Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for item in items:
        if isinstance(item, str):
            normalized.append({"id": item.strip()})
        elif isinstance(item, dict):
            entry: Dict[str, Any] = {}
            if item.get("id"):
                entry["id"] = item["id"].strip()
            bullets = item.get("bullets") or []
            if bullets:
                entry["bullets"] = [str(b).strip() for b in bullets if str(b).strip()]
            if item.get("notes"):
                entry["notes"] = item["notes"].strip()
            if entry:
                normalized.append(entry)
    return normalized


def _normalize_skills(items: List[Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for item in items:
        if isinstance(item, str):
            label = item.strip()
            if label:
                normalized.append({"label": label})
        elif isinstance(item, dict):
            entry: Dict[str, Any] = {}
            if item.get("id"):
                entry["id"] = item["id"].strip()
            if item.get("label"):
                entry["label"] = item["label"].strip()
            if entry:
                normalized.append(entry)
    return normalized


def _skill_label_maps(
    master: Dict[str, Any]
) -> tuple[Dict[str, str], Dict[str, List[str]], Dict[str, str]]:
    skill_lookup: Dict[str, str] = {}
    category_lookup: Dict[str, List[str]] = {}
    skill_to_category: Dict[str, str] = {}
    for category, entries in master.get("skills", {}).items():
        category_lookup[category] = [entry["label"] for entry in entries]
        for entry in entries:
            skill_lookup[entry["id"]] = entry["label"]
            skill_lookup[entry["label"].lower()] = entry["label"]
            skill_to_category[entry["id"]] = category
    return skill_lookup, category_lookup, skill_to_category


def _build_cover_letter_outline(
    master: Dict[str, Any],
    experience_plan: List[Dict[str, Any]],
    project_plan: List[Dict[str, Any]],
    skills_plan: List[Dict[str, Any]],
) -> Dict[str, str]:
    experience_lookup = {exp["id"]: exp for exp in master.get("experience", [])}
    project_lookup = {proj["id"]: proj for proj in master.get("projects", [])}
    skill_lookup, category_lookup, skill_to_category = _skill_label_maps(master)

    exp_lines = []
    for item in experience_plan:
        exp_id = item.get("id")
        exp = experience_lookup.get(exp_id)
        if not exp:
            continue
        bullets = item.get("bullets") or exp.get("bullets", [])
        bullet_text = "; ".join(bullets[:4])
        exp_lines.append(f"- {exp['company']} — {exp['title']} ({exp['dates']}): {bullet_text}")

    proj_lines = []
    for item in project_plan:
        proj_id = item.get("id")
        proj = project_lookup.get(proj_id)
        if not proj:
            continue
        bullets = item.get("bullets") or proj.get("bullets", [])
        bullet_text = "; ".join(bullets[:4])
        proj_lines.append(f"- {proj['name']} ({proj['year']}): {bullet_text}")

    skill_labels = []
    for entry in skills_plan:
        if isinstance(entry, str):
            entry = {"label": entry}
        label = entry.get("label")
        skill_id = entry.get("id")
        resolved = None
        if label:
            resolved = label
        elif skill_id and skill_id in skill_lookup:
            resolved = skill_lookup[skill_id]
        elif skill_id and skill_id in skill_to_category:
            category = skill_to_category[skill_id]
            resolved = ", ".join(category_lookup.get(category, []))
        elif skill_id:
            resolved = skill_id
        if resolved:
            skill_labels.append(resolved)

    return {
        "experience_text": "\n".join(exp_lines),
        "project_text": "\n".join(proj_lines),
        "skills_text": ", ".join(skill_labels),
    }


def _usage_output_tokens(response: Any) -> Optional[int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    if isinstance(usage, dict):
        return usage.get("output_tokens")
    return getattr(usage, "output_tokens", None)


def _call_resume_generation(
    client: OpenAI,
    instructions: str,
    user_content: List[Dict[str, Any]],
    request_kwargs: Dict[str, Any],
) -> Tuple[Any, Dict[str, Any]]:
    resume_prompt = instructions + "\n\nReturn a resume plan only (no cover letter yet)."
    try:
        response = client.responses.create(
            model=settings.responses_model,
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": resume_prompt}]},
                {"role": "user", "content": user_content},
            ],
            **request_kwargs,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("OpenAI resume request failed")
        raise RuntimeError(f"OpenAI request failed: {exc}") from exc

    try:
        raw_text = _extract_response_text(response)
        data = json.loads(raw_text)
    except Exception as exc:  # noqa: BLE001
        raw_dump = None
        try:
            raw_dump = response.model_dump()
        except Exception:  # noqa: BLE001
            raw_dump = str(response)
        logger.error("Failed to parse resume response", extra={"response_dump": raw_dump})
        raise RuntimeError(f"Failed to parse AI response: {exc}") from exc
    return response, data


def generate_cover_letter_text(
    master_store: MasterStore,
    record: Dict[str, Any],
    instructions: str = "",
) -> Dict[str, Any]:
    if not settings.openai_api_key:
        raise RuntimeError("OpenAI API key not configured")

    master = master_store.get_master_snapshot()
    client = OpenAI(api_key=settings.openai_api_key)

    experience_plan = record.get("experience_plan") or [{"id": eid} for eid in record.get("experience_ids", [])]
    project_plan = record.get("project_plan") or [{"id": pid} for pid in record.get("project_ids", [])]
    skills_plan = record.get("skills_plan") or [{"label": label} for label in record.get("skill_labels", [])]

    resume_outline = _build_cover_letter_outline(master, experience_plan, project_plan, skills_plan)

    cover_system_prompt = (
        "You are writing a concise, first-person cover letter tailored to the provided job ad and resume outline.\n"
        "Respond with plain text only. Use 2-4 paragraphs separated by blank lines. Avoid JSON or markdown."
    )

    context_parts = [
        f"Target job title: {record.get('job_title', '').strip() or '(unspecified)'}",
        f"Resume summary: {record.get('summary', '').strip() or '(none)'}",
        "Experience selections:",
        resume_outline["experience_text"] or "(no experience selected)",
        "",
        "Project selections:",
        resume_outline["project_text"] or "(no projects selected)",
        "",
        "Highlighted skills:",
        resume_outline["skills_text"] or "(no skills highlighted)",
    ]

    cover_user_text = (
        "Job ad:\n"
        + (record.get("job_ad", "").strip() or "(job ad not provided)")
        + "\n\nResume outline:\n"
        + "\n".join(context_parts)
    )

    if instructions:
        cover_user_text += "\n\nAdditional instructions:\n" + instructions.strip()

    request_kwargs: Dict[str, Any] = {}
    model_lower = settings.responses_model.lower()
    if "gpt-5" in model_lower:
        request_kwargs["reasoning"] = {"effort": "minimal"}
        request_kwargs["text"] = {"verbosity": "medium"}
    elif settings.responses_temperature is not None:
        request_kwargs["temperature"] = settings.responses_temperature

    try:
        response = client.responses.create(
            model=settings.responses_model,
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": cover_system_prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": cover_user_text}]},
            ],
            **request_kwargs,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("OpenAI cover letter request failed")
        raise RuntimeError(f"OpenAI request failed while generating cover letter: {exc}") from exc

    try:
        cover_text = _extract_response_text(response)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to extract cover letter text", exc_info=True)
        raise RuntimeError(f"Failed to extract cover letter text: {exc}") from exc
    stripped = cover_text.strip()
    if stripped.startswith("{"):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict) and parsed.get("cover_letter"):
                cover_text = parsed["cover_letter"]
        except json.JSONDecodeError:
            pass
    return {
        "cover_letter": cover_text.strip(),
        "token_count": _usage_output_tokens(response),
    }


def _generate_cover_letter(
    client: OpenAI,
    master: Dict[str, Any],
    package: Dict[str, Any],
    job_ad: str,
    resume_html: str,
    resume_data: Dict[str, Any],
    request_kwargs: Dict[str, Any],
) -> Tuple[str, Any]:
    cover_instructions = (
        "You already built the resume. Now craft a 2-4 paragraph cover letter tailored to the role.\n"
        "Reference the chosen experience/projects where helpful. Output plain text only."
    )
    cover_user_content = [
        {
            "type": "input_text",
            "text": (
                "Job ad:\n"
                + job_ad.strip()
                + "\n\nResume summary:\n"
                + json.dumps(
                    {
                        "job_title": package.get("job_title"),
                        "summary": package.get("summary"),
                        "experience": package.get("experience"),
                        "projects": package.get("projects"),
                        "skills": package.get("skills"),
                    },
                    indent=2,
                )
            ),
        }
    ]
    cover_prompt = SYSTEM_PROMPT + "\n\n" + cover_instructions
    try:
        response = client.responses.create(
            model=settings.responses_model,
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": cover_prompt}]},
                {"role": "user", "content": cover_user_content},
            ],
            **request_kwargs,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("OpenAI cover letter request failed")
        raise RuntimeError(f"OpenAI request failed while generating cover letter: {exc}") from exc

    try:
        cover_text = _extract_response_text(response)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to extract cover letter text", exc_info=True)
        raise RuntimeError(f"Failed to extract cover letter text: {exc}") from exc
    return cover_text.strip(), response

