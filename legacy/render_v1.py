"""The Daily Fantasizer: renderer.
Usage: python3 render.py 5      (reads data/week5_facts.json + data/week5_copy.json)
Writes daily-fantasizer-week5.html. Charts, numbers and layout come from facts;
words come from the copy file. {T7} = full team name with crest, {S7} = short name with crest."""
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
NT = len(teams)
esc = html.escape
WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen"}

def lg(t, size=""): return f'<i class="lg lg-{t} {size}" aria-hidden="true"></i>'
def T(t, short=False): return f'<span class="tm">{lg(t)}{esc(SHORT[t] if short else teams[t]["name"])}</span>'
def fill(s):
    s = re.sub(r"\{T(\d+)\}", lambda m: T(int(m.group(1))), s)
    return re.sub(r"\{S(\d+)\}", lambda m: T(int(m.group(1)), True), s)
def f2(x): return f"{x:.2f}"
def key(a, b, d): return d.get(f"{a}-{b}") or d.get(f"{b}-{a}")

L = F["league"]; games = F["games"]

# ---------- ticker (automatic) ----------
cl, tp = L["closest"], L["top_player"]
first, *rest = tp[1]["name"].split(" ")
ticker = "".join([
    f'<div><span><b>League average</b>{L["avg"]:.2f} pts</span></div>',
    f'<div>{lg(L["high"])}<span><b>High score</b>{f2(TF[L["high"]]["week_pts"])}</span></div>',
    f'<div>{lg(cl["winner"])}<span><b>Closest game</b>{cl["margin"]:.2f} pts</span></div>',
    f'<div>{lg(tp[0])}<span><b>Top player</b>{esc(first[0] + ". " + " ".join(rest))} · {tp[1]["pts"]:g}</span></div>',
    f'<div><span><b>Left on benches</b>{L["total_left"]:.2f} pts</span></div>'])
crests = "".join(f'<i class="lg lg-{t}"></i>' for t in sorted(teams))

# ---------- hero + lead ----------
h = C["hero"]; hw, hl = h["winner"], h["loser"]
hero = f'''<section class="hero" aria-label="Page one result">
  <div class="side"><i class="lg lg-{hw} lg-xl"></i><span class="score">{f2(TF[hw]["week_pts"])}</span><span class="tname">{esc(teams[hw]["name"])}</span></div>
  <div class="mid"><b>{esc(h["big"])}</b><span>{esc(h["label"])}</span></div>
  <div class="side lose"><i class="lg lg-{hl} lg-xl"></i><span class="score">{f2(TF[hl]["week_pts"])}</span><span class="tname">{esc(teams[hl]["name"])}</span></div>
</section>'''
ld = C["lead"]
lead = (f'<article class="lead"><span class="kicker">{esc(ld["kicker"])}</span><h2>{esc(ld["headline"])}</h2>'
        f'<p class="deck">{esc(ld["deck"])}</p><div class="body">' + "".join(f"<p>{fill(p)}</p>" for p in ld["paragraphs"]) + "</div></article>")

# ---------- sidebar boxes ----------
def viz(v):
    if not v: return ""
    if v["type"] == "twin":
        return (f'<div class="twin">{lg(v["left"], "lg-md")}<span>{esc(v["left_value"])}</span><span class="eq">{esc(v.get("symbol", "="))}</span>'
                f'<span>{esc(v["right_value"])}</span>{lg(v["right"], "lg-md")}</div>')
    if v["type"] == "wins":  # actual wins vs all-play expected wins
        mx = max(max(SEA[t]["w"], SEA[t]["expected_wins"]) for t in v["teams"]) or 1
        rows = []
        for i, t in enumerate(v["teams"]):
            s = SEA[t]
            rows.append(f'<div{" style=\"margin-top:6px\"" if i else ""}><span>{T(t, True)}</span><span></span><span></span></div>'
                        f'<div><span>Actual</span><i class="b" style="width:{s["w"]/mx*100:.1f}%"></i><span>{s["w"]:.2f}</span></div>'
                        f'<div><span>Earned</span><i class="b alt" style="width:{s["expected_wins"]/mx*100:.1f}%"></i><span>{s["expected_wins"]:.2f}</span></div>')
        return f'<div class="minibars" aria-label="Actual wins versus all-play expected wins">{"".join(rows)}</div>'
    if v["type"] == "bars":  # free-form: {"type":"bars","rows":[{"team":3,"label":"x","value":12.3}]}
        mx = max(r["value"] for r in v["rows"]) or 1
        return '<div class="minibars">' + "".join(
            f'<div><span>{T(r["team"], True) if "team" in r else esc(r["label"])}</span><i class="b{" alt" if r.get("alt") else ""}" style="width:{r["value"]/mx*100:.1f}%"></i><span>{r["value"]:g}</span></div>'
            for r in v["rows"]) + "</div>"
    return ""
