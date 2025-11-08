from __future__ import annotations

import pathlib
from typing import Any, Dict

from flask import Flask, abort, jsonify, request, send_from_directory

from lib.json_store import JobConfigStore, MasterStore

ROOT = pathlib.Path(__file__).resolve().parents[1]
UI_DIR = ROOT / "ui"

app = Flask(__name__, static_folder=str(UI_DIR), static_url_path="")
app.config["JSON_SORT_KEYS"] = False

master_store = MasterStore(ROOT / "data" / "master.json")
jobs_store = JobConfigStore(ROOT / "jobs", ROOT / "jobs" / "template.json")


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


def create_app():
    """Factory for testing."""
    return app


if __name__ == "__main__":
    app.run(debug=True, port=5050)

