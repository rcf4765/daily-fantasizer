#!/usr/bin/env python3
"""Put an edition on the league website (GitHub Pages, served from docs/).

Usage: python3 publish_site.py N

- docs/index.html   = week N edition (the permanent link always shows the newest paper)
- docs/weekN.html   = permanent copy of week N
- docs/archive.html = list of every edition in docs/
- docs/.nojekyll    = serve the files as-is

The edition HTML is copied byte for byte; the design is never touched here. The only
addition is the home-screen app tags (icon, manifest, offline worker) placed right after
the <title> of the copies in docs/, between <!--app--> and <!--/app-->. The install page
(docs/install.html), manifest, sw.js and icons/ are static files that live in docs/.
"""
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent
DOCS = ROOT / "docs"

# Home-screen app tags, added to every page in docs/ (see docs/install.html).
APP_TAGS = """<!--app-->
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icons/favicon-32.png">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<meta name="theme-color" content="#0b1433">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Fantasizer">
<script>if('serviceWorker'in navigator)navigator.serviceWorker.register('sw.js').catch(function(){})</script>
<!--/app-->"""


def add_app_tags(path):
    """Put APP_TAGS right after the first </title> (replacing an older copy). Idempotent."""
    html = path.read_text(encoding="utf-8")
    html = re.sub(r"\n?<!--app-->.*?<!--/app-->", "", html, count=1, flags=re.S)
    i = html.find("</title>")
    if i < 0:
        sys.exit(f"{path.name} has no <title>; can't add the app tags")
    i += len("</title>")
    path.write_text(html[:i] + "\n" + APP_TAGS + html[i:], encoding="utf-8")


ARCHIVE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Daily Fantasizer — Archive</title>
{app}
<style>
:root{{--paper:#e3e6de;--sheet:#f4f5f0;--ink:#151a24;--muted:#59606c;--line:#c9cdc3;--blue:#1c3fae;--honolulu:#0076b6;--silver:#b0b7bc}}
@media (prefers-color-scheme:dark){{:root{{--paper:#0e1117;--sheet:#171b24;--ink:#e8eae3;--muted:#a2a9b5;--line:#333a47;--blue:#7d97ea;--honolulu:#2a95d4;--silver:#8c949b;color-scheme:dark}}}}
body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:640px;margin:0 auto;padding:32px 16px 48px;background:var(--sheet);min-height:100vh;box-sizing:border-box;border-top:6px solid var(--honolulu)}}
h1{{font:900 2.2rem/1 Georgia,serif;margin:0 0 4px;letter-spacing:-.5px}}
p.sub{{color:var(--muted);margin:0 0 24px}}
ul{{list-style:none;padding:0;margin:0;border-top:2px solid var(--ink)}}
li{{border-bottom:1px solid var(--line)}}
a{{display:flex;justify-content:space-between;padding:14px 4px;color:var(--ink);text-decoration:none;font-weight:600}}
a:hover{{color:var(--blue)}}
span.tag{{font-size:.8rem;color:var(--muted);font-weight:500}}
p.app{{margin:28px 0 0;text-align:center}}
p.app a{{display:inline-block;padding:10px 18px;border:2px solid var(--line);border-radius:10px}}
</style></head>
<body><main>
<h1>The Daily Fantasizer</h1>
<p class="sub">Men Fantasizing · every edition</p>
<ul>
{items}
</ul>
<p class="app"><a href="install.html">Put the paper on your home screen</a></p>
</main></body></html>
"""


def main():
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        sys.exit("usage: python3 publish_site.py N")
    n = int(sys.argv[1])
    src = ROOT / f"daily-fantasizer-week{n}.html"
    if not src.exists():
        sys.exit(f"missing {src.name}; run render.py {n} first")

    DOCS.mkdir(exist_ok=True)
    (DOCS / ".nojekyll").touch()
    shutil.copyfile(src, DOCS / f"week{n}.html")
    add_app_tags(DOCS / f"week{n}.html")

    weeks = sorted(
        int(m.group(1))
        for p in DOCS.glob("week*.html")
        if (m := re.fullmatch(r"week(\d+)\.html", p.name))
    )
    latest = max(weeks)
    for w in weeks:  # older copies get the app tags too (no-op when already there)
        add_app_tags(DOCS / f"week{w}.html")
    # The homepage always shows the newest edition, even when an older week is re-published.
    shutil.copyfile(DOCS / f"week{latest}.html", DOCS / "index.html")

    items = "\n".join(
        f'<li><a href="week{w}.html">Week {w}'
        + ('<span class="tag">latest</span>' if w == latest else "")
        + "</a></li>"
        for w in sorted(weeks, reverse=True)
    )
    (DOCS / "archive.html").write_text(ARCHIVE.format(items=items, app=APP_TAGS), encoding="utf-8")
    print(f"site: index = week {latest}; archive = {weeks}")


if __name__ == "__main__":
    main()