sidebar = "".join(f'<div class="box{" hi" if b.get("style") == "hi" else ""}"><span class="kicker">{esc(b["kicker"])}</span><h3>{esc(b["title"])}</h3>{viz(b.get("viz"))}<p>{fill(b["text"])}</p></div>' for b in C["sidebar"])

# ---------- scoreboard chart ----------
win = {g["winner"] for g in games if not g["tie"]}
MAX = math.ceil((max(TF[t]["optimal"] for t in TF) + 5) / 10) * 10
avgp = L["avg"] / MAX * 100
rows = []
for t in sorted(TF, key=lambda t: -TF[t]["week_pts"]):
    a, o = TF[t]["week_pts"], TF[t]["optimal"]
    rows.append(f'''<div class="br" title="{esc(teams[t]['name'])}: {f2(a)} scored, {f2(o)} possible ({f2(o-a)} left on bench)">
<span class="br-name">{lg(t)}<span>{esc(SHORT[t])}</span></span>
<span class="br-track"><span class="br-bar {"w" if t in win else "l"}" style="width:{a/MAX*100:.2f}%"></span><span class="br-gap" style="left:{a/MAX*100:.2f}%;width:{(o-a)/MAX*100:.2f}%"></span><span class="avg" style="left:{avgp:.2f}%"></span></span>
<span class="br-val num">{f2(a)} <em>+{o-a:.1f}</em></span></div>''')
ticks = "".join(f'<span class="tick{" near" if 0 < abs(v/MAX*100-avgp) < 12 else ""}{" near-m" if 0 < abs(v/MAX*100-avgp) < 25 and v else ""}" style="left:{v/MAX*100:.2f}%">{v}</span>' for v in range(0, MAX + 1, 50))
scoreboard = f'''<div class="chart" role="img" aria-label="Week {W} scores by team, with points left on the bench" style="--grid:{50/MAX*100:.2f}%">
<div class="br-grid"><span></span><span class="axis">{ticks}<span class="avgline" style="left:{avgp:.2f}%"><b>avg {L["avg"]:.2f}</b></span></span><span></span></div>
{"".join(rows)}
<div class="legend"><span><i class="sw w"></i>Won</span><span><i class="sw l"></i>Lost</span><span><i class="sw gap"></i>Points left on the bench (best possible lineup)</span></div></div>'''

# ---------- game cards ----------
cards = []
for g in sorted(games, key=lambda g: g["margin"]):
    w, l = g["winner"], g["loser"]
    rc = key(w, l, C["recaps"]) or {"headline": "", "text": ""}
    share = g["ws"] / (g["ws"] + g["ls"]) * 100
    flag = '<span class="flag">Best lineup would have won</span>' if g["loser_optimal_would_win"] else ""
    cards.append(f'''<article class="game">
<div class="vs"><div class="side">{lg(w, "lg-lg")}<b class="num">{f2(g["ws"])}</b><span>{esc(SHORT[w])}</span></div>
<span class="vs-mid">{"tied" if g["tie"] else "def."}<br><em class="num">by {g["margin"]:.2f}</em></span>
<div class="side lose">{lg(l, "lg-lg")}<b class="num">{f2(g["ls"])}</b><span>{esc(SHORT[l])}</span></div></div>
<div class="split" title="{f2(g['ws'])} to {f2(g['ls'])}"><span style="width:{share:.1f}%"></span></div>
<h3>{esc(rc["headline"])}</h3>{flag}<p>{fill(rc["text"])}</p></article>''')

