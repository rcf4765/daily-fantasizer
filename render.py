"""The Daily Fantasizer renderer (graphics-first design, approved 2026-10-13 with the week 5 edition).
Usage: python3 render.py 5   (reads data/week5_facts.json, data/week5_copy.json, data/week5_raw.txt,
data/trades.json if present, league.json, data/logos.txt and template.html)
Writes daily-fantasizer-week5.html. Every chart number comes from the facts/raw/trades data; words from the copy file."""
import json, re, html, math, sys

W = int(sys.argv[1])
F = json.load(open(f"data/week{W}_facts.json"))
C = json.load(open(f"data/week{W}_copy.json"))
LG = json.load(open("league.json"))
logos = {int(l.split(" ", 1)[0][1:]): l.split(" ", 1)[1].strip() for l in open("data/logos.txt") if l.strip()}
teams = {int(k): v for k, v in F["teams"].items()}
TF = {int(k): v for k, v in F["this_week"].items()}
SEA = {int(k): v for k, v in F["season"].items()}
for v in SEA.values(): v["weekly"] = {int(k): x for k, x in v["weekly"].items()}
SHORT = {int(k): v for k, v in LG["short_names"].items()}
for t in teams: SHORT.setdefault(t, teams[t]["name"])
NT = len(teams); L = F["league"]; games = F["games"]
esc = html.escape
def lg(t, size=""): return f'<i class="lg lg-{t} {size}" aria-hidden="true"></i>'
def T(t, short=False): return f'<span class="tm">{lg(t)}{esc(SHORT[t] if short else teams[t]["name"])}</span>'
def fill(s):
    s = re.sub(r"\{T(\d+)\}", lambda m: T(int(m.group(1))), s)
    return re.sub(r"\{S(\d+)\}", lambda m: T(int(m.group(1)), True), s)
def f2(x): return f"{x:.2f}"
def g(x): return f"{x:g}"
def key(a, b, d): return d.get(f"{a}-{b}") or d.get(f"{b}-{a}")
def last(n): return n.replace(" Jr.", "").replace(" Sr.", "").replace(" III", "").replace(" II", "").split(" ")[-1] if "D/ST" not in n else n.replace(" D/ST", " D")
win = {g_["winner"] for g_ in games if not g_["tie"]}

# ---------- stat tiles ----------
tp = L["top_player"]; perfect = sorted(t for t in TF if TF[t]["left_on_bench"] == 0)
tiles = [
    ("League average", f'{L["avg"]:.1f}', "points per team", ""),
    ("High score", f2(TF[L["high"]]["week_pts"]), SHORT[L["high"]], lg(L["high"])),
    ("Low score", f2(TF[L["low"]]["week_pts"]), SHORT[L["low"]], lg(L["low"])),
    ("Top player", g(tp[1]["pts"]), tp[1]["name"], lg(tp[0])),
    ("Left on benches", f2(L["total_left"]), "across all 12 teams", ""),
    ("Perfect lineups", str(len(perfect)), "only one of them won", "".join(lg(t) for t in perfect)),
]
tiles_html = "".join(f'<div class="tile"><span class="tile-k">{k}</span><b class="num">{v}</b><span class="tile-s">{c}<span>{esc(s)}</span></span></div>' for k, v, s, c in tiles)
crests = "".join(lg(t) for t in sorted(teams))

# ---------- upsets & heartbreakers (top of the paper; user, 2026-10-19) ----------
# Games come from facts.py (F["upsets"]); words from copy "upsets" keyed "winnerId-loserId" (headline, text)
# and optional "upsets_empty". Salt chips and records are automatic.
UPS = F.get("upsets", [])
CU = C.get("upsets", {})
def rec_s(r): return f'{r["w"]}–{r["l"]}' + (f'–{r["t"]}' if r.get("t") else "")
ucards = []
for u in UPS:
    w, l = u["winner"], u["loser"]
    rc = key(w, l, CU)
    if not rc:
        print(f"WARNING: no upsets copy for {w}-{l}; using an automatic headline")
        rc = {"headline": (f"No. {u['w_rank_pre']} Topples No. {u['l_rank_pre']}" if u["upset"] else f"Lost by {u['margin']:.2f}" if u["heartbreaker"] else f"Buried by {u['margin']:.0f}"), "text": ""}
    stamps = (('<span class="stamp up-st">Upset</span>' if u["upset"] else "")
              + ('<span class="stamp hb-st">Heartbreaker</span>' if u["heartbreaker"] else "")
              + ('<span class="stamp bo-st">Blowout</span>' if u.get("blowout") else ""))
    kick = (f'No. {u["w_rank_pre"]} ({rec_s(u["w_pre"])}) took down No. {u["l_rank_pre"]} ({rec_s(u["l_pre"])})' if u["upset"]
            else f'Decided by {u["margin"]:.2f} points' if u["heartbreaker"] else f'Week {W}\'s biggest beatdown')
    salt = [f'Left {u["l_left_on_bench"]:.1f} on the bench'] if u["l_left_on_bench"] > 0 else []
    if u.get("blowout") and u["l_optimal"] < u["ws"]: salt.append(f'Perfect lineup ({u["l_optimal"]:.2f}) still loses by {u["ws"] - u["l_optimal"]:.2f}')
    if u["loser_optimal_would_win"]: salt.append(f'Best lineup ({u["l_optimal"]:.2f}) would have won')
    if u["l_benched_star"] and u["l_benched_star"][2] > 0: salt.append(f'Benched {u["l_benched_star"][0]}: {g(u["l_benched_star"][2])}')
    if u["l_streak"][0] == "L" and int(u["l_streak"][1:]) >= 2: salt.append(f'{u["l_streak"][1:]} straight losses')
    lead_u = not ucards  # the first game is the page-one banner: full width, giant headline and crests
    cls = " both" if u["upset"] and u["heartbreaker"] else " hb" if u["heartbreaker"] else " bo" if u.get("blowout") and not u["upset"] else ""
    cs = "lg-xl" if lead_u else "lg-lg"
    hd = "h2" if lead_u else "h3"
    ucards.append(f'''<article class="ups-card{cls}{" lead-up" if lead_u else ""}">
<div class="ups-top"><span class="kicker">{esc(kick)}</span><span class="ups-stamps">{stamps}</span></div>
<{hd} class="ups-h">{esc(rc["headline"])}</{hd}>
<div class="ups-vs"><div class="ups-w">{lg(w, cs)}<span class="ups-n">{esc(SHORT[w])}</span><b class="num">{f2(u["ws"])}</b><small>now {esc(u["w_now"].replace("-", "–"))}</small></div>
<div class="ups-m"><b class="num">+{u["margin"]:.2f}</b><span>margin</span></div>
<div class="ups-l">{lg(l, cs)}<span class="ups-n">{esc(SHORT[l])}</span><b class="num">{f2(u["ls"])}</b><small>now {esc(u["l_now"].replace("-", "–"))}</small></div></div>
{f"<p>{fill(rc['text'])}</p>" if rc.get("text") else ""}
<div class="ups-salt">{"".join(f"<span>{esc(s)}</span>" for s in salt)}</div></article>''')
# No qualifying games -> no section at all (the paper opens with the hero as before).
upsets_html = (f'<section class="ups-news" id="upsets" aria-label="The biggest news of week {W}"><div class="ups">{"".join(ucards)}</div></section>') if ucards else ""

