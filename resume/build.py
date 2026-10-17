"""Build profile/resume.pdf from profile/*.json and resume/resume.json.

Usage: python3 resume/build.py [--html PATH]
Renders the resume as HTML, then prints it to PDF with headless Chromium
(Microsoft Edge by default; override with RESUME_BROWSER=/path/to/chrome).
--html also saves the rendered page, for previewing design changes in a browser.
"""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "profile"
PDF_OUT = PROFILE / "resume.pdf"
BROWSER = os.environ.get(
    "RESUME_BROWSER", "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
)
MONTHS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]
# Bullets per role, newest first; older roles are condensed to keep the resume at 2 pages.
BULLETS = (5, 5, 2, 2, 1, 1)
DETAILED_ROLES = 2  # roles that also show their summary line
MAX_TECH = (14, 9)  # tech chips for the newest role, then for the rest

FONTS = (
    "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400"
    "&family=JetBrains+Mono:wght@400;500&family=Space+Grotesk:wght@500;600;700&display=block"
)

# Lucide icons (stroke paths, 24x24 viewBox).
ICONS = {
    "mail": '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    "phone": '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
    "map-pin": '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
    "github": '<path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/>',
    "linkedin": '<path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect width="4" height="12" x="2" y="9"/><circle cx="4" cy="4" r="2"/>',
}

CSS = """
:root {
  --ink: #09090b; --ink-2: #3f3f46; --muted: #52525b; --line: #e4e4e7;
  --chip: #f4f4f5; --accent: #2563eb;
  --sans: "IBM Plex Sans", "Helvetica Neue", Arial, sans-serif;
  --display: "Space Grotesk", "Helvetica Neue", Arial, sans-serif;
  --mono: "JetBrains Mono", Menlo, Consolas, monospace;
}
@page { size: A4; margin: 11mm 13mm; }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { margin: 0; font: 9pt/1.45 var(--sans); color: var(--ink-2); }
a { color: inherit; text-decoration: none; }
p { margin: 0 0 4px; }
ul { margin: 3px 0 4px; padding-left: 13px; }
li { margin-bottom: 1.5px; break-inside: avoid; }
li::marker { color: var(--accent); }

header { padding-bottom: 9px; border-bottom: 1px solid var(--line); }
header::before { content: ""; display: block; width: 30px; height: 3px; margin-bottom: 9px;
  border-radius: 2px; background: var(--accent); }
h1 { margin: 0; font: 700 25pt/1.05 var(--display); letter-spacing: -0.02em; color: var(--ink); }
.headline { margin: 5px 0 8px; font: 500 10.5pt/1.3 var(--display); color: var(--ink-2); }
.headline b { color: var(--accent); font-weight: 600; }
.contacts { display: flex; flex-wrap: wrap; gap: 3px 15px; margin: 0; padding: 0; list-style: none;
  font: 7.9pt/1.4 var(--mono); color: var(--muted); }
.contacts li { display: flex; align-items: center; gap: 5px; margin: 0; }
.contacts svg { width: 10px; height: 10px; flex: none; stroke: var(--accent); fill: none;
  stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }

h2 { display: flex; align-items: center; gap: 8px; margin: 11px 0 6px;
  font: 600 9pt/1 var(--display); letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--ink); break-after: avoid; }
h2::before { content: ""; width: 6px; height: 6px; border-radius: 1.5px; background: var(--accent); }
h2::after { content: ""; flex: 1; height: 1px; background: var(--line); }
.summary p { max-width: 172mm; }

.role { display: grid; grid-template-columns: 82px 1fr; column-gap: 14px; }
.when { padding-top: 1px; text-align: right; font: 7.6pt/1.45 var(--mono); color: var(--muted); }
.when b { display: block; font-weight: 500; color: var(--ink-2); }
/* No positioning here: positioned boxes paint (and extract) after the rail, breaking text order. */
.what { padding: 0 0 9px 14px; border-left: 1px solid var(--line); }
.what h3::before { content: ""; display: inline-block; width: 8px; height: 8px; margin: 0 10.5px 0 -18.5px;
  vertical-align: 1px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 0 2.5px #fff; }
.role:last-child .what { padding-bottom: 2px; }
h3 { margin: 0; font: 600 10.2pt/1.3 var(--display); color: var(--ink); break-after: avoid; }
h3 .at { color: var(--accent); }
.sub { margin: 1px 0 2px; font-style: italic; color: var(--muted); }

.chips { display: flex; flex-wrap: wrap; gap: 3px; margin-top: 3px; }
.chip { padding: 0.5px 5px; border-radius: 3px; background: var(--chip);
  font: 6.9pt/1.5 var(--mono); color: var(--ink-2); white-space: nowrap; }

.projects { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.card { display: flex; flex-direction: column; padding: 6px 9px 7px; border: 1px solid var(--line);
  border-radius: 6px; break-inside: avoid; }
.card h3 { font-size: 9.4pt; display: flex; justify-content: space-between; align-items: baseline; gap: 6px; }
.card .url { font: 6.9pt var(--mono); color: var(--accent); white-space: nowrap; }
.card p { flex: 1; margin: 2px 0 0; font-size: 8.3pt; line-height: 1.4; }

.skills { display: grid; grid-template-columns: max-content 1fr; gap: 2px 14px; font-size: 8.4pt; }
.skills dt { font: 600 7.2pt/1.75 var(--display); letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
.skills dd { margin: 0; color: var(--ink-2); }

.footer { display: grid; grid-template-columns: 0.95fr 1.7fr 0.6fr; gap: 0 18px; break-inside: avoid; }
.footer h2 { margin-top: 12px; }
.footer .item { margin-bottom: 4px; font-size: 8.4pt; line-height: 1.4; }
.footer .item b { display: block; font: 600 8.8pt/1.35 var(--display); color: var(--ink); }
.footer .meta { font: 7.2pt/1.5 var(--mono); color: var(--muted); }
.certs { margin: 0; padding: 0; list-style: none; font-size: 8.4pt; }
.certs .meta { white-space: nowrap; }
.certs li { display: flex; justify-content: space-between; gap: 8px; margin-bottom: 2px; }
"""


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fmt_date(value: str) -> str:
    if "-" not in value:
        return escape(value)
    year, month = value.split("-")[:2]
    return f"{MONTHS[int(month) - 1]} {year}"


