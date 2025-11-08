from __future__ import annotations

import html
import logging
import pathlib
import time
from typing import Any, Dict

from flask import Flask, abort, jsonify, request, send_from_directory

from api.services.ai_projects import AIProjectError, generate_project_from_context
from api.services.ai_resume import generate_resume_package, generate_cover_letter_text
from api.settings import settings
from lib.json_store import GenerationStore, JobConfigStore, MasterStore, PromptStore

try:
    import pdfkit
except Exception:  # noqa: BLE001
    pdfkit = None


def _pdfkit_configuration():
    if pdfkit is None:
        return None
    wkhtml_path = settings.wkhtmltopdf_path
    try:
        if wkhtml_path:
            return pdfkit.configuration(wkhtmltopdf=wkhtml_path)
        return pdfkit.configuration()
    except (OSError, IOError) as exc:  # noqa: B909
        raise RuntimeError(
            "wkhtmltopdf binary not found. Install wkhtmltopdf and/or set WKHTMLTOPDF_PATH."
        ) from exc


ROOT = pathlib.Path(__file__).resolve().parents[1]
UI_DIR = ROOT / "ui"

app = Flask(__name__, static_folder=str(UI_DIR), static_url_path="")
app.config["JSON_SORT_KEYS"] = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("career_console")

master_store = MasterStore(ROOT / "data" / "master.json")
jobs_store = JobConfigStore(ROOT / "jobs", ROOT / "jobs" / "template.json")
generations_store = GenerationStore(
    ROOT / "data" / "generated_docs.json",
    ROOT / "data" / "generated"
)
prompt_store = PromptStore(ROOT / "data" / "prompts.json")

GENERATED_DIR = ROOT / "data" / "generated"


def _send_generated_asset(asset_path: str):
    safe_path = pathlib.Path(asset_path)
    full_path = (GENERATED_DIR / safe_path).resolve()
    if not full_path.is_file() or not full_path.is_relative_to(GENERATED_DIR.resolve()):
        abort(404)
    relative = full_path.relative_to(GENERATED_DIR)
    return send_from_directory(GENERATED_DIR, relative.as_posix())


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def json_response(data: Any = None, *, meta: Dict[str, Any] | None = None, status: int = 200):
    payload = {"data": data}
    if meta:
        payload["meta"] = meta
    return jsonify(payload), status


@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(500)
def handle_error(err):
    status = getattr(err, "code", 500)
    description = getattr(err, "description", str(err))
    return jsonify({"error": {"message": description, "status": status}}), status


# ---------------------------------------------------------------------------
# Static UI
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    return send_from_directory(UI_DIR, "index.html")


