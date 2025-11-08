#!/usr/bin/env python3
import json, argparse, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "jobs" / "template.json"

def main():
    p = argparse.ArgumentParser(description="Create a new job config from template.json")
    p.add_argument("--name", required=True, help="Job config name (e.g., acme-ml-researcher)")
    p.add_argument("--title", required=True, help="Target role title (e.g., ML Researcher)")
    args = p.parse_args()

    dest = ROOT / "jobs" / f"{args.name}.json"
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    data["title"] = args.title
    dest.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Created {dest}\nEdit selected_projects, summary_key, skills_order as needed.")

if __name__ == "__main__":
    main()
