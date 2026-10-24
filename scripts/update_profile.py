"""Refresh the responsive metrics panels from GitHub's public repositories endpoint."""
import argparse
import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

USERNAME = "brunoflma"
ROOT = Path(__file__).resolve().parents[1]
ASSETS = (ROOT / "assets/lex-profile/activity-v4.svg", ROOT / "assets/lex-profile/activity-v4-mobile.svg")
LOCAL_ZONE = timezone(timedelta(hours=-3))  # America/Fortaleza
SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)


def fetch_repositories():
    headers = {"User-Agent": "brunoflma-profile", "Accept": "application/vnd.github+json"}
    if token := os.environ.get("PROFILE_GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    repositories = []
    for page in range(1, 101):
        url = f"https://api.github.com/users/{USERNAME}/repos?type=owner&per_page=100&page={page}"
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=25) as response:
            batch = json.load(response)
        if not isinstance(batch, list):
            raise TypeError("GitHub did not return a repository list")
        repositories.extend(batch)
        if len(batch) < 100:
            return repositories
    raise ValueError("Repository pagination limit reached; existing panels were preserved")


def summarize(repositories, today):
    projects = [
        r for r in repositories
        if r.get("visibility") == "public"
        and r.get("private") is False
        and r.get("owner", {}).get("login", "").lower() == USERNAME
        and not r.get("fork", True)
        and r["name"].lower() != USERNAME
    ]
    recent = sorted(
        (r for r in projects if not r.get("archived") and r.get("pushed_at")),
        key=lambda r: (r["pushed_at"], r["name"]), reverse=True,
    )[:3]
    return {"projects": len(projects), "stars": sum(r["stargazers_count"] for r in projects),
            "recent": [{"name": r["name"], "date": datetime.fromisoformat(
                r["pushed_at"].replace("Z", "+00:00")).astimezone(LOCAL_ZONE).date().isoformat()} for r in recent],
            "as_of": today.isoformat()}


def compact_number(value):
    if value < 1000:
        return str(value)
    divisor, suffix = (1_000_000, "M") if value >= 1_000_000 else (1000, "k")
    return f"{value / divisor:.1f}".replace(".", ",") + suffix


def render(source, data):
    tree = ET.fromstring(source)
    atlas = json.loads((ROOT / "scripts/profile-glyphs.json").read_text(encoding="utf-8"))
    mobile = tree.get("width") == "600"
    values = {"metric-projects": compact_number(data["projects"]),
              "metric-stars": compact_number(data["stars"]),
              "updated-at": "Atualizado em " + datetime.fromisoformat(data["as_of"]).strftime("%d/%m/%Y")}
    for index in range(3):
        item = data["recent"][index] if index < len(data["recent"]) else None
        name = item["name"] if item else "—"
        limit = 26 if mobile else 38
        values[f"recent-name-{index}"] = name if len(name) <= limit else name[:limit - 1] + "…"
        values[f"recent-date-{index}"] = datetime.fromisoformat(item["date"]).strftime("%d/%m") if item else ""
    for field, value in values.items():
        matches = tree.findall(f'.//{{{SVG}}}g[@id="{field}"]')
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one SVG field: {field}")
        target = matches[0]
        font = atlas[target.attrib["data-face"]]
        glyphs = [font["characters"][char] for char in value]
        size = float(target.attrib["data-size"])
        scale = size / font["units"]
        x, y = float(target.attrib["data-x"]), float(target.attrib["data-y"])
        if target.attrib["data-align"] == "center":
            x -= sum(glyph["advance"] for glyph in glyphs) * scale / 2
        x = round(x, 2)
        for child in list(target):
            target.remove(child)
        target.set("aria-label", value)
        drawing = ET.SubElement(target, f"{{{SVG}}}g", {
            "fill": target.attrib["data-color"],
            "transform": f"translate({x:g} {y:g}) scale({scale:.6f} {-scale:.6f})",
        })
        cursor = 0
        for glyph in glyphs:
            if glyph["path"]:
                ET.SubElement(drawing, f"{{{SVG}}}path", {
                    "transform": f"translate({cursor:.2f} 0)", "d": glyph["path"],
                })
            cursor += glyph["advance"]
    title, desc = tree.find(f"{{{SVG}}}title"), tree.find(f"{{{SVG}}}desc")
    if title is None or desc is None:
        raise ValueError("Missing SVG title or description")
    title.text = f"Atividade pública: {data['projects']} projetos e {data['stars']} estrelas"
    stamp = datetime.fromisoformat(data["as_of"]).strftime("%d/%m/%Y")
    desc.text = (f"Consulta em {stamp}. Projetos públicos próprios, sem forks e sem o repositório do perfil. "
                 "Datas em America/Fortaleza. Fonte: GitHub API.")
    return ET.tostring(tree, encoding="unicode")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="Update both local SVG files")
    mode.add_argument("--check", action="store_true", help="Fail when a panel needs refreshing")
    args = parser.parse_args()
    data = summarize(fetch_repositories(), datetime.now(LOCAL_ZONE).date())
    # Fetch and validate every output before touching either file.
    sources = {path: path.read_text(encoding="utf-8") for path in ASSETS}
    rendered = {path: render(source, data) for path, source in sources.items()}
    changed = [path for path in ASSETS if rendered[path] != sources[path]]
    if args.write:
        for path in changed:
            path.write_text(rendered[path], encoding="utf-8", newline="\n")
    print(json.dumps({**data, "changed_panels": len(changed)}, ensure_ascii=True))
    if args.check and changed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
