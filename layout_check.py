#!/usr/bin/env python3
"""Layout check: does a new edition have exactly the same tabs, sections and
section order as the current published paper?

    python3 layout_check.py daily-fantasizer-weekN.html [reference.html]

The reference defaults to docs/index.html, which (before publish_site.py runs)
is the previous edition, i.e. the design the user approved last. Run it after
render.py and before publishing. It compares the skeleton only (tab panes,
section ids, the paper's fixed blocks, the tab groups' buttons), never words or
numbers. Sections that legitimately come and go week to week are ignored:
announcements, the Trade Desk, the hero score box (left out when its game is
in the biggest news), and the forecast / Matchup of the Week (no next week).

Exit 0 = same layout. Exit 1 = something was added, dropped or moved: fix the
pipeline (or, if the user asked for the change, say so in the report and
update RUNBOOK.md, the fantasizer-edition skill and the scheduled task).
"""
import re
import sys

OPTIONAL = {"announcements", "trades", "  trades", "forecast", "matchup", "block:hero"}
PANES = ["paper", "league", "player-stats", "proposals"]
# fixed blocks of the paper that have no id, found by class
BLOCKS = [("hero", r'class="hero[" ]'), ("lead", r'class="lead[" ]'),
          ("side", r'class="side[" ]'), ("honor", r'class="honor[" ]')]


def skeleton(path):
    h = open(path, encoding="utf-8").read()
    starts = []
    for p in PANES:
        m = re.search(r'id="%s"' % re.escape(p), h)
        starts.append((m.start() if m else -1, p))
    missing_panes = [p for s, p in starts if s < 0]
    found = sorted((s, p) for s, p in starts if s >= 0)
    out = {}
    for i, (s, p) in enumerate(found):
        e = found[i + 1][0] if i + 1 < len(found) else len(h)
        body = h[s:e]
        items = []
        # sections, plus the panels inside the tabbed groups (combine.py)
        for m in re.finditer(r'<section\b[^>]*\bid="([^"]+)"|<div class="cmb-p[^"]*" id="([^"]+)"', body):
            items.append((m.start(), m.group(1) or "  " + m.group(2)))
        if p == "paper":
            for name, rx in BLOCKS:
                m = re.search(rx, body)
                if m:
                    items.append((m.start(), "block:" + name))
        out[p] = [x for _, x in sorted(items)]
    return out, missing_panes


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    new, ref = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "docs/index.html")
    a, miss_a = skeleton(ref)
    b, miss_b = skeleton(new)
    bad = []
    if miss_b:
        bad.append("missing tabs in the new edition: " + ", ".join(miss_b))
    for p in PANES:
        ra = [x for x in a.get(p, []) if x not in OPTIONAL]
        rb = [x for x in b.get(p, []) if x not in OPTIONAL]
        dropped = [x for x in ra if x not in rb]
        added = [x for x in rb if x not in ra]
        if dropped:
            bad.append(f"[{p}] dropped: {', '.join(dropped)}")
        if added:
            bad.append(f"[{p}] added: {', '.join(added)}")
        common_a = [x for x in ra if x in rb]
        common_b = [x for x in rb if x in ra]
        if common_a != common_b:
            bad.append(f"[{p}] order changed:\n   was {common_a}\n   now {common_b}")
    for p in PANES:
        opt = sorted(set(b.get(p, [])) & OPTIONAL)
        if opt:
            print(f"[{p}] optional sections this week: {', '.join(opt)}")
    if bad:
        print("LAYOUT DIFFERS from " + ref + ":")
        print("\n".join(" - " + x for x in bad))
        sys.exit(1)
    print(f"Layout matches {ref}: " + ", ".join(f"{p} {len(b.get(p, []))}" for p in PANES))


if __name__ == "__main__":
    main()
