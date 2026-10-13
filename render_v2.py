"""The Daily Fantasizer v2 (graphics-first edition).
Usage: python3 render_v2.py 5   (reads data/week5_facts.json + data/week5_copy_v2.json, template_v2.html)
Writes daily-fantasizer-week5-v2.html. Every chart number comes from the facts file."""
import json, re, html, math, sys

W = int(sys.argv[1])
F = json.load(open(f"data/week{W}_facts.json"))
C = json.load(open(f"data/week{W}_copy_v2.json"))
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
cards = []
for g_ in sorted(games, key=lambda g_: g_["margin"]):
    w, l = g_["winner"], g_["loser"]
    rc = key(w, l, C["recaps"]) or {"headline": "", "text": ""}
    gm = max(TF[w]["optimal"], TF[l]["optimal"], g_["ws"])
    def lane(t, s):
        o = TF[t]["optimal"]
        return (f'<div class="lane"><span class="lane-t">{lg(t)}</span><span class="lane-track"><span class="lane-bar {"w" if t == w else "l"}" style="width:{s/gm*100:.1f}%"></span>'
                f'<span class="lane-opt" style="left:{o/gm*100:.1f}%" title="Best lineup {f2(o)}"></span></span><b class="num">{f2(s)}</b></div>')
    flag = '<span class="flag">Best lineup would have won</span>' if g_["loser_optimal_would_win"] else ""
    cards.append(f'''<article class="game"><div class="g-head"><span class="kicker">{esc(SHORT[w])} def. {esc(SHORT[l])}</span><span class="margin num">+{g_["margin"]:.2f}</span></div>
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


# ---------- trade rumors (from data/trades.json; only offers ESPN shows this account) ----------
import os, datetime as _dt
from collections import Counter
rumors = ""
if os.path.exists("data/trades.json"):
    TR = json.load(open("data/trades.json"))["trades"]
    PTS = {}; cur = None  # week-W points for every rostered player, from the raw dump
    for line in open(f"data/week{W}_raw.txt", encoding="utf-8"):
        line = line.rstrip("\n")
        if line == "ROSTERS": cur = 0; continue
        if cur is None: continue
        if line.startswith("#"): cur = int(line[1:]); continue
        if "|" not in line: break
        n, pos, sl, pts, pr = line.split("|"); PTS[n] = float(pts)
    def P(x): return _dt.datetime.fromisoformat(x.rstrip("Z"))
    def sig(t): return sorted((i["player"], i["from"], i["to"]) for i in t["items"])
    props = [t for t in TR if t["type"] == "TRADE_PROPOSAL" and t["status"] == "PENDING" and t["items"]]
    offers = []
    for pr in props:
        end = next((t for t in TR if t["type"] == "TRADE_PROPOSAL" and t["status"] in ("CANCELED", "EXECUTED") and t["items"]
                    and sig(t) == sig(pr) and t["proposed"] >= pr["proposed"]), None)
        other = next(i["from"] for i in pr["items"] if i["from"] != pr["team"])
        dec = end and next((t for t in TR if t["type"] == "TRADE_DECLINE" and t["proposed"] == end["proposed"]), None)
        if end is None: out, cls = "Pending", "pen"
        elif end["status"] == "EXECUTED": out, cls = "Accepted", "acc"
        elif dec: out, cls = "Declined", "dec"
        else: out, cls = "Expired", "exp"
        mins = (P(end["proposed"]) - P(pr["proposed"])).total_seconds() / 60 if end else None
        offers.append(dict(fr=pr["team"], to=other, week=pr["period"], out=out, cls=cls, mins=mins,
                           give=[i["player"] for i in pr["items"] if i["from"] == pr["team"]],
                           get=[i["player"] for i in pr["items"] if i["from"] == other]))
    if offers:
        shopped = Counter(n for o in offers for n in o["give"]).most_common(1)[0]
        outs = Counter(o["out"] for o in offers)
        pmax = max([PTS.get(n, 0) for o in offers for n in o["give"] + o["get"]] + [1])
        def dur(m):
            if m < 90: return f"{m:.0f} min"
            if m < 48 * 60: return f"{m/60:.0f} hrs"
            return f"{m/1440:.0f} days"
        def side(t, names, cls):
            rows = "".join(f'<div class="pl"><span>{esc(n)}</span><b>{g(PTS[n]) if n in PTS else "—"}</b><span class="pl-bar"><i style="width:{PTS.get(n, 0)/pmax*100:.1f}%"></i></span></div>' for n in names)
            return f'<div class="ru-side {cls}">{T(t, True)}{rows}</div>', sum(PTS.get(n, 0) for n in names)
        rcards = []
        for o in sorted(offers, key=lambda o: -o["week"]):
            a, ta = side(o["fr"], o["give"], "give"); b, tb = side(o["to"], o["get"], "get")
            when = f'{o["out"].lower()} after {dur(o["mins"])}' if o["mins"] is not None else "still on the table"
            rcards.append(
                f'<article class="rumor"><div class="ru-head"><span class="kicker">Week {o["week"]} offer · {esc(SHORT[o["fr"]])} → {esc(SHORT[o["to"]])}</span>'
                f'<span class="stamp {o["cls"]}">{o["out"]}</span></div>'
                f'<div class="ru-body">{a}<span class="ru-arrow" aria-hidden="true">⇄</span>{b}</div>'
                f'<div class="ru-foot"><span>Week {W}: offered <b class="num">{ta:.1f}</b> for <b class="num">{tb:.1f}</b></span><span>{when}</span></div></article>')
        stats = (f'<div class="rum-stats"><div class="rs"><b class="num">{len(offers)}</b><span>Offers sent</span></div>'
                 f'<div class="rs"><b class="num">{outs.get("Declined", 0)}</b><span>Declined</span></div>'
                 f'<div class="rs"><b class="num">{outs.get("Expired", 0) + outs.get("Pending", 0)}</b><span>Ignored / expired</span></div>'
                 f'<div class="rs hot"><b class="num">{shopped[1]}×</b><span>Most shopped</span><small>{esc(shopped[0])}: {g(PTS.get(shopped[0], 0))} pts in week {W}</small></div></div>')
        rumors = stats + f'<div class="rumors">{"".join(rcards)}</div>'

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

out = open("template_v2.html", encoding="utf-8").read()
for k, v in {"/*LOGOS*/": "\n".join(f".lg-{t}{{background-image:url({u})}}" for t, u in logos.items()),
             "<!--CRESTS-->": crests, "<!--TILES-->": tiles_html, "<!--HERO-->": hero, "<!--LEAD-->": lead,
             "<!--SIDEBAR-->": sidebar,
             "<!--SCOREBOARD-->": scoreboard, "<!--BOOMBUST-->": boombust, "<!--POSITIONS-->": positions, "<!--POSKINGS-->": poskings,
             "<!--GAMES-->": "".join(cards), "<!--HONOR-->": honor, "<!--HEAT-->": heat, "<!--SCATTER-->": scatter,
             "<!--BLOTTER-->": blotter, "<!--MISSING-->": missing, "<!--PECKING-->": "".join(trs), "<!--WIRE-->": wire_html, "<!--RUMORS-->": rumors, "<!--FORECAST-->": forecast,
             "{{WEEK}}": str(W), "{{SEASON}}": str(LG["season"]), "{{VOLUME}}": str(LG["volume"]), "{{LEAGUE_NAME}}": esc(LG["league_name"]),
             "{{LEAGUE_FORMAT}}": esc(LG["league_format"]), "{{PRICE}}": esc(LG["price"]), "{{NWEEKS}}": str(len(weeks))}.items():
    out = out.replace(k, v)
left = re.findall(r"<!--[A-Z0-9]+-->|\{\{[A-Z_]+\}\}|\{[TS]\d+\}", out)
open(f"daily-fantasizer-week{W}-v2.html", "w", encoding="utf-8").write(out)
print(f"daily-fantasizer-week{W}-v2.html", len(out), "chars; leftover placeholders:", left)