# ---------- hero with lineup strips ----------
h = C["hero"]; hw, hl = h["winner"], h["loser"]
hmax = max(TF[hw]["week_pts"], TF[hl]["week_pts"])
def strip(t):
    st = sorted([s for s in TF[t]["starters"] if s[3] > 0], key=lambda s: -s[3])
    segs = "".join(f'<span class="seg" style="width:{s[3]/hmax*100:.2f}%" title="{esc(s[0])} {g(s[3])}">{esc(last(s[0])) + " " + g(s[3]) if s[3]/hmax > .1 else ""}</span>' for s in st)
    return f'<div class="strip {"w" if t in win else "l"}"><span class="strip-n">{lg(t)}<b class="num">{f2(TF[t]["week_pts"])}</b></span><div class="strip-bar">{segs}</div></div>'
hero = f'''<section class="hero" aria-label="Page one result">
  <div class="hero-top">
    <div class="side">{lg(hw, "lg-xl")}<span class="score num">{f2(TF[hw]["week_pts"])}</span><span class="tname">{esc(teams[hw]["name"])}</span></div>
    <div class="mid"><b>{esc(h["big"])}</b><span>{esc(h["label"])}</span></div>
    <div class="side lose">{lg(hl, "lg-xl")}<span class="score num">{f2(TF[hl]["week_pts"])}</span><span class="tname">{esc(teams[hl]["name"])}</span></div>
  </div>
  <div class="strips"><span class="kicker">Where the points came from · each block is one starter</span>{strip(hw)}{strip(hl)}</div>
</section>'''
# No duplicates (user, 2026-10-19): when the page-one game is already in the biggest-news section
# under the stat tiles, that section is its page one, so the score box is left out.
if {hw, hl} in [{u["winner"], u["loser"]} for u in UPS]:
    print(f"NOTE: hero game {hw}-{hl} is already in the biggest-news section; hero box left out. The lead story must not repeat it.")
    hero = ""
ld = C["lead"]
lead = (f'<article class="lead"><span class="kicker">{esc(ld["kicker"])}</span><h2>{esc(ld["headline"])}</h2>'
        f'<p class="deck">{esc(ld["deck"])}</p>' + "".join(f"<p>{fill(p)}</p>" for p in ld["paragraphs"]) + "</article>")

# ---------- sidebar ----------
def viz(v):
    if not v: return ""
    if v["type"] == "wins":
        mx = max(max(SEA[t]["w"], SEA[t]["expected_wins"]) for t in v["teams"]) or 1
        rows = []
        for t in v["teams"]:
            s = SEA[t]
            rows.append(f'<div class="mb-team">{T(t, True)}</div>'
                        f'<div><span>Actual</span><i class="b" style="width:{s["w"]/mx*100:.1f}%"></i><span class="num">{s["w"]:.2f}</span></div>'
                        f'<div><span>Earned</span><i class="b alt" style="width:{s["expected_wins"]/mx*100:.1f}%"></i><span class="num">{s["expected_wins"]:.2f}</span></div>')
        return f'<div class="minibars" aria-label="Actual wins versus all-play expected wins">{"".join(rows)}</div>'
    if v["type"] == "bars":
        mx = max(r["value"] for r in v["rows"]) or 1
        return '<div class="minibars">' + "".join(
            f'<div><span>{T(r["team"], True) if "team" in r else esc(r["label"])}</span><i class="b{" alt" if r.get("alt") else ""}" style="width:{r["value"]/mx*100:.1f}%"></i><span class="num">{g(r["value"])}</span></div>'
            for r in v["rows"]) + "</div>"
    return ""
sidebar = "".join(f'<div class="box{" hi" if b.get("style") == "hi" else ""}"><span class="kicker">{esc(b["kicker"])}</span><h3>{esc(b["title"])}</h3>{viz(b.get("viz"))}<p>{fill(b["text"])}</p></div>' for b in C["sidebar"])


# ---------- scoreboard (actual + bench) ----------
MAX = math.ceil((max(TF[t]["optimal"] for t in TF) + 5) / 10) * 10
avgp = L["avg"] / MAX * 100
rows = []
for t in sorted(TF, key=lambda t: -TF[t]["week_pts"]):
    a, o = TF[t]["week_pts"], TF[t]["optimal"]
    rows.append(f'''<div class="br" title="{esc(teams[t]['name'])}: {f2(a)} scored, {f2(o)} possible">
<span class="br-name">{lg(t)}<span>{esc(SHORT[t])}</span></span>
<span class="br-track"><span class="br-bar {"w" if t in win else "l"}" style="width:{a/MAX*100:.2f}%"></span><span class="br-gap" style="left:{a/MAX*100:.2f}%;width:{(o-a)/MAX*100:.2f}%"></span><span class="avg" style="left:{avgp:.2f}%"></span></span>
<span class="br-val num">{f2(a)} <em>+{o-a:.1f}</em></span></div>''')
ticks = "".join(f'<span class="tick{" near" if 0 < abs(v/MAX*100-avgp) < 12 else ""}{" near-m" if 0 < abs(v/MAX*100-avgp) < 25 and v else ""}" style="left:{v/MAX*100:.2f}%">{v}</span>' for v in range(0, MAX + 1, 50))
scoreboard = f'''<div class="chart" role="img" aria-label="Week {W} scores by team, with points left on the bench" style="--grid:{50/MAX*100:.2f}%">
<div class="br-grid"><span></span><span class="axis">{ticks}<span class="avgline" style="left:{avgp:.2f}%"><b>avg {L["avg"]:.1f}</b></span></span><span></span></div>
{"".join(rows)}
<div class="legend"><span><i class="sw w"></i>Won</span><span><i class="sw l"></i>Lost</span><span><i class="sw gap"></i>Left on the bench</span><span><i class="sw avg"></i>League average</span></div></div>'''

# ---------- boom / bust ----------
bb = [(r[0], r[1], r[3], r[4], r[5]) for r in L["booms"][:5]] + [(r[0], r[1], r[3], r[4], r[5]) for r in L["worst_busts"][:5]]
bmx = max(abs(r[4]) for r in bb)
def bbrow(t, n, pr, act, d):
    w = abs(d) / bmx * 100
    bar = f'<span class="bb-bar {"up" if d > 0 else "dn"}" style="width:{w:.1f}%"></span>'
    return (f'<div class="bb-row" title="{esc(n)}: projected {g(pr)}, scored {g(act)}"><span class="bb-name">{lg(t)}<span>{esc(n)}</span></span>'
            f'<span class="bb-l">{bar if d < 0 else ""}</span><span class="bb-r">{bar if d > 0 else ""}</span><span class="bb-v num">{d:+.1f}<em>{g(pr)}→{g(act)}</em></span></div>')