def link(url: str, text: str | None = None) -> str:
    return f'<a href="{escape(url)}">{escape(text or url.split("://", 1)[-1].rstrip("/"))}</a>'


def tech_list(items: list[str]) -> list[str]:
    # experience.json prefixes group starts like "Languages: Python"; drop the label.
    return [i.split(": ", 1)[-1] for i in items]


def chips(items: list[str]) -> str:
    return (
        '<div class="chips">'
        + "".join(f'<span class="chip">{escape(i)}</span>' for i in items)
        + "</div>"
    )


def icon(name: str) -> str:
    return f'<svg viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>'


def render() -> str:
    r = load(ROOT / "resume" / "resume.json")
    contact = load(PROFILE / "contact.json")
    experience = list(reversed(load(PROFILE / "experience.json")))
    education = load(PROFILE / "education.json")
    skills = load(PROFILE / "skills.json")
    courses = [
        c for c in load(PROFILE / "courses.json") if c["issuer"] in r["courseIssuers"]
    ]

    contacts = [
        ("mail", link(f"mailto:{contact['email']}", contact["email"])),
        ("phone", escape(contact["phone"])),
        ("map-pin", escape(contact["location"])),
        ("globe", link("https://vachagan.dev")),
        *(
            (s["icon"], link(s["url"]))
            for s in contact["socials"]
            if s["icon"] in ICONS
        ),
    ]
    # Highlight the first part of the headline ("Senior Python Developer").
    first, _, rest = r["headline"].partition(" · ")
    headline = f"<b>{escape(first)}</b>" + (f" · {escape(rest)}" if rest else "")

    roles = []
    for n, e in enumerate(experience):
        limit = BULLETS[n] if n < len(BULLETS) else BULLETS[-1]
        sub = f'<p class="sub">{escape(e["summary"])}</p>' if n < DETAILED_ROLES else ""
        bullets = "".join(f"<li>{escape(h)}</li>" for h in e["highlights"][:limit])
        roles.append(
            f'<article class="role"><div class="when"><b>{fmt_date(e["startDate"])} –<br>'
            f'{fmt_date(e["endDate"])}</b>{escape(e["location"])}</div><div class="what">'
            f'<h3>{escape(e["role"])} <span class="at">· {escape(e["company"])}</span></h3>'
            f"{sub}<ul>{bullets}</ul>{chips(tech_list(e['techStack'])[: MAX_TECH[n > 0]])}</div></article>"
        )

    projects = "".join(
        f'<div class="card"><h3>{link(p["url"], p["title"]) if p.get("url") else escape(p["title"])}'
        f"{'<span class=url>' + link(p['url']) + '</span>' if p.get('url') else ''}</h3>"
        f"<p>{escape(p['text'])}</p>{chips(p.get('tags', []))}</div>"
        for p in r["projects"]
    )
    skill_rows = "".join(
        f"<dt>{escape(s['category'])}</dt><dd>{' · '.join(map(escape, s['items']))}</dd>"
        for s in skills
    )
    edu = "".join(
        f'<div class="item"><b>{escape(e["degree"])}, {escape(e["field"])}</b>'
        f'{escape(e["institution"])}<div class="meta">{fmt_date(e["startDate"])} – '
        f"{fmt_date(e['endDate'])}</div></div>"
        for e in education
    )
    certs = "".join(
        f"<li><span>{link(c['credentialUrl'], c['title']) if c.get('credentialUrl') else escape(c['title'])}</span>"
        f'<span class="meta">{"Cisco" if c["issuer"].startswith("Cisco") else escape(c["issuer"])}'
        f"{' · ' + fmt_date(c['date']) if c.get('date') else ''}</span></li>"
        for c in courses
    )
    languages = "".join(
        f'<div class="item"><b>{escape(lang)}</b><span class="meta">{escape(level)}</span></div>'
        for lang, _, level in (entry.partition(": ") for entry in r["languages"])
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{escape(r["name"])} — Resume</title>
<link rel="stylesheet" href="{FONTS}"><style>{CSS}</style></head><body>
<header>
  <h1>{escape(r["name"])}</h1>
  <div class="headline">{headline}</div>
  <ul class="contacts">{"".join(f"<li>{icon(i)}{c}</li>" for i, c in contacts)}</ul>
</header>
<h2>Summary</h2><section class="summary">{"".join(f"<p>{escape(p)}</p>" for p in r["summary"])}</section>
<h2>Experience</h2>{"".join(roles)}
<h2>Selected Projects</h2><section class="projects">{projects}</section>
<h2>Skills</h2><dl class="skills">{skill_rows}</dl>
<section class="footer">
  <div><h2>Education</h2>{edu}</div>
  <div><h2>Certifications</h2><ul class="certs">{certs}</ul></div>
  <div><h2>Languages</h2>{languages}</div>
</section>
</body></html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build profile/resume.pdf.")
    parser.add_argument("--html", type=Path, help="also save the rendered HTML here")
    args = parser.parse_args()

    # A throwaway profile keeps headless runs independent of an open browser window.
    with tempfile.TemporaryDirectory() as profile_dir:
        html = Path(profile_dir) / "resume.html"
        html.write_text(render(), encoding="utf-8")
        subprocess.run(
            [
                BROWSER,
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                "--virtual-time-budget=10000",  # let web fonts load before printing
                f"--user-data-dir={profile_dir}",
                f"--print-to-pdf={PDF_OUT}",
                html.as_uri(),
            ],
            check=True,
            capture_output=True,
        )
        if args.html:
            shutil.copyfile(html, args.html)
    print(f"Wrote {PDF_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