# ---------------------------------------------------------------------------
# AI helpers
# ---------------------------------------------------------------------------
@app.post("/api/ai/projects")
def api_ai_project_generate():
    if not settings.openai_api_key:
        abort(400, description="OpenAI API key not configured. Set OPENAI_API_KEY in .env.")

    payload = request.get_json(force=True, silent=False) or {}
    context = (payload.get("context") or "").strip()
    if not context:
        abort(400, description="context is required")

    project_id = payload.get("project_id")
    existing_project = None
    if project_id:
        existing_project = next((p for p in master_store.list_projects() if p.get("id") == project_id), None)
        if not existing_project:
            abort(404, description=f"Project '{project_id}' not found")

    logger.info(
        "AI project request start",
        extra={
            "context_chars": len(context),
            "project_id": project_id,
            "has_existing_project": bool(existing_project),
        },
    )
    start_time = time.perf_counter()
    prompts = prompt_store.get_prompts()

    try:
        project_payload = generate_project_from_context(
            master_store,
            context=context,
            existing_project=existing_project,
            extra_instruction=prompts.get("project_extra_instruction", ""),
        )
    except AIProjectError as exc:
        logger.exception("AI project request failed")
        abort(400, description=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error during AI project request")
        abort(500, description=f"Unexpected AI error: {exc}")
    finally:
        duration = time.perf_counter() - start_time
        logger.info(
            "AI project request complete",
            extra={
                "project_id": project_id,
                "duration_seconds": round(duration, 2),
            },
        )

    skill_specs = project_payload.pop("skills", [])
    experience_refs = project_payload.pop("linked_experience", [])

    skill_ids = master_store.ensure_skills(skill_specs)
    experience_ids = []
    for reference in experience_refs:
        if isinstance(reference, dict):
            reference = reference.get("id") or reference.get("lookup") or reference.get("name")
        exp_id = master_store.find_experience_id(str(reference))
        if exp_id:
            experience_ids.append(exp_id)

    project_data = {
        "name": project_payload.get("name", ""),
        "year": project_payload.get("year", ""),
        "description_short": project_payload.get("description_short", ""),
        "bullets": project_payload.get("bullets", []),
        "skills_used": skill_ids,
        "linked_experience": experience_ids,
    }

    if existing_project:
        saved = master_store.update_project(existing_project["id"], project_data)
        meta = {"action": "updated", "project_id": existing_project["id"], "skills_used": skill_ids}
    else:
        saved = master_store.create_project(project_data)
        meta = {"action": "created", "project_id": saved["id"], "skills_used": skill_ids}

    logger.info(
        "AI project write success",
        extra={
            "project_id": saved["id"],
            "action": meta["action"],
            "skills_used": skill_ids,
            "bullets": len(project_data.get("bullets", [])),
        },
    )

    return json_response(saved, meta=meta, status=201 if not existing_project else 200)


@app.get("/api/ai/resumes")
def api_ai_resume_list():
    items = generations_store.list_items()
    return json_response(items, meta={"count": len(items)})


@app.get("/api/ai/resumes/<item_id>")
def api_ai_resume_get(item_id):
    item = generations_store.get_item(item_id)
    if not item:
        abort(404, description=f"Generated resume '{item_id}' not found")
    return json_response(item)


@app.post("/api/ai/resumes")
def api_ai_resume_generate():
    payload = request.get_json(force=True, silent=False) or {}
    job_ad = (payload.get("job_ad") or "").strip()
    if not job_ad:
        abort(400, description="job_ad is required")

    logger.info("AI resume generation start", extra={"job_ad_chars": len(job_ad)})
    start_time = time.perf_counter()
    try:
        prompts = prompt_store.get_prompts()
        result = generate_resume_package(
            master_store,
            job_ad=job_ad,
            extra_instruction=prompts.get("resume_extra_instruction", ""),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("AI resume generation failed")
        abort(400, description=str(exc))
    duration = time.perf_counter() - start_time

    package = result["package"]
    prompts = prompt_store.get_prompts()

    record = generations_store.create_item(
        {
            "job_title": package.get("job_title", ""),
            "job_ad": job_ad,
            "summary": package.get("summary", ""),
            "resume_html": result["resume_html"],
            "cover_letter": package.get("cover_letter", ""),
            "experience_ids": result["experience_ids"],
            "project_ids": result["project_ids"],
            "skill_labels": result["skill_labels"],
            "reasoning_effort": package.get("reasoning_effort"),
            "verbosity": package.get("verbosity"),
            "resume_token_count": result.get("resume_token_count"),
            "cover_letter_token_count": None,
            "experience_plan": package.get("experience"),
            "project_plan": package.get("projects"),
            "skills_plan": package.get("skills"),
        }
    )
    logger.info(
        "AI resume generation success",
        extra={
            "resume_id": record["id"],
            "duration_seconds": round(duration, 2),
            "experience_count": len(record["experience_ids"]),
            "project_count": len(record["project_ids"]),
        },
    )
    return json_response(record, status=201)


@app.post("/api/ai/resumes/<item_id>/cover-letter")
def api_ai_resume_cover_letter(item_id):
    payload = request.get_json(force=True, silent=False) or {}
    instructions = (payload.get("instructions") or "").strip()
    manual_text = payload.get("cover_letter")

    record = generations_store.get_item(item_id)
    if not record:
        abort(404, description=f"Generated resume '{item_id}' not found")

    if manual_text is not None:
        updated = generations_store.update_item(
            item_id,
            {
                "cover_letter": manual_text,
                "cover_letter_token_count": None,
            },
        )
        if not updated:
            abort(404, description=f"Generated resume '{item_id}' not found")
        logger.info("Manual cover letter update", extra={"resume_id": item_id})
        return json_response(updated)

    prompts = prompt_store.get_prompts()
    combined_instructions = "\n".join(
        part for part in [prompts.get("cover_letter_extra_instruction", ""), instructions] if part
    )

    logger.info(
        "AI cover letter generation start",
        extra={"resume_id": item_id, "has_instructions": bool(instructions)},
    )
    start_time = time.perf_counter()
    try:
        result = generate_cover_letter_text(master_store, record, combined_instructions)
    except Exception as exc:  # noqa: BLE001
        logger.exception("AI cover letter generation failed")
        abort(400, description=str(exc))
    duration = time.perf_counter() - start_time

    updated = generations_store.update_item(
        item_id,
        {
            "cover_letter": result["cover_letter"],
            "cover_letter_token_count": result.get("token_count"),
        },
    )
    logger.info(
        "AI cover letter generation success",
        extra={
            "resume_id": item_id,
            "duration_seconds": round(duration, 2),
        },
    )
    return json_response(updated)


@app.put("/api/ai/resumes/<item_id>/resume")
def api_ai_resume_update_html(item_id):
    payload = request.get_json(force=True, silent=False) or {}
    resume_html = payload.get("resume_html")
    if resume_html is None:
        abort(400, description="resume_html is required")

    updated = generations_store.update_item(
        item_id,
        {
            "resume_html": resume_html,
        },
    )
    if not updated:
        abort(404, description=f"Generated resume '{item_id}' not found")
    logger.info("Manual resume HTML update", extra={"resume_id": item_id})
    return json_response(updated)


@app.put("/api/ai/resumes/<item_id>")
def api_ai_resume_update_metadata(item_id):
    payload = request.get_json(force=True, silent=False) or {}
    updates = {}
    if "job_title" in payload:
        updates["job_title"] = (payload["job_title"] or "").strip()
    if not updates:
        abort(400, description="No supported fields provided")

    updated = generations_store.update_item(item_id, updates)
    if not updated:
        abort(404, description=f"Generated resume '{item_id}' not found")
    logger.info("Resume metadata update", extra={"resume_id": item_id})
    return json_response(updated)


@app.post("/api/ai/resumes/<item_id>/export")
def api_ai_resume_export(item_id):
    if pdfkit is None:
        abort(500, description="pdfkit is not installed. Run `pip install pdfkit`." )

    record = generations_store.get_item(item_id)
    if not record:
        abort(404, description=f"Generated resume '{item_id}' not found")

    resume_html = record.get("resume_html", "")
    if not resume_html.strip():
        abort(400, description="Resume HTML is empty; generate or edit it before exporting.")

    try:
        config = _pdfkit_configuration()
    except RuntimeError as exc:
        abort(500, description=str(exc))

    resume_rel, resume_pdf_path = generations_store.resume_pdf_paths(item_id)
    cover_rel, cover_pdf_path = generations_store.cover_letter_pdf_paths(item_id)
    resume_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    cover_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    options = {"quiet": ""}

    try:
        pdfkit.from_string(resume_html, str(resume_pdf_path), configuration=config, options=options)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to export resume PDF")
        abort(500, description=f"Failed to export resume PDF: {exc}")

    cover_letter_text = record.get("cover_letter", "").strip()
    if not cover_letter_text:
        cover_letter_text = "(Cover letter intentionally left blank.)"
    cover_letter_html = f"""
    <html>
      <head><meta charset=\"utf-8\"></head>
      <body style=\"font-family: 'Segoe UI', sans-serif; font-size: 12pt; white-space: pre-wrap; line-height: 1.4;\">
        {html.escape(cover_letter_text)}
      </body>
    </html>
    """
    try:
        pdfkit.from_string(cover_letter_html, str(cover_pdf_path), configuration=config, options=options)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to export cover letter PDF")
        abort(500, description=f"Failed to export cover letter PDF: {exc}")

    updated = generations_store.update_item(
        item_id,
        {
            "resume_pdf_path": resume_rel,
            "cover_letter_pdf_path": cover_rel,
        },
    )
    logger.info(
        "Exported PDFs",
        extra={
            "resume_id": item_id,
            "resume_pdf": resume_rel,
            "cover_pdf": cover_rel,
        },
    )
    return json_response(updated)


@app.delete("/api/ai/resumes/<item_id>")
def api_ai_resume_delete(item_id):
    deleted = generations_store.delete_item(item_id)
    if not deleted:
        abort(404, description=f"Generated resume '{item_id}' not found")
    return json_response({"deleted": item_id})


# ---------------------------------------------------------------------------
# Master data endpoints
# ---------------------------------------------------------------------------
@app.get("/api/projects")
def api_list_projects():
    projects = master_store.list_projects()
    return json_response(projects, meta={"count": len(projects)})


@app.post("/api/projects")
def api_create_project():
    payload = request.get_json(force=True, silent=False) or {}
    try:
        project = master_store.create_project(payload)
    except ValueError as exc:
        abort(400, description=str(exc))
    return json_response(project, status=201)


@app.put("/api/projects/<project_id>")
def api_update_project(project_id):
    payload = request.get_json(force=True, silent=False) or {}
    try:
        project = master_store.update_project(project_id, payload)
    except KeyError as exc:
        abort(404, description=str(exc))
    return json_response(project)


@app.delete("/api/projects/<project_id>")
def api_delete_project(project_id):
    try:
        result = master_store.delete_project(project_id)
    except KeyError as exc:
        abort(404, description=str(exc))
    return json_response(result)


@app.get("/api/skills")
def api_list_skills():
    skills = master_store.list_skills(include_usage=True)
    meta = {
        "categories": list(skills.keys()),
        "count": sum(len(entries) for entries in skills.values()),
    }
    return json_response(skills, meta=meta)


@app.post("/api/skills")
def api_add_skill():
    payload = request.get_json(force=True, silent=False) or {}
    category = payload.get("category", "")
    label = payload.get("label", "")
    try:
        entry = master_store.add_skill(category, label)
    except ValueError as exc:
        abort(400, description=str(exc))
    return json_response(entry, status=201)


@app.put("/api/skills/<category>/<skill_id>")
def api_update_skill(category, skill_id):
    payload = request.get_json(force=True, silent=False) or {}
    label = payload.get("label", "")
    try:
        entry = master_store.update_skill(category, skill_id, label)
    except KeyError as exc:
        abort(404, description=str(exc))
    return json_response(entry)


@app.delete("/api/skills/<category>/<skill_id>")
def api_delete_skill(category, skill_id):
    try:
        result = master_store.delete_skill(category, skill_id)
    except KeyError as exc:
        abort(404, description=str(exc))
    return json_response(result)


@app.get("/api/experience")
def api_list_experience():
    experience = master_store.list_experience()
    return json_response(experience, meta={"count": len(experience)})


@app.post("/api/experience")
def api_create_experience():
    payload = request.get_json(force=True, silent=False) or {}
    try:
        result = master_store.create_experience(payload)
    except ValueError as exc:
        abort(400, description=str(exc))
    return json_response(result, status=201)


@app.put("/api/experience/<experience_id>")
def api_update_experience(experience_id):
    payload = request.get_json(force=True, silent=False) or {}
    try:
        result = master_store.update_experience(experience_id, payload)
    except KeyError as exc:
        abort(404, description=str(exc))
    return json_response(result)


@app.delete("/api/experience/<experience_id>")
def api_delete_experience(experience_id):
    try:
        result = master_store.delete_experience(experience_id)
    except KeyError as exc:
        abort(404, description=str(exc))
    return json_response(result)


@app.get("/api/summaries")
def api_summary_keys():
    keys = master_store.list_summary_keys()
    return json_response(keys, meta={"count": len(keys)})


@app.get("/api/master")
def api_master_snapshot():
    snapshot = master_store.get_master_snapshot()
    return json_response(snapshot)


# ---------------------------------------------------------------------------
# Job configs
# ---------------------------------------------------------------------------
@app.get("/api/jobs")
def api_list_jobs():
    jobs = jobs_store.list_configs()
    return json_response(jobs, meta={"count": len(jobs)})


@app.get("/api/jobs/<slug>")
def api_get_job(slug):
    try:
        job = jobs_store.get_config(slug)
    except FileNotFoundError as exc:
        abort(404, description=str(exc))
    return json_response(job | {"slug": slug})


@app.post("/api/jobs")
def api_create_job():
    payload = request.get_json(force=True, silent=False) or {}
    slug = payload.get("slug")
    if not slug:
        abort(400, description="slug is required")
    try:
        job = jobs_store.create_config(slug, payload)
    except FileExistsError as exc:
        abort(400, description=str(exc))
    except FileNotFoundError as exc:
        abort(500, description=str(exc))
    return json_response(job, status=201)


@app.put("/api/jobs/<slug>")
def api_update_job(slug):
    payload = request.get_json(force=True, silent=False) or {}
    try:
        job = jobs_store.update_config(slug, payload)
    except FileNotFoundError as exc:
        abort(404, description=str(exc))
    return json_response(job)


@app.delete("/api/jobs/<slug>")
def api_delete_job(slug):
    try:
        result = jobs_store.delete_config(slug)
    except FileNotFoundError as exc:
        abort(404, description=str(exc))
    return json_response(result)


# ---------------------------------------------------------------------------
# Prompt settings
# ---------------------------------------------------------------------------
@app.get("/api/prompts")
def api_get_prompts():
    prompts = prompt_store.get_prompts()
    return json_response(prompts)


@app.put("/api/prompts")
def api_update_prompts():
    payload = request.get_json(force=True, silent=False) or {}
    prompts = prompt_store.update_prompts(payload)
    return json_response(prompts)


@app.get("/generated/<path:asset_path>")
def api_generated_asset(asset_path):
    return _send_generated_asset(asset_path)


@app.get("/api/ai/resumes/<item_id>/resume-html")
def api_ai_resume_open_html(item_id):
    record = generations_store.get_item(item_id)
    if not record:
        abort(404, description=f"Generated resume '{item_id}' not found")
    path = record.get("resume_path")
    if not path:
        abort(404, description="Resume HTML path not found")
    return _send_generated_asset(path)


@app.get("/api/ai/resumes/<item_id>/cover-letter-txt")
def api_ai_resume_open_cover_letter(item_id):
    record = generations_store.get_item(item_id)
    if not record:
        abort(404, description=f"Generated resume '{item_id}' not found")
    path = record.get("cover_letter_path")
    if not path:
        abort(404, description="Cover letter path not found")
    return _send_generated_asset(path)


def create_app():
    """Factory for testing."""
    return app


if __name__ == "__main__":
    app.run(debug=True, port=5050)