boombust = ('<div class="bb"><div class="bb-head"><span></span><span>Busts</span><span>Booms</span><span></span></div>'
            + "".join(bbrow(*r) for r in sorted(bb, key=lambda r: -r[4])) + '</div>')

# ---------- positions ----------
POS = ["QB", "RB", "WR", "TE", "FLEX", "D/ST", "K"]
posd = {t: {p: sum(max(s[3], 0) for s in TF[t]["starters"] if s[2] == p) for p in POS} for t in TF}
pmx = max(sum(posd[t].values()) for t in TF)
prow = []
for t in sorted(TF, key=lambda t: -TF[t]["week_pts"]):
    segs = "".join(f'<span class="ps ps-{i}" style="width:{posd[t][p]/pmx*100:.2f}%" title="{p} {posd[t][p]:.1f}">{p if posd[t][p]/pmx > .07 else ""}</span>' for i, p in enumerate(POS))
    prow.append(f'<div class="pr"><span class="br-name">{lg(t)}<span>{esc(SHORT[t])}</span></span><span class="pr-bar">{segs}</span></div>')
lgpos = {p: sum(posd[t][p] for t in TF) / NT for p in POS}
best_pos = {p: max(TF, key=lambda t: posd[t][p]) for p in POS}
poslegend = "".join(f'<span><i class="sw ps-{i}"></i>{p} <em class="num">avg {lgpos[p]:.1f}</em></span>' for i, p in enumerate(POS))
positions = f'<div class="pos">{"".join(prow)}<div class="legend">{poslegend}</div></div>'
poskings = "".join(f'<div class="pk"><span class="pk-p">{p}</span>{lg(best_pos[p], "lg-sm")}<b class="num">{posd[best_pos[p]][p]:.1f}</b><span>{esc(SHORT[best_pos[p]])}</span></div>' for p in POS)

# ---------- games ----------
game_cards = []
for g_ in sorted(games, key=lambda g_: g_["margin"]):
    w, l = g_["winner"], g_["loser"]
    rc = key(w, l, C["recaps"]) or {"headline": "", "text": ""}
    gm = max(TF[w]["optimal"], TF[l]["optimal"], g_["ws"])
    def lane(t, s):
        o = TF[t]["optimal"]
        return (f'<div class="lane"><span class="lane-t">{lg(t)}</span><span class="lane-track"><span class="lane-bar {"w" if t == w else "l"}" style="width:{s/gm*100:.1f}%"></span>'
                f'<span class="lane-opt" style="left:{o/gm*100:.1f}%" title="Best lineup {f2(o)}"></span></span><b class="num">{f2(s)}</b></div>')
    flag = '<span class="flag">Best lineup would have won</span>' if g_["loser_optimal_would_win"] else ""
    game_cards.append(f'''<article class="game"><div class="g-head"><span class="kicker">{esc(SHORT[w])} def. {esc(SHORT[l])}</span><span class="margin num">+{g_["margin"]:.2f}</span></div>
{lane(w, g_["ws"])}{lane(l, g_["ls"])}<h3>{esc(rc["headline"])}</h3>{flag}<p>{fill(rc["text"])}</p></article>''')

# ---------- honor ----------
ho = C["honor"]
honor = (f'''<section class="honor" aria-label="{esc(ho["kicker"])}">{lg(ho["team"], "lg-lg")}
<div class="big num">{esc(ho["big"])}<small>{esc(ho["big_label"])}</small></div>
<div><span class="kicker">{esc(ho["kicker"])}</span><h3>{esc(ho["title"])}</h3><p>{fill(ho["text"])}</p></div></section>''')

# ---------- heatmap ----------
weeks = sorted({w_ for t in SEA for w_ in SEA[t]["weekly"]})
allv = [SEA[t]["weekly"][w_] for t in SEA for w_ in weeks if w_ in SEA[t]["weekly"]]
hlo, hhi = min(allv), max(allv)
hrows = []
for t in F["ranking"]:
    cells = ""
    for w_ in weeks:
        v = SEA[t]["weekly"].get(w_)
        if v is None: cells += '<span class="hc"></span>'; continue
        p = (v - hlo) / (hhi - hlo)
        mark = " hc-hi" if v == hhi else (" hc-lo" if v == hlo else "")
        cells += f'<span class="hc{mark}{" dark" if p > .55 else ""}" style="--p:{p*100:.0f}%" title="Week {w_}: {f2(v)}">{v:.0f}</span>'
    hrows.append(f'<div class="hr"><span class="br-name">{lg(t)}<span>{esc(SHORT[t])}</span></span>{cells}<span class="hc-avg num">{SEA[t]["avg"]:.1f}</span></div>')
heat = (f'<div class="heat-wrap"><div class="heat" style="--nw:{len(weeks)}"><div class="hr hh"><span></span>' + "".join(f"<span>Wk {w_}</span>" for w_ in weeks)
        + '<span>Avg</span></div>' + "".join(hrows) + f'</div><div class="heat-key"><span class="num">{hlo:.0f}</span><i></i><span class="num">{hhi:.0f}</span><span>· season low and high are outlined</span></div></div>')

# ---------- luck scatter (PF vs PA) ----------
pfs = [SEA[t]["pf"] for t in SEA]; pas = [SEA[t]["pa"] for t in SEA]
x0, x1 = min(pfs) - 35, max(pfs) + 35; y0, y1 = min(pas) - 75, max(pas) + 75
mpf, mpa = sum(pfs) / NT, sum(pas) / NT
def X(v): return (v - x0) / (x1 - x0) * 100
def Y(v): return 100 - (v - y0) / (y1 - y0) * 100
dots = "".join(f'<span class="dot" style="left:{X(SEA[t]["pf"]):.1f}%;top:{Y(SEA[t]["pa"]):.1f}%" title="{esc(teams[t]["name"])}: {f2(SEA[t]["pf"])} for, {f2(SEA[t]["pa"])} against, {SEA[t]["w"]}–{SEA[t]["l"]}">{lg(t, "lg-sm")}<em class="num">{SEA[t]["w"]}–{SEA[t]["l"]}</em></span>' for t in SEA)
scatter = f'''<div class="sc-wrap"><div class="sc" role="img" aria-label="Points for versus points against, season to date">
<span class="q q1">Good team,<br>brutal schedule</span><span class="q q2">Bad team,<br>brutal schedule</span><span class="q q3">Bad team,<br>soft schedule</span><span class="q q4">Good team,<br>soft schedule</span>
<span class="vline" style="left:{X(mpf):.1f}%"></span><span class="hline" style="top:{Y(mpa):.1f}%"></span>{dots}</div>
<div class="sc-x"><span class="num">{x0:.0f}</span><span>Points scored →</span><span class="num">{x1:.0f}</span></div>
<span class="sc-y">Points allowed →</span></div>'''

