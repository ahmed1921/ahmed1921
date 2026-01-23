import os, json, re, urllib.request

USERNAME = os.getenv("GITHUB_USERNAME")
TOKEN = os.getenv("GITHUB_TOKEN")
COLUMNS = int(os.getenv("COLUMNS", "3"))
THEME = os.getenv("THEME", "tokyonight")
EXCLUDE_FORKS = os.getenv("EXCLUDE_FORKS", "true") == "true"
SORT = os.getenv("SORT", "updated")

START = "<!-- REPO-GRID:START -->"
END = "<!-- REPO-GRID:END -->"

def gh(url):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    return json.loads(urllib.request.urlopen(req).read())

def fetch_repos():
    repos, page = [], 1
    while True:
        data = gh(f"https://api.github.com/users/{USERNAME}/repos?per_page=100&page={page}")
        if not data:
            break
        repos += data
        page += 1
    return repos

def sort_repos(repos):
    if SORT == "stars":
        return sorted(repos, key=lambda r: r["stargazers_count"], reverse=True)
    if SORT == "name":
        return sorted(repos, key=lambda r: r["name"].lower())
    return sorted(repos, key=lambda r: r["updated_at"], reverse=True)

def card(repo):
    name = repo["name"]
    return (
        f'<a href="https://github.com/{USERNAME}/{name}">'
        f'<img width="420" '
        f'src="https://github-readme-stats.vercel.app/api/pin/'
        f'?username={USERNAME}&repo={name}&theme={THEME}&hide_border=true" />'
        f'</a>'
    )

def build_grid(repos):
    cards = [card(r) for r in repos]
    rows = [cards[i:i+COLUMNS] for i in range(0, len(cards), COLUMNS)]
    header = "| " + " | ".join([" "] * COLUMNS) + " |"
    sep = "| " + " | ".join(["---"] * COLUMNS) + " |"
    table = [header, sep]
    for row in rows:
        row += [" "] * (COLUMNS - len(row))
        table.append("| " + " | ".join(row) + " |")
    return "\n".join(table)

def main():
    with open("README.md", "r", encoding="utf-8") as f:
        readme = f.read()
    repos = fetch_repos()
    if EXCLUDE_FORKS:
        repos = [r for r in repos if not r["fork"]]
    repos = sort_repos(repos)
    grid = build_grid(repos)
    new_block = f"{START}\n{grid}\n{END}"
    readme = re.sub(f"{START}[\s\S]*?{END}", new_block, readme)
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme)

if __name__ == "__main__":
    main()
