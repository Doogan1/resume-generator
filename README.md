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

## Create a new job
```bash
python scripts/new_job.py --name acme-ml-researcher --title "ML Researcher"
# Edit jobs/acme-ml-researcher.json (pick projects, choose summary_key, reorder skills)
python src/build.py --job jobs/acme-ml-researcher.json
```