# ---------- what if: everyone starts their best possible lineup every week ----------
# Re-scores every played week from the saved data/weekK_raw.txt rosters (facts.optimal), then replays the
# schedule with both teams at their optimal score. Standings = wins, then points for (ESPN's tiebreak).
import os as _os
from facts import load as _load, optimal as _optimal
WI_WEEKS = [k for k in range(1, W + 1) if _os.path.exists(f"data/week{k}_raw.txt")]
whatif = ""
if len(WI_WEEKS) == W:
    WR = {t: dict(aw=0, al=0, at=0, ow=0, ol=0, ot=0, apf=0.0, opf=0.0, flips=[]) for t in teams}
    for k in WI_WEEKS:
        _m, _slots, _t, _sched, _ros, _tx, _lu = _load(f"data/week{k}_raw.txt")
        opt = {t: _optimal(_ros[t], _slots)[0] for t in _ros}
        for gm in _sched:
            if gm["wk"] != k or not gm["away"]: continue
            for t, u, tp, up in ((gm["home"], gm["away"], gm["hp"], gm["ap"]), (gm["away"], gm["home"], gm["ap"], gm["hp"])):
                r = WR[t]; a_res = "W" if tp > up else "L" if tp < up else "T"; o_res = "W" if opt[t] > opt[u] else "L" if opt[t] < opt[u] else "T"
                r["a" + a_res.lower()] += 1; r["o" + o_res.lower()] += 1; r["apf"] += tp; r["opf"] += opt[t]
                if a_res != o_res: r["flips"].append((k, u, a_res, o_res, opt[t], opt[u]))
    rank_a = sorted(teams, key=lambda t: (-WR[t]["aw"], -WR[t]["apf"]))
    rank_o = sorted(teams, key=lambda t: (-WR[t]["ow"], -WR[t]["opf"]))
    PO = int(F["meta"].get("playoffteams", 6)); RH = 38; H = RH * NT
    def rec(t, p): r = WR[t]; return f'{r[p+"w"]}–{r[p+"l"]}' + (f'–{r[p+"t"]}' if r[p + "t"] else "")
    def col(order, side):
        return "".join(f'<div class="sl-row {side}{" po" if i < PO else ""}"><b class="num">{i+1}</b>{lg(t)}<span>{esc(SHORT[t])}</span><em class="num">{rec(t, "a" if side == "l" else "o")}</em></div>' for i, t in enumerate(order))
    lines = []
    for t in teams:
        y1 = rank_a.index(t) * RH + RH / 2; y2 = rank_o.index(t) * RH + RH / 2
        cls = "up" if y2 < y1 else "dn" if y2 > y1 else "eq"
        lines.append(f'<line x1="0" y1="{y1:.0f}" x2="100" y2="{y2:.0f}" class="sl-{cls}"/>')
    pol = PO * RH
    slope = (f'<div class="slope" style="--rh:{RH}px" role="img" aria-label="Actual standings rank versus what-if rank">'
             f'<div class="sl-head"><span>Actual</span><span></span><span>What if</span></div>'
             f'<div class="sl-body"><div class="sl-col">{col(rank_a, "l")}</div>'
             f'<svg viewBox="0 0 100 {H}" preserveAspectRatio="none" height="{H}" aria-hidden="true">'
             f'<line x1="0" x2="100" y1="{pol}" y2="{pol}" class="sl-po"/>{"".join(sorted(lines, key=lambda s: "sl-eq" not in s))}</svg>'
             f'<div class="sl-col">{col(rank_o, "r")}</div><span class="sl-po-lab" style="top:{pol}px">Playoff line</span></div></div>')
    wrows = []
    for i, t in enumerate(rank_o, 1):
        r = WR[t]; mv = rank_a.index(t) + 1 - i
        badge = f'<span class="mv {"up" if mv > 0 else "dn" if mv < 0 else "eq"}">{"▲" + str(mv) if mv > 0 else "▼" + str(-mv) if mv < 0 else "–"}</span>'
        flips = "".join(f'<span class="flip {"w" if o == "W" else "l"}">Wk {k} vs {esc(SHORT[u])} {a}→{o}</span>' for k, u, a, o, x, y in r["flips"]) or '<span class="flip none">No change</span>'
        wrows.append(f'<tr><td class="rk">{i}</td><td><span class="po-team">{lg(t, "lg-md")}<span><b>{esc(SHORT[t])}</b><small>actual rank {rank_a.index(t)+1}</small></span></span></td>'
                     f'<td>{badge}</td><td class="n">{rec(t, "a")} <span class="arr">→</span> <b>{rec(t, "o")}</b></td>'
                     f'<td class="n">{r["apf"]:.2f} <span class="arr">→</span> <b>{r["opf"]:.2f}</b><small class="gain">+{r["opf"]-r["apf"]:.2f}</small></td><td><span class="flips">{flips}</span></td></tr>')
    nflip = sum(len(WR[t]["flips"]) for t in teams) // 2
    po_in = [t for t in rank_o[:PO] if t not in rank_a[:PO]]; po_out = [t for t in rank_a[:PO] if t not in rank_o[:PO]]
    big = max(teams, key=lambda t: rank_a.index(t) - rank_o.index(t))
    stats = (f'<div class="rum-stats"><div class="rs"><b class="num">{nflip}</b><span>Games flipped</span></div>'
             f'<div class="rs"><b class="num">{sum(WR[t]["opf"]-WR[t]["apf"] for t in teams):.1f}</b><span>Bench points, wks {WI_WEEKS[0]}–{W}</span></div>'
             f'<div class="rs">{lg(big, "lg-sm")}<span>Biggest climber</span><small>{esc(SHORT[big])}: {rank_a.index(big)+1} → {rank_o.index(big)+1}</small></div>'
             f'<div class="rs hot"><span>Playoff picture</span><small>' + (f'In: {", ".join(esc(SHORT[t]) for t in po_in)} · Out: {", ".join(esc(SHORT[t]) for t in po_out)}' if po_in else "Same six teams") + '</small></div></div>')
    whatif = (f'<section class="sec" id="what-if"><div class="sec-head"><h2>What If?</h2><span class="kicker">Standings if every team started its best possible lineup, weeks {WI_WEEKS[0]}–{W}</span></div>'
              f'{stats}<div class="wi-grid">{slope}<div class="tbl-wrap"><table class="wi"><thead><tr><th>#</th><th>Team</th><th>Move</th><th class="n">Record</th><th class="n">Points for</th><th>Games that flip</th></tr></thead>'
              f'<tbody>{"".join(wrows)}</tbody></table></div></div>'
              f'<p class="note-s">Both teams in every game get their best lineup from that week\'s roster. Ranked by wins, then points for. Top {PO} make the playoffs.</p></section>')

