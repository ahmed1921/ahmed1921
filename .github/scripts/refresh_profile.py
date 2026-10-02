"""Refresh repository cards and a contribution city using GitHub's own APIs."""

import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'assets'
USERNAME = os.environ.get('GITHUB_USERNAME', 'ahmed1921')


def api(path, body=None):
    token = os.environ.get('GITHUB_TOKEN', '')
    request = urllib.request.Request(
        'https://api.github.com/' + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'profile-dashboard',
            **({'Authorization': 'Bearer ' + token} if token else {}),
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def repositories():
    results = []
    page = 1
    while True:
        batch = api(f'users/{urllib.parse.quote(USERNAME)}/repos?type=public&per_page=100&page={page}')
        results.extend(batch)
        if len(batch) < 100:
            return results
        page += 1


def calendar():
    query = '''query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date weekday contributionCount } }
          }
        }
      }
    }'''
    result = api('graphql', {'query': query, 'variables': {'login': USERNAME}})
    if result.get('errors'):
        raise RuntimeError('GitHub contribution calendar query failed: ' +
                           '; '.join(e.get('message', 'unknown error') for e in result['errors']))
    return result['data']['user']['contributionsCollection']['contributionCalendar']


def t(x, y, label, size=20, color='#eef0fb', weight=400, mono=False):
    family = 'DejaVu Sans Mono, monospace' if mono else 'DejaVu Sans, Arial, sans-serif'
    return (f'<text x="{x}" y="{y}" fill="{color}" font-family="{family}" '
            f'font-size="{size}" font-weight="{weight}">{html.escape(str(label))}</text>')


def panel(width, height, body, title):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="{html.escape(title, quote=True)}">
    <title>{html.escape(title)}</title>
    <defs><linearGradient id="a"><stop stop-color="#35d7ed"/><stop offset="1" stop-color="#b695ff"/></linearGradient></defs>
    <style>.signal{{animation:pulse 3s ease-in-out infinite}}@keyframes pulse{{50%{{opacity:.35}}}}@media(prefers-reduced-motion:reduce){{*{{animation:none!important}}}}</style>
    <rect x="1" y="1" width="{width-2}" height="{height-2}" rx="22" fill="#0c0f1c" stroke="#2a324c"/>{body}</svg>\n'''


def repo_card(repo):
    name = repo['name']
    descriptions = {
        'School-VR-Multiplayer': ['Multiplayer VR classroom project.', 'Unity / XR / shared sessions'],
        'Color-Fill-3D': ['A recreation of hypercasual gameplay.', 'Unity / gameplay mechanics'],
    }
    description = repo.get('description') or 'Explore the source and project files.'
    lines = descriptions.get(name, [description[:58], description[58:116]])
    body = t(28, 39, 'REPOSITORY', 11, '#a4aec7', 500, True)
    body += t(28, 80, name[:36], 23, '#eef0fb', 700)
    for i, line in enumerate(lines):
        body += t(28, 115 + i * 25, line, 15, '#a4aec7')
    body += '<path d="M28 160H572" stroke="#2a324c"/>'
    language = repo.get('language') or 'Profile'
    body += '<circle cx="34" cy="186" r="5" fill="#35d7ed"/>'
    body += t(49, 191, language, 14, '#35d7ed')
    body += t(344, 191, f"STARS {repo.get('stargazers_count', 0)}", 12, '#b695ff', 400, True)
    body += t(464, 191, f"FORKS {repo.get('forks_count', 0)}", 12, '#a4aec7', 400, True)
    return panel(600, 216, body, f'{name}: {description}')


def refresh_repositories(repos):
    public = [r for r in repos if not r.get('private')]
    code = [r for r in public if not r.get('fork') and not r.get('archived') and r['name'] != USERNAME]
    priorities = {'School-VR-Multiplayer': 0, 'Color-Fill-3D': 1}
    code.sort(key=lambda r: (priorities.get(r['name'], 2), r['name'].lower()))
    rows = ['<table>']
    for i, repo in enumerate(code):
        if i % 2 == 0:
            rows.append('<tr>')
        # Use an opaque path so unusual repository names remain safe in Markdown and URLs.
        filename = 'repo-' + hashlib.sha256(repo['name'].encode()).hexdigest()[:12] + '.svg'
        (ASSETS / filename).write_text(repo_card(repo))
        href = html.escape(repo['html_url'], quote=True)
        name = html.escape(repo['name'], quote=True)
        rows.append(f'<td width="50%"><a href="{href}"><img src="assets/{filename}" width="100%" alt="{name}" /></a></td>')
        if i % 2 == 1:
            rows.append('</tr>')
    if len(code) % 2:
        rows.extend(['<td width="50%"></td>', '</tr>'])
    rows.append('</table>')
    grid = '\n'.join(rows) if code else '_No public code repositories to display._'
    readme_path = ROOT / 'README.md'
    readme = readme_path.read_text()
    start, end = '<!-- REPO-GRID:START -->', '<!-- REPO-GRID:END -->'
    pattern = re.compile(re.escape(start) + r'.*?' + re.escape(end), re.S)
    if len(pattern.findall(readme)) != 1:
        raise RuntimeError('README must contain exactly one repository grid marker pair')
    readme_path.write_text(pattern.sub(lambda _: start + '\n' + grid + '\n' + end, readme))
    today = datetime.now(timezone.utc).strftime('%d %b %Y')
    body = t(36, 39, 'PUBLIC GITHUB SNAPSHOT', 12, '#35d7ed', 600, True)
    metrics = [
        (36, len(public), 'PUBLIC REPOSITORIES'),
        (365, len([r for r in public if r.get('language') == 'C#']), 'C# REPOSITORIES'),
        (713, len(code), 'CODE REPOSITORIES'),
    ]
    for x, value, label in metrics:
        body += t(x, 93, value, 37, '#eef0fb', 700) + t(x, 123, label, 12, '#a4aec7', 500, True)
    body += t(1030, 84, 'REFRESHED', 11, '#a4aec7', 500, True)
    body += t(1030, 113, today, 17, '#b695ff')
    (ASSETS / 'github-snapshot.svg').write_text(panel(1280, 150, body, 'Public repository statistics, refreshed ' + today))


def city(data):
    weeks = data['weeks']
    counts = [d['contributionCount'] for w in weeks for d in w['contributionDays']]
    maximum = max(counts, default=0)
    palette = ['#35d7ed', '#57a6ea', '#9885ed', '#be91f7', '#fa8dc4']
    body = t(40, 48, 'CONTRIBUTION CITY / LAST 12 MONTHS', 14, '#35d7ed', 600, True)
    body += t(40, 92, 'A year of building, one day at a time.', 31, '#eef0fb', 700)
    body += t(40, 132, f"{data['totalContributions']:,} GitHub contributions · each tower represents one day", 19, '#a4aec7')
    # An isometric calendar: 52/53 weeks across, seven weekdays deep.
    dx, dy = 19.2, 4.1
    ox, oy = 182, 218
    days = [(wi, day) for wi, week in enumerate(weeks) for day in week['contributionDays']]
    for wi, day in sorted(days, key=lambda pair: (pair[0] + pair[1]['weekday'], pair[0])):
        dow = day['weekday']
        count = day['contributionCount']
        x, y = ox + (wi-dow)*dx, oy + (wi+dow)*dy
        height = 1 if count == 0 else 6 + 82 * math.log1p(count) / math.log1p(maximum)
        color = '#1a2339' if count == 0 else palette[min(4, int(4*count/max(1, maximum)))]
        tip = html.escape(f"{day['date']}: {count} contributions")
        body += f'<g><title>{tip}</title>'
        body += f'<path d="M{x-dx} {y}L{x} {y+dy}V{y+dy-height}L{x-dx} {y-height}Z" fill="{color}" fill-opacity=".5" stroke="#0c0f1c" stroke-width=".65"/>'
        body += f'<path d="M{x} {y+dy}L{x+dx} {y}V{y-height}L{x} {y+dy-height}Z" fill="{color}" fill-opacity=".75" stroke="#0c0f1c" stroke-width=".65"/>'
        body += f'<path d="M{x} {y-dy-height}L{x+dx} {y-height}L{x} {y+dy-height}L{x-dx} {y-height}Z" fill="{color}" stroke="#0c0f1c" stroke-width=".65"/></g>'
    first = weeks[0]['contributionDays'][0]['date']
    last = weeks[-1]['contributionDays'][-1]['date']
    body += t(40, 508, first + ' — ' + last, 13, '#a4aec7', 400, True)
    body += t(878, 508, 'LESS', 11, '#a4aec7', 400, True)
    for i, color in enumerate(['#1a2339']+palette):
        body += f'<rect x="{929+i*32}" y="492" width="23" height="19" rx="4" fill="{color}"/>'
    body += t(1138, 508, 'MORE', 11, '#a4aec7', 400, True)
    body += t(40, 548, 'Refreshed daily from GitHub’s contribution calendar.', 16, '#a4aec7')
    return panel(1280, 575, body, f"GitHub contribution city: {data['totalContributions']} contributions from {first} to {last}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repos-file', type=Path)
    parser.add_argument('--calendar-file', type=Path)
    parser.add_argument('--skip-calendar', action='store_true')
    args = parser.parse_args()
    ASSETS.mkdir(exist_ok=True)
    repos = json.loads(args.repos_file.read_text()) if args.repos_file else repositories()
    refresh_repositories(repos)
    if not args.skip_calendar:
        data = json.loads(args.calendar_file.read_text()) if args.calendar_file else calendar()
        (ASSETS / 'contribution-city.svg').write_text(city(data))


if __name__ == '__main__':
    main()
