#!/usr/bin/env python3
"""Put an edition on the league website (GitHub Pages, served from docs/).

Usage: python3 publish_site.py N

- docs/index.html   = week N edition (the permanent link always shows the newest paper)
- docs/weekN.html   = permanent copy of week N
- docs/archive.html = list of every edition in docs/
- docs/.nojekyll    = serve the files as-is

The edition HTML is copied byte for byte; the design is never touched here.
"""
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent
DOCS = ROOT / "docs"

ARCHIVE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Daily Fantasizer — Archive</title>
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
</style></head>
<body><main>
<h1>The Daily Fantasizer</h1>
<p class="sub">Men Fantasizing · every edition</p>
<ul>
{items}
</ul>
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

    weeks = sorted(
        int(m.group(1))
        for p in DOCS.glob("week*.html")
        if (m := re.fullmatch(r"week(\d+)\.html", p.name))
    )
    latest = max(weeks)
    # The homepage always shows the newest edition, even when an older week is re-published.
    shutil.copyfile(DOCS / f"week{latest}.html", DOCS / "index.html")

    items = "\n".join(
        f'<li><a href="week{w}.html">Week {w}'
        + ('<span class="tag">latest</span>' if w == latest else "")
        + "</a></li>"
        for w in sorted(weeks, reverse=True)
    )
    (DOCS / "archive.html").write_text(ARCHIVE.format(items=items), encoding="utf-8")
    print(f"site: index = week {latest}; archive = {weeks}")


if __name__ == "__main__":
    main()