# ---------- season sections: power rankings over time, playoff odds, floor/ceiling, bench hall of shame, waiver MVP ----------
# All built from data/week1_raw.txt .. data/weekN_raw.txt (and data/schedule.json for playoff odds). Skipped if a week is missing.
import random as _random, statistics as _st
power_html = odds_html = rangebench_html = waiver_html = ""
if all(_os.path.exists(f"data/week{k}_raw.txt") for k in range(1, W + 1)):
    SD = {}  # week -> dict(score, opt, opp, starters, tx)
    for k in range(1, W + 1):
        _m, _slots, _t, _sched, _ros, _tx, _lu = _load(f"data/week{k}_raw.txt")
        sc, opp = {}, {}
        for gm in _sched:
            if gm["wk"] == k and gm["away"]:
                sc[gm["home"]], sc[gm["away"]] = gm["hp"], gm["ap"]; opp[gm["home"]], opp[gm["away"]] = gm["away"], gm["home"]
        SD[k] = dict(score=sc, opp=opp, opt={t: _optimal(_ros[t], _slots)[0] for t in _ros}, ros=_ros, tx=_tx)
    WEEKS = list(range(1, W + 1))

    # --- power rankings over time: cumulative all-play wins, then points for (same rule as the Pecking Order) ---
    ranks = {}
    cap, cpf = {t: 0 for t in teams}, {t: 0.0 for t in teams}
    for k in WEEKS:
        s = SD[k]["score"]
        for t in teams:
            cap[t] += sum(s[t] > s[o] for o in s if o != t); cpf[t] += s[t]
        ranks[k] = {t: i + 1 for i, t in enumerate(sorted(teams, key=lambda t: (-cap[t], -cpf[t])))}
    PR_RH = 34; PR_H = PR_RH * NT; XW = 100
    last, prev = ranks[W], ranks[W - 1] if W > 1 else ranks[W]
    def pr_y(r): return (r - 1) * PR_RH + PR_RH / 2
    plines = []
    for t in teams:
        pts = " ".join(f"{(k - 1) * XW:.0f},{pr_y(ranks[k][t]):.0f}" for k in WEEKS)
        mv = prev[t] - last[t]
        plines.append((mv != 0, f'<polyline points="{pts}" class="pw-{"up" if mv > 0 else "dn" if mv < 0 else "eq"}"><title>{esc(teams[t]["name"])}: ' + " → ".join(str(ranks[k][t]) for k in WEEKS) + '</title></polyline>'))
    pr_right = "".join(
        f'<div class="pw-row"><b class="num">{r}</b>{lg(t)}<span>{esc(SHORT[t])}</span><em class="mv {"up" if prev[t] > r else "dn" if prev[t] < r else "eq"}">'
        + ("▲" + str(prev[t] - r) if prev[t] > r else "▼" + str(r - prev[t]) if prev[t] < r else "–") + '</em></div>'
        for t, r in sorted(last.items(), key=lambda x: x[1]))
    pr_left = "".join(f'<div class="pw-row l">{lg(t)}</div>' for t, r in sorted(ranks[1].items(), key=lambda x: x[1]))
    power_html = (f'<section class="sec" id="power"><div class="sec-head"><h2>Power Rankings Over Time</h2><span class="kicker">All-play rank after every week · color = this week\'s move</span></div>'
                  f'<div class="pw"><div class="pw-wk"><span></span><span class="pw-ticks">' + "".join(f'<span>Wk {k}</span>' for k in WEEKS) + '</span><span></span></div>'
                  f'<div class="pw-body"><div class="pw-col">{pr_left}</div>'
                  f'<svg viewBox="0 0 {max((W - 1) * XW, 1)} {PR_H}" preserveAspectRatio="none" height="{PR_H}" aria-hidden="true">'
                  + "".join(f'<line x1="0" x2="{(W - 1) * XW}" y1="{i * PR_RH}" y2="{i * PR_RH}" class="pw-grid"/>' for i in range(1, NT))
                  + "".join(l for _, l in sorted(plines, key=lambda x: x[0])) + f'</svg><div class="pw-col">{pr_right}</div></div></div></section>')

    # --- playoff odds: Monte Carlo over the remaining schedule ---
    if _os.path.exists("data/schedule.json"):
        SCH = json.load(open("data/schedule.json"))
        REG, POT = SCH["regweeks"], SCH["playoff_teams"]
        left_games = [(g["wk"], g["home"], g["away"]) for g in SCH["games"] if W < g["wk"] <= REG]
        allw = [SD[k]["score"][t] for k in WEEKS for t in teams]
        lmean = _st.mean(allw)
        mu = {t: (sum(SD[k]["score"][t] for k in WEEKS) + 3 * lmean) / (W + 3) for t in teams}
        sig = _st.pstdev([SD[k]["score"][t] - _st.mean(SD[j]["score"][t] for j in WEEKS) for k in WEEKS for t in teams])
        w0 = {t: sum(SD[k]["score"][t] > SD[k]["score"][SD[k]["opp"][t]] for k in WEEKS) for t in teams}
        pf0 = {t: sum(SD[k]["score"][t] for k in WEEKS) for t in teams}
        rng = _random.Random(20260000 + W); NS = 10000
        made = {t: 0 for t in teams}; seeds = {t: [0] * NT for t in teams}; wins_tot = {t: 0 for t in teams}
        for _ in range(NS):
            wv, pv = dict(w0), dict(pf0)
            for wk, h, a in left_games:
                sh, sa = rng.gauss(mu[h], sig), rng.gauss(mu[a], sig)
                pv[h] += sh; pv[a] += sa; wv[h if sh > sa else a] += 1
            for i, t in enumerate(sorted(teams, key=lambda t: (-wv[t], -pv[t]))):
                seeds[t][i] += 1; made[t] += i < POT
            for t in teams: wins_tot[t] += wv[t]
        lw = {t: 0 for t in teams}; ll = {t: 0 for t in teams}
        for t in teams: ll[t] = W - w0[t]
        orow = []
        for t in sorted(teams, key=lambda t: (-made[t], -wins_tot[t])):
            p = made[t] / NS * 100; ew = wins_tot[t] / NS
            cells = "".join(f'<i class="sd{" po" if i < POT else ""}" style="--p:{min(100, (seeds[t][i] / NS) ** 0.5 * 160):.0f}%" title="Seed {i+1}: {seeds[t][i] / NS * 100:.1f}%"></i>' for i in range(NT))
            pl = "&gt;99%" if p > 99.4 else "&lt;1%" if p < 0.5 else f"{p:.0f}%"
            orow.append(f'<div class="od-row"><span class="br-name">{lg(t)}<span>{esc(SHORT[t])}</span></span><span class="od-rec num">{w0[t]}–{W - w0[t]}</span>'
                        f'<span class="od-track"><span class="od-bar" style="width:{p:.1f}%"></span></span><b class="od-p num">{pl}</b>'
                        f'<span class="od-proj num">{ew:.1f}–{REG - ew:.1f}</span><span class="seeds">{cells}</span></div>')
        odds_html = (f'<section class="sec" id="playoff-odds"><div class="sec-head"><h2>Playoff Odds</h2><span class="kicker">10,000 simulated seasons · top {POT} of {NT} make it</span></div>'
                     f'<div class="od"><div class="od-row od-head"><span>Team</span><span>Now</span><span>Chance to make playoffs</span><span></span><span>Proj. record</span><span class="seeds-h">Seed 1 → {NT}</span></div>{"".join(orow)}</div>'
                     f'<p class="note-s">Weeks {W + 1}–{REG} are played out 10,000 times on the real schedule. Each team scores around its season average (pulled slightly toward the league average of {lmean:.1f}) '
                     f'with the league\'s typical week-to-week swing of ±{sig:.1f}. Ties go to points for. Darker seed cells = more likely.</p></section>')

    # --- floor and ceiling ---
    fl = {t: sorted(SD[k]["score"][t] for k in WEEKS) for t in teams}
    flo, fhi = min(v[0] for v in fl.values()), max(v[-1] for v in fl.values())
    flo, fhi = math.floor((flo - 5) / 10) * 10, math.ceil((fhi + 5) / 10) * 10
    def fx(v): return (v - flo) / (fhi - flo) * 100
    frows = "".join(
        f'<div class="fc-row" title="{esc(teams[t]["name"])}: low {fl[t][0]:.2f}, median {_st.median(fl[t]):.2f}, high {fl[t][-1]:.2f}, week {W} {SD[W]["score"][t]:.2f}">'
        f'<span class="br-name">{lg(t)}<span>{esc(SHORT[t])}</span></span><span class="fc-track">'
        f'<span class="fc-range" style="left:{fx(fl[t][0]):.1f}%;width:{fx(fl[t][-1]) - fx(fl[t][0]):.1f}%"></span>'
        f'<span class="fc-med" style="left:{fx(_st.median(fl[t])):.1f}%"></span><span class="fc-now" style="left:{fx(SD[W]["score"][t]):.1f}%"></span></span>'
        f'<span class="fc-v num">{fl[t][0]:.0f}<em>–</em>{fl[t][-1]:.0f}</span></div>'
        for t in sorted(teams, key=lambda t: -_st.median(fl[t])))
    fticks = "".join(f'<span style="left:{fx(v):.1f}%">{v}</span>' for v in range(flo, fhi + 1, 20))
    floor_html = (f'<div class="sec" id="floor-ceiling"><div class="sec-head"><h2>Floor &amp; Ceiling</h2><span class="kicker">Worst to best week · sorted by median</span></div>'
                  f'<div class="fcc"><div class="fc-row fc-axis"><span></span><span class="fc-ticks">{fticks}</span><span></span></div>{frows}'
                  f'<div class="legend"><span><i class="sw fcr"></i>Season range</span><span><i class="sw fcm"></i>Median</span><span><i class="sw fcn"></i>Week {W}</span></div></div></div>')

    # --- bench hall of shame ---
    bench = {t: [round(SD[k]["opt"][t] - SD[k]["score"][t], 2) for k in WEEKS] for t in teams}
    cost = {t: sum(1 for k in WEEKS if SD[k]["score"][t] < SD[k]["score"][SD[k]["opp"][t]] < SD[k]["opt"][t]) for t in teams}
    bmx = max(sum(v) for v in bench.values()) or 1
    brows = "".join(
        f'<div class="bh-row"><span class="br-name">{lg(t)}<span>{esc(SHORT[t])}</span></span><span class="bh-bar">'
        + "".join(f'<span class="bh-seg bw{(k - 1) % 5}" style="width:{bench[t][k - 1] / bmx * 100:.2f}%" title="Week {k}: {bench[t][k - 1]:.2f}"></span>' for k in WEEKS)
        + f'</span><b class="num">{sum(bench[t]):.1f}</b><span class="bh-cost">' + ("✕" * cost[t] if cost[t] else "") + '</span></div>'
        for t in sorted(teams, key=lambda t: -sum(bench[t])))
    bench_html = (f'<div class="sec" id="bench-shame"><div class="sec-head"><h2>Bench Hall of Shame</h2><span class="kicker">Points left on the bench, weeks 1–{W}</span></div>'
                  f'<div class="bh">{brows}<div class="legend">' + "".join(f'<span><i class="sw bw{(k - 1) % 5}"></i>Wk {k}</span>' for k in WEEKS)
                  + '<span><b class="bh-x">✕</b> = a loss the best lineup would have won</span></div></div></div>')
    rangebench_html = f'<section class="twocol">{floor_html}{bench_html}</section>'

    # --- waiver wire MVP: points scored in the starting lineup by players a team picked up ---
    adds = {}  # (team, player) -> first week added
    for k in WEEKS:
        for tx in SD[k]["tx"]:
            if tx["kind"] not in ("free agent", "waiver"): continue
            for mv in tx["moves"]:
                if mv.startswith("ADD:"): adds.setdefault((tx["team"], mv[4:]), (k, tx["kind"]))
    pick = {}
    for (t, n), (k0, kind) in adds.items():
        pts, starts, pos = 0.0, 0, ""
        for k in range(k0, W + 1):
            for p in SD[k]["ros"][t]:
                if p["name"] == n:
                    pos = p["pos"]
                    if p["slot"] not in ("BE", "IR"): pts += p["pts"]; starts += 1
        pick[(t, n)] = dict(pts=round(pts, 2), starts=starts, pos=pos, wk=k0, kind=kind)
    top = sorted((x for x in pick.items() if x[1]["starts"]), key=lambda x: -x[1]["pts"])[:8]
    if top:
        wmx = top[0][1]["pts"]
        wrows = "".join(
            f'<div class="wv-row"><b class="wv-rk">{i}</b>{lg(t, "lg-sm")}<span class="wv-name"><b>{esc(n)}</b><small>{esc(v["pos"])} · {esc(SHORT[t])} · {v["kind"]} add, wk {v["wk"]}</small></span>'
            f'<span class="wv-track"><span class="wv-bar" style="width:{v["pts"] / wmx * 100:.1f}%"></span></span>'
            f'<span class="wv-v num"><b>{v["pts"]:.1f}</b><small>{v["starts"]} start{"s" if v["starts"] != 1 else ""}</small></span></div>'
            for i, ((t, n), v) in enumerate(top, 1))
        tpts = {t: sum(v["pts"] for (u, _), v in pick.items() if u == t) for t in teams}
        tadd = {t: sum(1 for (u, _) in adds if u == t) for t in teams}
        best_t = max(teams, key=lambda t: tpts[t]); busy = max(teams, key=lambda t: tadd[t])
        waiver_html = (f'<section class="sec" id="waiver-mvp"><div class="sec-head"><h2>Waiver Wire MVP</h2><span class="kicker">Pickups ranked by points scored while starting · weeks 1–{W}</span></div>'
                       f'<div class="rum-stats"><div class="rs"><b class="num">{len(adds)}</b><span>Pickups this season</span></div>'
                       f'<div class="rs"><b class="num">{sum(tpts.values()):.1f}</b><span>Points pickups scored as starters</span></div>'
                       f'<div class="rs">{lg(best_t, "lg-sm")}<span>Best waiver team</span><small>{esc(SHORT[best_t])}: {tpts[best_t]:.1f} pts</small></div>'
                       f'<div class="rs">{lg(busy, "lg-sm")}<span>Busiest</span><small>{esc(SHORT[busy])}: {tadd[busy]} pickups</small></div></div>'
                       f'<div class="wv">{wrows}</div></section>')

