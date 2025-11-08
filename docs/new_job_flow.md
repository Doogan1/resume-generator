## New Job Flow

This guide documents the full “found a new job posting → tailor resume output” process so you can hand context to ChatGPT (or any assistant) and get actionable help editing `data/master.json` and producing the right `jobs/*.json` config.

### 1. Provide Context to the Assistant

- Share the high‑level repo shape:
  - `data/master.json`: canonical experience, projects, skills, summaries.
  - `jobs/<name>.json`: per‑job selections plus display settings.
  - `scripts/new_job.py`: scaffold for new job configs.
  - `src/build.py`: assembler that renders `templates/base.html` with selected data.
- Paste the relevant slices of `master.json` so the assistant can see current content (or at least the portions you expect to change).
- Supply the target job description or extracted requirements (must‑have skills, responsibilities, keywords) so it can map to existing assets or suggest new ones.

### 2. Collect Raw Inputs

1. **Job requirements** — summarize the posting in bullets:
   - core responsibilities / problems to solve,
   - tech stack / tools,
   - measurable outcomes they care about.
2. **Your supporting material** — list experiences and projects that map to those requirements, including quantities, technologies, and results.
3. **Gap notes** — flag anything missing so the assistant knows to suggest net-new bullets or skill entries.

### 3. Update `data/master.json`

Ask the assistant for edits in structured form. Typical operations:

- **Add experience bullets**: either append to an existing role or introduce a new object with `company`, `title`, `dates`, `bullets`.
- **Add projects**: each project needs `name`, `year`, `bullets` (2–3 concise, impact-focused lines).
- **Expand skills**: insert new strings into the correct arrays (`programming_data`, `ai_automation`, etc.) or propose a new category if there’s a better grouping.
- **Create summary variants**: add a new key/value under the `summary` object (e.g., `"acme_ml": "..."`) tuned to the job’s theme.

When handing work back to the repo, you can ask the assistant to emit JSON patches for the specific sections so you can copy/paste into `master.json` without manual merging.

### 4. Create/Update the Job Config

Steps for `jobs/<name>.json`:

1. Run `python scripts/new_job.py --name <slug> --title "<Role Title>"` if a new config is needed.
2. Edit fields:
   - `title`: what appears on the resume.
   - `summary_key`: one of the keys in `master.summary`.
   - `selected_projects`: array of project `name` strings from `master.projects` to show.
   - `show_freelance`: toggle the freelance experience.
   - `skills_order`: reorder categories to match the posting.
   - `skills_label_map`: rename sections for tone/clarity.
3. Let the assistant draft the JSON with the right selections once it knows which experiences/projects/skills you want emphasized.

### 5. Build and Review

- Run `python src/build.py --job jobs/<name>.json [--open]`.
- Inspect `dist/resume_<name>.html`.
- Iterate: tweak bullets, summaries, project selection, or ordering until it reads naturally and hits the posting’s keywords.

### 6. Tips for Assistant Collaboration

- Request focused prompts, e.g., “Suggest two quantified bullets for my county AI role that align with automation cost savings.”
- Ask for diff-friendly output (`json` snippets or bullet lists) to reduce manual editing mistakes.
- Keep track of reusable content. If an assistant creates new bullets or projects, paste them back into `master.json` so future job configs can reference them.

With this checklist you can drop the file into a ChatGPT conversation, provide the job description, and have it co-write updates to `master.json` plus the matching `jobs/<name>.json` config.

