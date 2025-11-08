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

Create a `.env` file next to this README to enable AI helpers:

```
OPENAI_API_KEY=sk-...
# Optional overrides
OPENAI_RESPONSES_MODEL=gpt-4.1-mini
OPENAI_RESPONSES_TEMPERATURE=0.35
```

Views:

- **Projects Dashboard** — edit project metadata, bullets, linked experience, and skills tags.
- **Skills Manager** — maintain the categorized skills catalog and inspect project usage.
- **Job Config Helper** — create/update `jobs/*.json` selections and labels.
- **Resume Generator** — paste a job posting to generate a tailored resume + cover letter (stored in `data/generated_docs.json` for later reference).
- **Settings** — manage reusable prompt guidance for AI project drafting, resumes, and cover letters.

All edits write back to the JSON files (`data/master.json`, `jobs/*.json`) so `src/build.py` continues to render tailored resumes. Future AI helpers can plug into `api/services/` without rewiring the UI.

### AI project drafting (optional)

With an OpenAI key configured, any project form includes an **AI Prompt Context** field:

1. Paste raw notes, metrics, or accomplishments.
2. Click **Draft with AI** (new projects) or **AI Rewrite** (existing projects).
3. The assistant calls the latest Responses API to:
   - Generate or refresh the project’s name, summary, bullets, and year.
   - Suggest skills; new skills are created automatically in the catalog.
   - Link referenced experience entries when possible.
4. Review the generated fields, tweak if needed, and save.

The AI schema lives in `api/services/ai_projects.py`, ready for future expansions (e.g., summary rewrites, job-config suggestions).

### Resume + cover letter generation

Use the **Resume Generator** tab to paste a job description. The system will:

1. Analyze the posting alongside your canonical data in `data/master.json`.
2. Produce a tailored resume (rendered with the default theme). Review it, then supply optional guidance and click **Generate Cover Letter** to draft the letter whenever you're ready.
3. Store each package (metadata + pointers) in `data/generated_docs.json` with the actual assets written to `data/generated/<package_id>/resume.html` and `.../cover_letter.txt`. You can edit both files directly from the UI (textarea editors) or via the filesystem.

Outputs honor GPT‑5’s controls (reasoning effort, verbosity) and can be reviewed or exported directly from the console.

#### PDF exports

- Install [wkhtmltopdf](https://wkhtmltopdf.org/) and ensure its binary is on your `PATH`. On Windows, install the official `.msi` and optionally set `WKHTMLTOPDF_PATH` in `.env` to the installed executable (e.g., `C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe`).
- Install Python deps (`pip install -r requirements.txt`).
- In the Resume Generator detail view, use **Export PDFs** to render `resume.pdf` and `cover_letter.pdf` beside the HTML/text assets under `data/generated/<package_id>/`.

### Prompt settings

Use the **Settings** tab to maintain extra system instructions for:

- Project generation (`project_extra_instruction`)
- Resume generation (`resume_extra_instruction`)
- Cover letter generation (`cover_letter_extra_instruction`)

These strings live in `data/prompts.json`, are appended to every AI call, and help you reinforce tone (e.g., “stay truthful, avoid exaggeration”). You can still provide per-cover-letter guidance when generating letters from the resume tab.

- Use **Open Resume in Browser** to launch the generated HTML and rely on your browser’s print-to-PDF for finely tuned output if you prefer a manual export path.