# ---------- pecking order ----------
allvals = allv; lo, hi = min(allvals) - 4, max(allvals) + 4
def spark(t, w=110, h=32):
    vals = [SEA[t]["weekly"][k] for k in sorted(SEA[t]["weekly"])]
    n = max(len(vals) - 1, 1)
    pts = [(5 + i * (w - 10) / n, h - 5 - (v - lo) / (hi - lo) * (h - 10)) for i, v in enumerate(vals)]
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
    area = path + f" L{pts[-1][0]:.1f},{h} L{pts[0][0]:.1f},{h} Z"
    ex, ey = pts[-1]; ay = h - 5 - (L["avg"] - lo) / (hi - lo) * (h - 10)
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="Weekly scores {", ".join(f2(v) for v in vals)}">'
            f'<path d="{area}" class="sp-area"/><line x1="0" x2="{w}" y1="{ay:.1f}" y2="{ay:.1f}" class="sp-avg"/>'
            f'<path d="{path}" class="sp-line"/><circle cx="{ex:.1f}" cy="{ey:.1f}" r="3.2" class="sp-end"/></svg>')
lmax = max(1.2, max(abs(SEA[t]["luck"]) for t in SEA))
trs = []
for i, t in enumerate(F["ranking"], 1):
    s = SEA[t]; luck = s["luck"]; wd = min(abs(luck) / lmax * 50, 50)
    side = f"left:50%;width:{wd:.1f}%" if luck >= 0 else f"left:{50-wd:.1f}%;width:{wd:.1f}%"
    rec = f'{s["w"]}–{s["l"]}' + (f'–{s["t"]}' if s["t"] else "")
    ap_w, ap_l = s["allplay"].split("-")
    form = "".join(f'<i class="fm {"fw" if r == "W" else "fl"}">{r}</i>' for r in s["results"])
    trs.append(f'''<tr><td class="rk">{i}</td>
<td><span class="po-team">{lg(t, "lg-md")}<span><b>{esc(teams[t]["name"])}</b><small>{esc(teams[t]["owner"])}</small></span></span></td>
<td class="n">{rec}</td><td><span class="form">{form}</span></td><td class="n">{ap_w}–{ap_l}</td><td class="n">{f2(s["pf"])}</td><td>{spark(t)}</td>
<td><span class="luck" title="Luck {luck:+.2f} wins"><span class="luck-mid"></span><span class="luck-bar {'up' if luck >= 0 else 'dn'}" style="{side}"></span></span><span class="num luck-n">{luck:+.2f}</span></td>
<td class="note">{fill(C["pecking_notes"].get(str(t), ""))}</td></tr>''')

