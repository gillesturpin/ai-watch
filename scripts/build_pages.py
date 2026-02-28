#!/usr/bin/env python3
"""Build static site from briefings/ markdown files."""

import re
from datetime import datetime
from pathlib import Path

import markdown

BRIEFINGS_DIR = Path("briefings")
OUTPUT_DIR = Path("_site")

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

STYLE = """
:root { --bg: #0d1117; --surface: #161b22; --border: #30363d; --text: #e6edf3;
        --muted: #8b949e; --accent: #58a6ff; --green: #3fb950; }
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica,
       Arial, sans-serif; background: var(--bg); color: var(--text);
       line-height: 1.6; }
.container { max-width: 720px; margin: 0 auto; padding: 2rem 1.5rem; }
header { border-bottom: 1px solid var(--border); padding-bottom: 1.5rem;
         margin-bottom: 2rem; }
header h1 { font-size: 1.5rem; font-weight: 600; }
header h1 span { color: var(--accent); }
header p { color: var(--muted); font-size: 0.875rem; margin-top: 0.25rem; }
.status { display: inline-flex; align-items: center; gap: 0.4rem;
          font-size: 0.8rem; color: var(--green); margin-top: 0.5rem; }
.status::before { content: ""; width: 8px; height: 8px; border-radius: 50%;
                  background: var(--green); display: inline-block; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* Index page */
.briefing-list { list-style: none; }
.briefing-list li { border: 1px solid var(--border); border-radius: 6px;
                    margin-bottom: 0.75rem; }
.briefing-list a { display: block; padding: 1rem 1.25rem; color: var(--text);
                   transition: background 0.15s; }
.briefing-list a:hover { background: var(--surface); text-decoration: none; }
.briefing-date { font-weight: 600; }
.briefing-sub { color: var(--muted); font-size: 0.85rem; margin-top: 0.2rem; }

/* Briefing page */
article h2 { font-size: 1.25rem; margin-top: 2rem; margin-bottom: 0.75rem;
             padding-bottom: 0.4rem; border-bottom: 1px solid var(--border); }
article h3 { font-size: 1.05rem; margin-top: 1.25rem; margin-bottom: 0.5rem;
             color: var(--accent); }
article p { margin-bottom: 0.75rem; }
article hr { border: none; border-top: 1px solid var(--border);
             margin: 1.5rem 0; }
article strong { color: #f0f6fc; }
article a { color: var(--accent); }
.back { display: inline-block; margin-bottom: 1.5rem; color: var(--muted);
        font-size: 0.875rem; }
.back:hover { color: var(--accent); }
"""


def html_page(title: str, body: str, back: bool = False) -> str:
    back_link = '<a class="back" href="./">&larr; All briefings</a>' if back else ""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{STYLE}</style>
</head>
<body>
<div class="container">
{back_link}
{body}
</div>
</body>
</html>"""


def extract_first_heading(md_text: str) -> str:
    """Pull the date or title from the first # heading."""
    match = re.search(r"^#\s+(.+)", md_text, re.MULTILINE)
    return match.group(1) if match else ""


def parse_date_from_filename(name: str) -> datetime | None:
    match = re.search(r"(\d{4}-\d{2}-\d{2})", name)
    if match:
        return datetime.strptime(match.group(1), "%Y-%m-%d")
    return None


def format_date_fr(dt: datetime) -> str:
    days = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    months = ["", "janvier", "février", "mars", "avril", "mai", "juin",
              "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    return f"{days[dt.weekday()]} {dt.day} {months[dt.month]} {dt.year}"


def count_items(md_text: str) -> int:
    return len(re.findall(r"^###\s+", md_text, re.MULTILINE))


def build():
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Collect briefings (exclude target/draft files)
    briefings = []
    for f in sorted(BRIEFINGS_DIR.glob("briefing-*.md"), reverse=True):
        if "target" in f.name:
            continue
        dt = parse_date_from_filename(f.name)
        if dt is None:
            continue
        text = f.read_text()
        briefings.append({"file": f, "date": dt, "text": text})

    if not briefings:
        print("No briefings found.")
        return

    # Build individual pages
    md = markdown.Markdown(extensions=["fenced_code", "tables"])
    for b in briefings:
        slug = b["date"].strftime("%Y-%m-%d")
        html_content = md.convert(b["text"])
        md.reset()

        page = html_page(
            title=f"AI Watch — {slug}",
            body=f"<article>{html_content}</article>",
            back=True,
        )
        (OUTPUT_DIR / f"{slug}.html").write_text(page)

    # Build index
    latest = briefings[0]["date"].strftime("%Y-%m-%d")
    items_html = ""
    for b in briefings:
        slug = b["date"].strftime("%Y-%m-%d")
        nice_date = format_date_fr(b["date"])
        n_items = count_items(b["text"])
        items_html += f"""<li><a href="{slug}.html">
            <div class="briefing-date">{nice_date}</div>
            <div class="briefing-sub">{n_items} items couverts</div>
        </a></li>\n"""

    body = f"""<header>
    <h1><span>AI Watch</span></h1>
    <p>Veille IA quotidienne automatisée — HuggingFace Papers, GitHub Trending, Simon Willison</p>
    <div class="status">Dernier briefing : {latest}</div>
</header>
<ul class="briefing-list">
{items_html}
</ul>"""

    index = html_page(title="AI Watch — Veille IA quotidienne", body=body)
    (OUTPUT_DIR / "index.html").write_text(index)

    print(f"Built {len(briefings)} briefing(s) → _site/")


if __name__ == "__main__":
    build()