# ---------- honor ----------
ho = C.get("honor")
honor = (f'''<section class="honor" aria-label="{esc(ho["kicker"])}">{lg(ho["team"], "lg-lg")}
<div class="big">{esc(ho["big"])}<small>{esc(ho["big_label"])}</small></div>
<div><span class="kicker">{esc(ho["kicker"])}</span><h3>{esc(ho["title"])}</h3><p>{fill(ho["text"])}</p></div></section>''') if ho else ""

# ---------- blotter (booking number = points left on bench) ----------
blotter = "".join(f'''<div class="case"><div class="mug">{lg(b["team"], "lg-mug")}<span class="mug-no num">{TF[b["team"]]["left_on_bench"]:.2f}</span></div>
<div><span class="kicker">{T(b["team"])}</span><h3>{esc(b["title"])}</h3><p>{fill(b["text"])}</p></div></div>''' for b in C["blotter"])

# ---------- missing persons (proj/actual looked up from the roster) ----------
def starter(t, name):
    for n, pos, sl, pts, pr in TF[t]["starters"]:
        if n == name: return pr, pts
    raise SystemExit(f"Missing person {name} is not a starter for team {t}")
mp_rows = [(m, *starter(m["team"], m["player"])) for m in C["missing"]]
pmx = max(max(p, a) for _, p, a in mp_rows) * 1.03 if mp_rows else 1
missing = "".join(f'''<div class="poster"><div class="poster-top"><span class="kicker">Missing</span>{lg(m["team"], "lg-sm")}</div>
<h3>{esc(m["player"])}</h3>
<div class="pa"><span class="pa-l">Projected</span><span class="pa-t"><span class="pa-b proj" style="width:{p/pmx*100:.1f}%"></span></span><span class="num">{p:.1f}</span>
<span class="pa-l">Found</span><span class="pa-t"><span class="pa-b act" style="width:{max(a/pmx*100,0.6):.1f}%"></span></span><span class="num">{a:.1f}</span></div>
<p>{fill(m["text"])}</p><span class="poster-foot">Last seen on {T(m["team"], True)}</span></div>''' for m, p, a in mp_rows)

# ---------- pecking order ----------
allvals = [v for t in SEA for v in SEA[t]["weekly"].values()]
lo, hi = min(allvals) - 4, max(allvals) + 4
nweeks = max(len(SEA[t]["weekly"]) for t in SEA)
def spark(t, w=120, h=34):
    vals = [SEA[t]["weekly"][k] for k in sorted(SEA[t]["weekly"])]
    n = max(len(vals) - 1, 1)
    pts = [(6 + i * (w - 12) / n, h - 5 - (v - lo) / (hi - lo) * (h - 10)) for i, v in enumerate(vals)]
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
    ex, ey = pts[-1]; ay = h - 5 - (L["avg"] - lo) / (hi - lo) * (h - 10)
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="Weekly scores {", ".join(f2(v) for v in vals)}">'
            f'<title>Weeks 1–{W}: {" · ".join(f2(v) for v in vals)}</title><line x1="0" x2="{w}" y1="{ay:.1f}" y2="{ay:.1f}" class="sp-avg"/>'
            f'<path d="{path}" class="sp-line"/><circle cx="{ex:.1f}" cy="{ey:.1f}" r="3.5" class="sp-end"/></svg>')