# ---------- blotter + missing ----------
blotter = "".join(f'''<div class="case"><div class="mug">{lg(b["team"], "lg-mug")}<span class="mug-no num">{TF[b["team"]]["left_on_bench"]:.2f}</span></div>
<div><span class="kicker">{T(b["team"], True)}</span><h3>{esc(b["title"])}</h3><p>{fill(b["text"])}</p></div></div>''' for b in C["blotter"])
def starter(t, name):
    for n, pos, sl, pts, pr in TF[t]["starters"]:
        if n == name: return pr, pts
    raise SystemExit(f"Missing person {name} is not a starter for team {t}")
mp_rows = [(m, *starter(m["team"], m["player"])) for m in C["missing"]]
mmx = max(max(p, a) for _, p, a in mp_rows) * 1.03
missing = "".join(f'''<div class="poster"><div class="poster-top"><span class="kicker">Missing</span>{lg(m["team"], "lg-sm")}</div>
<h3>{esc(m["player"])}</h3>
<div class="pa"><span class="pa-l">Proj</span><span class="pa-t"><span class="pa-b proj" style="width:{p/mmx*100:.1f}%"></span></span><span class="num">{p:.1f}</span>
<span class="pa-l">Found</span><span class="pa-t"><span class="pa-b act" style="width:{max(a/mmx*100,0.6):.1f}%"></span></span><span class="num">{a:.1f}</span></div>
<p>{fill(m["text"])}</p></div>''' for m, p, a in mp_rows)

# ---------- transaction wire ----------
def started(t, name):
    for n, pos, sl, pts, pr in TF[t]["starters"]:
        if n == name: return pts
    return None
wire = []
for tx in F["transactions"]:
    if not tx.get("verified", True): continue
    t = tx["team"]
    adds = [m[4:] for m in tx["moves"] if m.startswith("ADD:")]
    drops = [m[5:] for m in tx["moves"] if m.startswith("DROP:")]
    chips = "".join(f'<span class="chip in">＋ {esc(a)}{f" <b class=num>{g(started(t, a))}</b>" if started(t, a) is not None else " <b>bench</b>"}</span>' for a in adds)
    chips += "".join(f'<span class="chip out">− {esc(d)}</span>' for d in drops)
    wire.append(f'<div class="wire-row">{lg(t, "lg-sm")}<span class="wire-t">{esc(SHORT[t])}<em>{esc(tx["kind"])}</em></span><span class="chips">{chips}</span></div>')
wire_html = "".join(wire)


# ---------- completed trades + trading block (from the weekly fetch) ----------
import os
PTS = {}; cur = None  # week-W points for every rostered player, from the raw dump
for line in open(f"data/week{W}_raw.txt", encoding="utf-8"):
    line = line.rstrip("\n")
    if line == "ROSTERS": cur = 0; continue
    if cur is None: continue
    if line.startswith("#"): continue
    if "|" not in line: break
    n, pos, sl, pts, pr = line.split("|"); PTS[n] = float(pts)

trades_html = ""  # season's completed trades; section omitted when there are none
TRD = json.load(open("data/trades.json"))["trades"] if os.path.exists("data/trades.json") else []
TRD = [t for t in TRD if t.get("period") is None or t["period"] <= W]
if TRD:
    pmax = max([PTS.get(i["player"], 0) for t in TRD for i in t["items"]] + [1])
    tcards = []
    for t in sorted(TRD, key=lambda t: t["processed"] or "", reverse=True)[:6]:
        a, b = t["teams"][0], t["teams"][-1]
        def side(team):
            got = [i["player"] for i in t["items"] if i["to"] == team]
            rows = "".join(f'<div class="pl"><span>{esc(str(n))}</span><b>{g(PTS[n]) if n in PTS else "—"}</b><span class="pl-bar"><i style="width:{PTS.get(n, 0)/pmax*100:.1f}%"></i></span></div>' for n in got)
            return f'<div class="ru-side">{T(team, True)}<span class="kicker">receives</span>{rows}</div>', sum(PTS.get(n, 0) for n in got)
        sa, ta = side(a); sb, tb = side(b)
        win = a if ta > tb else b if tb > ta else None
        tcards.append(f'<article class="rumor"><div class="ru-head"><span class="kicker">Week {t["period"]} trade · {esc(SHORT[a])} ⇄ {esc(SHORT[b])}</span><span class="stamp acc">Done deal</span></div>'
                      f'<div class="ru-body">{sa}<span class="ru-arrow" aria-hidden="true">⇄</span>{sb}</div>'
                      f'<div class="ru-foot"><span>Week {W} points received: <b class="num">{ta:.1f}</b> vs <b class="num">{tb:.1f}</b></span><span>{"Edge: " + esc(SHORT[win]) if win else "Dead even"}</span></div></article>')
    trades_html = (f'<section class="sec" id="trades"><div class="sec-head"><h2>Trade Desk</h2><span class="kicker">Completed trades this season · bars = week {W} points</span></div>'
                   f'<div class="rum-stats"><div class="rs"><b class="num">{len(TRD)}</b><span>Trades completed</span></div>'
                   f'<div class="rs"><b class="num">{sum(len(t["items"]) for t in TRD)}</b><span>Players moved</span></div></div>'
                   f'<div class="rumors">{"".join(tcards)}</div></section>')

