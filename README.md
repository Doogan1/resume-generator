# HTML Resume Builder

Dependency-free HTML resume system built from JSON content + per-job config.

## Quick start
```bash
python src/build.py --job jobs/schupan.json
# Output → dist/resume_schupan.html

# Or build and open in browser automatically:
python src/build.py --job jobs/schupan.json --open
```

Open the HTML and Print to PDF for submission.

## Structure

- `data/master.json` — canonical content atoms (summary, experience, projects, skills)
- `jobs/*.json` — per-job selection/config (title, summary_key, selected_projects, skills_order)
- `src/build.py` — assembler (no external deps)
- `templates/base.html` — logic-free HTML with {{tokens}}
- `themes/default.css` — print-friendly CSS
- `scripts/new_job.py` — helper to scaffold a new job config
- `dist/` — build outputs
- `api/server.py` — Flask API serving the Career Console + JSON CRUD
- `lib/json_store/` — schema-aware helpers for master/job data
- `ui/` — vanilla JS Career Console frontend

## Create a new job
```bash
python scripts/new_job.py --name acme-ml-researcher --title "ML Researcher"
# Edit jobs/acme-ml-researcher.json (pick projects, choose summary_key, reorder skills)
python src/build.py --job jobs/acme-ml-researcher.json
```

## Career Console (local data manager)

Quick UI for editing master data, skills catalog, and job configs.

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Launch the console (http://127.0.0.1:5050)
python -m api.server
```

Views:

- **Projects Dashboard** — edit project metadata, bullets, linked experience, and skills tags.
- **Skills Manager** — maintain the categorized skills catalog and inspect project usage.
- **Job Config Helper** — create/update `jobs/*.json` selections and labels.

All edits write back to the JSON files (`data/master.json`, `jobs/*.json`) so `src/build.py` continues to render tailored resumes. Future AI helpers can plug into `api/services/` without rewiring the UI.
