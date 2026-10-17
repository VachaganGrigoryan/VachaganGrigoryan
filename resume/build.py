"""Build profile/resume.pdf from profile/*.json and resume/resume.json.

Usage: python3 resume/build.py
Renders the resume as HTML, then prints it to PDF with headless Chromium
(Microsoft Edge by default; override with RESUME_BROWSER=/path/to/chrome).
"""

import json
import os
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
BULLETS = (5, 5, 2, 2, 2, 2)
DETAILED_ROLES = 2  # roles that also show their summary line
MAX_TECH = 16

CSS = """
@page { size: A4; margin: 13mm 14mm; }
* { box-sizing: border-box; }
body { margin: 0; font: 9.4pt/1.38 "Helvetica Neue", Helvetica, Arial, sans-serif; color: #1f2937; }
a { color: inherit; text-decoration: none; }
h1 { margin: 0; font-size: 22pt; letter-spacing: -0.3px; color: #0f172a; }
.headline { margin: 2px 0 6px; font-size: 10.5pt; color: #0f766e; font-weight: 600; }
.contacts { display: flex; flex-wrap: wrap; gap: 2px 14px; font-size: 8.8pt; color: #475569; }
h2 { margin: 11px 0 5px; padding-bottom: 3px; font-size: 9.5pt; letter-spacing: 1.4px;
     text-transform: uppercase; color: #0f766e; border-bottom: 1.2px solid #99f6e4; }
p { margin: 0 0 5px; }
.role { margin-bottom: 8px; }
.role .row, li { break-inside: avoid; break-after: avoid-page; }
.row { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.title { font-weight: 700; color: #0f172a; font-size: 10.2pt; }
.client, .meta { color: #64748b; font-weight: 400; }
.meta { font-size: 8.8pt; white-space: nowrap; }
.sub { font-style: italic; color: #334155; margin-bottom: 2px; }
ul { margin: 2px 0 3px; padding-left: 15px; }
li { margin-bottom: 1px; }
.tech { font-size: 8.6pt; color: #475569; }
.tech b, .label { color: #334155; }
.project { margin-bottom: 4px; break-inside: avoid; }
.grid { display: grid; grid-template-columns: max-content 1fr; gap: 1px 12px; font-size: 8.8pt; }
.label { white-space: nowrap; }
.courses { font-size: 8.8pt; }
.cols { display: grid; grid-template-columns: 0.85fr 1.15fr; gap: 0 22px; }
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


def tech_list(items: list[str]) -> str:
    # experience.json prefixes group starts like "Languages: Python"; drop the label.
    return ", ".join(escape(i.split(": ", 1)[-1]) for i in items)


def render() -> str:
    r = load(ROOT / "resume" / "resume.json")
    contact = load(PROFILE / "contact.json")
    experience = list(reversed(load(PROFILE / "experience.json")))
    education = load(PROFILE / "education.json")
    skills = load(PROFILE / "skills.json")
    courses = [
        c for c in load(PROFILE / "courses.json") if c["issuer"] in r["courseIssuers"]
    ]

    socials = [link(s["url"]) for s in contact["socials"] if s["label"] != "Telegram"]
    contacts = [
        link(f"mailto:{contact['email']}", contact["email"]),
        escape(contact["phone"]),
        escape(contact["location"]),
        link("https://vachagan.dev"),
        *socials,
    ]

    roles = []
    for n, e in enumerate(experience):
        limit = BULLETS[n] if n < len(BULLETS) else BULLETS[-1]
        sub_html = (
            f'<div class="sub">{escape(e["summary"])}</div>'
            if n < DETAILED_ROLES
            else ""
        )
        bullets = "".join(f"<li>{escape(h)}</li>" for h in e["highlights"][:limit])
        roles.append(
            f'<div class="role"><div class="row"><span class="title">{escape(e["role"])} — '
            f'{escape(e["company"])}</span><span class="meta">{fmt_date(e["startDate"])} – '
            f"{fmt_date(e['endDate'])} · {escape(e['location'])}</span></div>"
            f"{sub_html}<ul>{bullets}</ul>"
            f'<div class="tech"><b>Tech:</b> {tech_list(e["techStack"][:MAX_TECH])}</div></div>'
        )

    projects = "".join(
        f'<div class="project"><span class="title">'
        f"{link(p['url'], p['title']) if p.get('url') else escape(p['title'])}</span>"
        f"{' <span class=meta>' + link(p['url']) + '</span>' if p.get('url') else ''}"
        f" — {escape(p['text'])}</div>"
        for p in r["projects"]
    )
    skill_rows = "".join(
        f'<span class="label"><b>{escape(s["category"])}</b></span><span>{", ".join(map(escape, s["items"]))}</span>'
        for s in skills
    )
    edu = "".join(
        f'<div class="row"><span><b>{escape(e["degree"])}, {escape(e["field"])}</b><br>'
        f'{escape(e["institution"])}</span><span class="meta">{fmt_date(e["startDate"])} – '
        f"{fmt_date(e['endDate'])}</span></div>"
        for e in education
    )
    course_items = "".join(
        f"<li>{link(c['credentialUrl'], c['title']) if c.get('credentialUrl') else escape(c['title'])}"
        f' <span class="meta">— {escape(c["issuer"])}{" · " + fmt_date(c["date"]) if c.get("date") else ""}</span></li>'
        for c in courses
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{escape(r["name"])} — Resume</title>
<style>{CSS}</style></head><body>
<h1>{escape(r["name"])}</h1>
<div class="headline">{escape(r["headline"])}</div>
<div class="contacts">{"".join(f"<span>{c}</span>" for c in contacts)}</div>
<h2>Summary</h2>{"".join(f"<p>{escape(p)}</p>" for p in r["summary"])}
<h2>Experience</h2>{"".join(roles)}
<h2>Selected Projects</h2>{projects}
<h2>Skills</h2><div class="grid">{skill_rows}</div>
<div class="cols">
  <div><h2>Education</h2>{edu}<h2>Languages</h2><p>{" · ".join(map(escape, r["languages"]))}</p></div>
  <div><h2>Certifications &amp; Courses</h2><ul class="courses">{course_items}</ul></div>
</div>
</body></html>
"""


def main() -> None:
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
                f"--user-data-dir={profile_dir}",
                f"--print-to-pdf={PDF_OUT}",
                html.as_uri(),
            ],
            check=True,
            capture_output=True,
        )
    print(f"Wrote {PDF_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
