#!/usr/bin/env python3
import json, argparse, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]

def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def render(template: str, tokens: dict) -> str:
    out = template
    for k, v in tokens.items():
        out = out.replace("{{"+k+"}}", v)
    return out

def bullets_to_html(bullets):
    return "".join([f"<li>{b}</li>" for b in bullets])

def assemble_experience(data, job):
    items = []
    for exp in data["experience"]:
        if exp["company"] == "Freelance" and not job.get("show_freelance", True):
            continue
        items.append(f'''
        <div class="item">
          <div class="meta">
            <div class="left">{exp["company"]} — {exp["title"]}</div>
            <div class="right">{exp["dates"]}</div>
          </div>
          <ul>{bullets_to_html(exp["bullets"])}</ul>
        </div>''')
    return "\n".join(items)

def assemble_projects(data, job):
    selections = set(job.get("selected_projects", []))
    items = []
    for p in data["projects"]:
        pid = p.get("id")
        include = p["name"] in selections or (pid and pid in selections)
        if not include:
            continue
        items.append(f'''
        <div class="item">
          <div class="meta">
            <div class="left">{p["name"]}</div>
            <div class="right">{p["year"]}</div>
          </div>
          <ul>{bullets_to_html(p["bullets"])}</ul>
        </div>''')
    return "\n".join(items)

def assemble_skills(data, job):
    order = job["skills_order"]
    label_map = job["skills_label_map"]
    blocks = []
    for key in order:
        label = label_map.get(key, key.title())
        items = data["skills"].get(key, [])
        labels = []
        for item in items:
            if isinstance(item, dict):
                labels.append(item.get("label", "").strip())
            else:
                labels.append(str(item).strip())
        labels = [l for l in labels if l]
        blocks.append(
            f'<div class="skill-block"><div class="label">{label}</div><div class="list">{", ".join(labels)}</div></div>'
        )
    return "\n".join(blocks)

def links_html(contact):
    return " &nbsp;•&nbsp; ".join([f'<a href="{l["url"]}">{l["label"]}</a>' for l in contact["links"]])

def main():
    parser = argparse.ArgumentParser(description="Build HTML resume from JSON content.")
    parser.add_argument("--job", required=True, help="Path to job config JSON (e.g., jobs/schupan.json)")
    parser.add_argument("--open", action="store_true", help="Open the generated HTML file in browser")
    args = parser.parse_args()

    master = read_json(ROOT / "data" / "master.json")
    job = read_json(ROOT / args.job)

    template = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    summary_key = job.get("summary_key", "default")
    summary = master["summary"].get(summary_key, master["summary"]["default"])

    tokens = {
        "name": master["name"],
        "target_title": job.get("title",""),
        "phone": master["contact"]["phone"],
        "email": master["contact"]["email"],
        "location": master["contact"]["location"],
        "links_html": links_html(master["contact"]),
        "summary": summary,
        "experience_html": assemble_experience(master, job),
        "projects_html": assemble_projects(master, job),
        "skills_html": assemble_skills(master, job),
        "date": datetime.date.today().strftime("%b %d, %Y"),
    }

    html = render(template, tokens)
    out = ROOT / "dist" / f"resume_{pathlib.Path(args.job).stem}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out}")
    
    if args.open:
        import webbrowser
        webbrowser.open(f"file://{out.absolute()}")
        print(f"Opened {out} in browser")

if __name__ == "__main__":
    main()
