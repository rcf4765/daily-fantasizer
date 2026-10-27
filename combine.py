"""The Daily Fantasizer: League & Teams in fewer, tabbed sections (user, 2026-10-26: "combine as many sections as you
can while keeping it visually pleasing").

combine(html) takes a rendered page and regroups the League & Teams sections into switchable panels. Every original
section keeps its id (so links still land), its charts and its caption; only its big title moves into the switch.

  Standings       Power Rankings · Playoff Odds · Full table (the Pecking Order; desktop only, as before)
  Season Scoring  Heat Map · Floor & Ceiling · Good or Lucky?
  Managers        Report Card · Bench Hall of Shame · One-Man Show
  Roster Radar    (unchanged)
  Moves           Waiver Wire MVP · Trade Desk (when there is a completed trade) · On the Block · Matchmaker

Idempotent: a page that already has <!--cmb--> is returned unchanged. A section missing that week just has no button;
a group with no sections is left out.
`python3 combine.py FILE...` regroups already-built pages.
"""
import re
import sys

GROUPS = [
    ("lg-standings", "Standings", "Who's really good, and who's getting in", [
        ("power", "Power Rankings"), ("playoff-odds", "Playoff Odds"), ("pecking-order", "Full Table")]),
    ("lg-scoring", "Season Scoring", "Every team's weeks, range and luck", [
        ("heat", "Heat Map"), ("floor-ceiling", "Floor & Ceiling"), ("luck", "Good or Lucky?")]),
    ("lg-managers", "Managers", "Grades, bench blunders and one-man teams", [
        ("report-card", "Report Card"), ("bench-shame", "Bench Shame"), ("one-man-show", "One-Man Show")]),
    ("lg-moves", "Moves", "Pickups, trades and trade ideas", [
        ("waiver-mvp", "Waivers"), ("trades", "Trade Desk"), ("trading-block", "On the Block"), ("matchmaker", "Matchmaker")]),
]
ANCHOR_BEFORE = "roster-radar"  # Standings, Scoring and Managers go before Roster Radar; Moves after it

CSS = """<style>
/* League & Teams combined sections (combine.py) */
.cmb-sw{display:flex;flex-wrap:wrap;gap:4px;border-bottom:2px solid var(--rule);padding-bottom:10px;margin-bottom:6px}
.cmb-sw button{appearance:none;font-family:var(--mono);font-size:.74rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;padding:7px 14px;border:2px solid var(--rule);background:var(--sheet);color:var(--ink);cursor:pointer}
.cmb-sw button[aria-selected="true"]{background:var(--honolulu);border-color:var(--honolulu);color:#fff}
.cmb-sw button:focus-visible{outline:3px solid var(--hi);outline-offset:1px}
.cmb-p{display:grid;gap:12px;min-width:0}
.cmb-p[hidden]{display:none!important}
.cmb-p>.sec-head{display:none}
.cmb-cap{font-family:var(--mono);font-size:.68rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
@media (max-width:760px),(pointer:coarse) and (max-width:1100px){
  .cmb-sw{display:grid;grid-template-columns:repeat(auto-fit,minmax(96px,1fr))}
  .cmb-sw button{padding:8px 4px;font-size:.62rem;letter-spacing:.03em}
  .cmb-sw button[data-k="pecking-order"]{display:none}
}
</style>"""

JS = """<script>
(function(){
  document.querySelectorAll('.cmb').forEach(function(g){
    var bs=g.querySelectorAll('.cmb-sw button'),ps=g.querySelectorAll('.cmb-p');
    function open(k){bs.forEach(function(b){b.setAttribute('aria-selected',b.dataset.k===k?'true':'false')});
      ps.forEach(function(p){p.hidden=p.id!==k});window.dispatchEvent(new Event('resize'))}
    bs.forEach(function(b){b.addEventListener('click',function(){open(b.dataset.k)})});
    g._open=open;
  });
  function hash(){var id=location.hash.slice(1),el=id&&document.getElementById(id);
    if(el&&el.classList.contains('cmb-p')){var g=el.closest('.cmb');if(g&&g._open)g._open(id)}}
  addEventListener('hashchange',hash);hash();
})();
</script>"""


def _span(html, i):
    """(start, end) of the element whose start tag begins at i, matching nested tags of the same name."""
    tag = re.match(r"<(\w+)", html[i:]).group(1)
    d = 0
    for m in re.finditer(rf"<{tag}\b|</{tag}>", html[i:]):
        d += 1 if m.group().startswith("<" + tag) else -1
        if d == 0:
            return i, i + m.end()
    raise ValueError("unbalanced " + tag)


def _find(html, id_):
    m = re.search(rf'<(section|div)\b[^>]*\bid="{re.escape(id_)}"', html)
    return _span(html, m.start()) if m else None


def _panel(el, id_, first):
    """Original section -> panel: same id and content, title hidden, its caption shown as a small line."""
    inner_start = el.index(">") + 1
    tag = re.match(r"<(\w+)", el).group(1)
    inner = el[inner_start:len(el) - len(f"</{tag}>")]
    cls = re.search(r'class="([^"]*)"', el[:inner_start])
    extra = " ".join(c for c in (cls.group(1).split() if cls else []) if c not in ("sec",))
    attrs = "".join(f' {a}' for a in re.findall(r'\b(data-[\w-]+="[^"]*")', el[:inner_start]))
    cap = re.search(r'<span class="kicker">(.*?)</span>', inner)
    caph = f'<div class="cmb-cap">{cap.group(1)}</div>' if cap else ""
    return f'<div class="cmb-p {extra}" id="{id_}" role="tabpanel"{attrs}{"" if first else " hidden"}>{caph}{inner}</div>'


def combine(html):
    if "<!--cmb-->" in html or 'id="league"' not in html:
        return html
    built = {}
    for gid, title, kick, items in GROUPS:
        panels, buttons = [], []
        for id_, label in items:
            sp = _find(html, id_)
            if not sp:
                continue
            el = html[sp[0]:sp[1]]
            html = html[:sp[0]] + html[sp[1]:]
            panels.append(_panel(el, id_, not panels))
            buttons.append(f'<button type="button" role="tab" data-k="{id_}" aria-selected="{"true" if len(buttons) == 0 else "false"}">{label}</button>')
        if panels:
            built[gid] = (f'<section class="sec cmb" id="{gid}"><div class="sec-head"><h2>{title}</h2><span class="kicker">{kick}</span></div>'
                          f'<div class="cmb-sw" role="tablist" aria-label="{title}">{"".join(buttons)}</div>{"".join(panels)}</section>')
    # drop the two-column wrappers the moved sections leave empty
    html = re.sub(r'<section class="twocol">\s*</section>', "", html)
    before = "".join(built.get(g, "") for g in ("lg-standings", "lg-scoring", "lg-managers"))
    after = built.get("lg-moves", "")
    sp = _find(html, ANCHOR_BEFORE)
    if sp:
        html = html[:sp[0]] + before + html[sp[0]:sp[1]] + after + html[sp[1]:]
    else:  # no radar that week: put everything after the League & Teams hero
        h = html.index('<section class="lg-hero"')
        _, e = _span(html, h)
        html = html[:e] + before + after + html[e:]
    i = html.rfind("</body>")
    i = i if i >= 0 else len(html)
    return html[:i] + "<!--cmb-->" + CSS + JS + html[i:]


if __name__ == "__main__":
    for f in sys.argv[1:]:
        s = open(f, encoding="utf-8").read()
        open(f, "w", encoding="utf-8").write(combine(s))
        print("combined", f)
