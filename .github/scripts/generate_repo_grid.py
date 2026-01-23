import os
import re
import json
import urllib.request
from typing import List, Dict

USERNAME = (os.getenv("GITHUB_USERNAME") or "").strip()
TOKEN = (os.getenv("GITHUB_TOKEN") or "").strip()

COLUMNS = int(os.getenv("COLUMNS", "3"))
CARD_WIDTH = int(os.getenv("CARD_WIDTH", "360"))
THEME = (os.getenv("THEME") or "tokyonight").strip()

SORT = (os.getenv("SORT") or "updated").strip().lower()  # updated | stars | name
EXCLUDE_FORKS = (os.getenv("EXCLUDE_FORKS") or "true").lower() == "true"
EXCLUDE_ARCHIVED = (os.getenv("EXCLUDE_ARCHIVED") or "true").lower() == "true"
MAX_REPOS = int(os.getenv("MAX_REPOS", "999"))

README_PATH = "README.md"
START = "<!-- REPO-GRID:START -->"
END = "<!-- REPO-GRID:END -->"

if not USERNAME:
    raise SystemExit("Missing GITHUB_USERNAME env var")

def gh_api(url: str):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "repo-grid-bot")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read().decode("utf-8"))

def fetch_all_public_repos(username: str) -> List[Dict]:
    repos: List[Dict] = []
    page = 1
    per_page = 100

    while True:
        url = f"https://api.github.com/users/{username}/repos?per_page={per_page}&page={page}&type=public&sort=updated"
        data = gh_api(url)
        if not data:
            break
        repos.extend(data)
        if len(data) < per_page:
            break
        page += 1

    return repos

def sort_repos(repos: List[Dict]) -> List[Dict]:
    if SORT == "stars":
        return sorted(repos, key=lambda r: (r.get("stargazers_count", 0), r.get("updated_at", "")), reverse=True)
    if SORT == "name":
        return sorted(repos, key=lambda r: (r.get("name", "").lower()))
    # default updated
    return sorted(repos, key=lambda r: (r.get("updated_at", "")), reverse=True)

def pin_card_html(repo_name: str) -> str:
    # Fixed-size “box” cards; title is centered automatically by the pin card image.
    # hide_border makes it look cleaner on both light/dark modes.
    src = (
        "https://github-readme-stats.vercel.app/api/pin/"
        f"?username={USERNAME}&repo={repo_name}&theme={THEME}&hide_border=true"
    )
    href = f"https://github.com/{USERNAME}/{repo_name}"
    return f'<a href="{href}"><img width="{CARD_WIDTH}" src="{src}" alt="{repo_name}" /></a>'

def build_grid_html(repos: List[Dict]) -> str:
    cards = []
    for r in repos[:MAX_REPOS]:
        name = r.get("name", "")
        if not name:
            continue
        cards.append(pin_card_html(name))

    if not cards:
        return "_No public repositories found._"

    # Build rows of N columns using HTML (more stable than markdown tables for image grids)
    lines = ['<p align="center">']
    for i, card in enumerate(cards, start=1):
        lines.append(card)
        # spacing
        if i % COLUMNS != 0:
            lines.append("&nbsp;")
        else:
            lines.append("<br/><br/>")
    # clean ending if last row didn't close with line breaks
    lines.append("</p>")
    return "\n".join(lines)

def replace_block(readme: str, new_content: str) -> str:
    if START not in readme or END not in readme:
        raise SystemExit(f"Markers not found in README.md. Add:\n{START}\n...\n{END}")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    return pattern.sub(f"{START}\n{new_content}\n{END}", readme)

def main():
    with open(README_PATH, "r", encoding="utf-8") as f:
        readme = f.read()

    repos = fetch_all_public_repos(USERNAME)

    if EXCLUDE_FORKS:
        repos = [r for r in repos if not r.get("fork", False)]
    if EXCLUDE_ARCHIVED:
        repos = [r for r in repos if not r.get("archived", False)]

    repos = sort_repos(repos)

    grid = build_grid_html(repos)
    updated = replace_block(readme, grid)

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(updated)

if __name__ == "__main__":
    main()