# Trading block ("On the Block"): players their managers marked ON_THE_BLOCK on ESPN. Untouchable and normal
# players are never shown. Built when at least league.json trade_block_min_teams teams (user: 10 of 12 is enough)
# return trading-block data; the section names any teams that didn't report.
block_html = ""
TB = json.load(open("data/trade_block.json")) if os.path.exists("data/trade_block.json") else None
if TB and len(TB["teams_reporting"]) >= LG.get("trade_block_min_teams", NT):
    PINFO = {}; cur = None  # player -> (team, pos, pts, proj) for week W
    for line in open(f"data/week{W}_raw.txt", encoding="utf-8"):
        line = line.rstrip("\n")
        if line == "ROSTERS": cur = 0; continue
        if cur is None: continue
        if line.startswith("#"): cur = int(line[1:]); continue
        if "|" not in line: break
        n, pos, sl, pts, pr = line.split("|"); PINFO[n] = (cur, pos, float(pts), float(pr), sl)
    avail = [(int(tid), p) for tid, ps in TB["block"].items() for p in ps if p["status"] == "ON_THE_BLOCK"]
    missing_t = [t for t in sorted(teams) if t not in TB["teams_reporting"]]
    bcards = []
    for t, p in sorted(avail, key=lambda x: -(PINFO.get(x[1]["player"], (0, 0, 0))[2])):
        info = PINFO.get(p["player"])
        stat = (f'<div class="fs-stat"><span><b class="num">{g(info[2])}</b>week {W} pts</span><span><b class="num">{g(info[3])}</b>projected</span>'
                f'<span><b>{"Started" if info[4] not in ("BE", "IR") else "Bench"}</b>week {W}</span></div>') if info else ""
        bcards.append(f'<article class="forsale"><div class="fs-top"><span class="fs-tag">Available</span>{lg(t, "lg-sm")}</div>'
                     f'<h3>{esc(p["player"])}</h3><span class="kicker">{esc(p["pos"])} · listed by {esc(SHORT[t])}</span>{stat}</article>')
    if not bcards:
        bcards.append('<article class="forsale empty"><h3>Nobody&#39;s selling</h3><span class="kicker">No players on any trading block this week</span></article>')
    note = f'{len(TB["teams_reporting"])} of {NT} teams reporting' + (f' · no trading block from {", ".join(esc(SHORT[t]) for t in missing_t)}' if missing_t else "")
    block_html = (f'<section class="sec" id="trading-block"><div class="sec-head"><h2>On the Block</h2><span class="kicker">Players their managers have listed as available for trade</span></div>'
                  f'<div class="forsale-grid">{"".join(bcards)}</div><p class="note-s">{note}. Set yours on ESPN: My Team → Trading Block.</p></section>')

# ---------- forecast ----------
fc = []
for n in F["next_week"]:
    fav, dog = n["fav"], n["dog"]
    pf = SEA[fav]["avg"] / (SEA[fav]["avg"] + SEA[dog]["avg"]) * 100
    fc.append(f'''<div class="fc"><div class="fc-vs"><span>{lg(fav, "lg-md")}<b>{esc(SHORT[fav])}</b></span><em class="num">−{g(n["spread"])}</em><span class="dog"><b>{esc(SHORT[dog])}</b>{lg(dog, "lg-md")}</span></div>
<div class="fc-split"><span style="width:{pf:.1f}%"><i class="num">{SEA[fav]["avg"]:.1f}</i></span><span><i class="num">{SEA[dog]["avg"]:.1f}</i></span></div>
<div class="odds num"><span>O/U {g(n["ou"])}</span><span>season avg per week</span></div>
<p>{fill(key(n["home"], n["away"], C.get("forecast_blurbs", {})) or "")}</p></div>''')
forecast = (f'<section class="sec" id="forecast"><div class="sec-head"><h2>Week {W+1} Forecast</h2><span class="kicker">Spreads from season averages. For arguing, not betting.</span></div>'
            f'<div class="forecast">{"".join(fc)}</div></section>') if fc else ""

# Player Stats tab (players.py, data from fetch_players.py); empty if data/players is missing
import players as _players
ps_html = _players.build(LG["short_names"], W) if os.path.exists("data/players/meta.json") else ""

out = open("template.html", encoding="utf-8").read()
for k, v in {"<!--PLAYERSTATS-->": ps_html, "/*LOGOS*/": "\n".join(f".lg-{t}{{background-image:url({u})}}" for t, u in logos.items()),
             "<!--CRESTS-->": crests, "<!--UPSETS-->": upsets_html, "<!--TILES-->": tiles_html, "<!--HERO-->": hero, "<!--LEAD-->": lead,
             "<!--SIDEBAR-->": sidebar,
             "<!--SCOREBOARD-->": scoreboard, "<!--BOOMBUST-->": boombust, "<!--POSITIONS-->": positions, "<!--POSKINGS-->": poskings,
             "<!--GAMES-->": "".join(game_cards), "<!--HONOR-->": honor, "<!--HEAT-->": heat, "<!--SCATTER-->": scatter,
             "<!--BLOTTER-->": blotter, "<!--MISSING-->": missing, "<!--PECKING-->": "".join(trs), "<!--WHATIF-->": whatif, "<!--POWER-->": power_html, "<!--ODDS-->": odds_html, "<!--RANGEBENCH-->": rangebench_html, "<!--WAIVERMVP-->": waiver_html, "<!--WIRE-->": wire_html, "<!--RUMORS-->": trades_html + block_html, "<!--FORECAST-->": forecast,
             "{{WEEK}}": str(W), "{{NEXTWEEK}}": str(W + 1), "{{SEASON}}": str(LG["season"]), "{{VOLUME}}": str(LG["volume"]), "{{LEAGUE_NAME}}": esc(LG["league_name"]),
             "{{LEAGUE_FORMAT}}": esc(LG["league_format"]), "{{PRICE}}": esc(LG["price"]), "{{NWEEKS}}": str(len(weeks))}.items():
    out = out.replace(k, v)
import mobile as _mobile
out = _mobile.tag(out)  # phone card layout: tag every table cell with its role and column label
left = re.findall(r"<!--(?!PS-->)[A-Z0-9]+-->|\{\{[A-Z_]+\}\}|\{[TS]\d+\}", out)
open(f"daily-fantasizer-week{W}.html", "w", encoding="utf-8").write(out)
print(f"daily-fantasizer-week{W}.html", len(out), "chars; leftover placeholders:", left)