lmax = max(1.2, max(abs(SEA[t]["luck"]) for t in SEA))
trs = []
for i, t in enumerate(F["ranking"], 1):
    s = SEA[t]; luck = s["luck"]; wd = min(abs(luck) / lmax * 50, 50)
    side = f"left:50%;width:{wd:.1f}%" if luck >= 0 else f"left:{50-wd:.1f}%;width:{wd:.1f}%"
    rec = f'{s["w"]}–{s["l"]}' + (f'–{s["t"]}' if s["t"] else "")
    ap_w, ap_l = s["allplay"].split("-")
    trs.append(f'''<tr><td class="rk">{i}</td>
<td><span class="po-team">{lg(t, "lg-md")}<span><b>{esc(teams[t]["name"])}</b><small>{esc(teams[t]["owner"])}</small></span></span></td>
<td class="n">{rec}</td><td class="n">{ap_w}–{ap_l}</td><td class="n">{f2(s["pf"])}</td><td>{spark(t)}</td>
<td><span class="luck" title="Luck {luck:+.2f} wins"><span class="luck-mid"></span><span class="luck-bar {'up' if luck >= 0 else 'dn'}" style="{side}"></span></span><span class="num luck-n">{luck:+.2f}</span></td>
<td class="note">{fill(C["pecking_notes"].get(str(t), ""))}</td></tr>''')

# ---------- classifieds ----------
ads = "".join(f'<div class="ad"><div class="ad-head">{lg(a["team"], "lg-sm")}<h3>{esc(a["title"])}</h3></div><p>{fill(a["text"])}</p><p class="from">{T(a["team"], True)}</p></div>' for a in C["ads"])

# ---------- forecast ----------
fc = []
for n in F["next_week"]:
    fav, dog = n["fav"], n["dog"]
    pf = SEA[fav]["avg"] / (SEA[fav]["avg"] + SEA[dog]["avg"]) * 100
    fc.append(f'''<div class="fc"><div class="fc-vs"><span>{lg(fav, "lg-md")}<b>{esc(SHORT[fav])}</b></span><em>vs</em><span class="dog"><b>{esc(SHORT[dog])}</b>{lg(dog, "lg-md")}</span></div>
<div class="split fc-split"><span style="width:{pf:.1f}%"></span></div>
<div class="odds num"><span>{esc(SHORT[fav])} −{n["spread"]:g}</span><span>O/U {n["ou"]:g}</span><span>Avg {SEA[fav]["avg"]:.1f} vs {SEA[dog]["avg"]:.1f}</span></div>
<p>{fill(key(n["home"], n["away"], C.get("forecast_blurbs", {})) or "")}</p></div>''')
forecast = (f'<section class="sec" id="forecast"><div class="sec-head"><h2>Week {W+1} Forecast</h2><span class="kicker">Lines from season scoring averages. For arguing, not betting.</span></div>'
            f'<div class="forecast">{"".join(fc)}</div></section>') if fc else ""

out = open("template.html", encoding="utf-8").read()
for k, v in {"/*LOGOS*/": "\n".join(f".lg-{t}{{background-image:url({u})}}" for t, u in logos.items()),
             "<!--CRESTS-->": crests, "<!--TICKER-->": ticker, "<!--HERO-->": hero, "<!--LEAD-->": lead,
             "<!--SIDEBAR-->": sidebar, "<!--SCOREBOARD-->": scoreboard, "<!--GAMES-->": "".join(cards),
             "<!--HONOR-->": honor, "<!--BLOTTER-->": blotter, "<!--MISSING-->": missing, "<!--PECKING-->": "".join(trs),
             "<!--ADS-->": ads, "<!--FORECAST-->": forecast,
             "{{WEEK}}": str(W), "{{SEASON}}": str(LG["season"]), "{{VOLUME}}": str(LG["volume"]), "{{LEAGUE_NAME}}": esc(LG["league_name"]),
             "{{LEAGUE_FORMAT}}": esc(LG["league_format"]), "{{PRICE}}": esc(LG["price"]), "{{NGAMES}}": WORDS.get(len(games), str(len(games))), "{{NOTHERS}}": WORDS.get(NT - 1, str(NT - 1))}.items():
    out = out.replace(k, v)
missing_logos = [t for t in teams if t not in logos]
if missing_logos: print("WARNING: no crest for teams", missing_logos)
left = re.findall(r"<!--[A-Z]+-->|\{\{[A-Z_]+\}\}|\{[TS]\d+\}", out)
open(f"daily-fantasizer-week{W}.html", "w", encoding="utf-8").write(out)
print(f"daily-fantasizer-week{W}.html", len(out), "bytes; leftover placeholders:", left)
