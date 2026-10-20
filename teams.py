"""Team-level sections added 2026-10-19 at the user's request (all automatic, no copy):

This Week's Paper
- Matchup of the Week: the next week's game with the smallest spread. Both teams' rest-of-season
  Roster Radars overlaid, plus each lineup slot's blended projection for that week, head to head.

League & Teams
- Manager Report Card: one grade per manager from
    Lineups  (40%) average of actual score / best possible score each week, weeks 1..N
    Waivers  (25%) points scored by free-agent/waiver pickups while in the starting lineup
    Roster   (35%) rest-of-season points per week of the current best lineup (Roster Radar values)
    Trades   (15%, only for teams with a completed trade; the other weights scale down to make room)
             rest-of-season points per week received minus given
  Each part is graded against the other managers by rank: top fifth A, then B, C, D, bottom fifth F.
- One-Man Show: share of each team's starting-lineup points from its top scorer, and from the next two.
- Trade Matchmaker: one-for-one swaps of players at different positions, judged by each team's best starting
  lineup (QB, 2 RB, 2 WR, TE, FLEX; rest-of-season points per week). Every team gets at least one idea
  (user, 2026-10-19). Tiers: win-win (both gain 0.3+, consensus ranks within 12 spots or 25%), small win-win
  (both gain, ranks within 24 spots or 50%), even swap (one gains, the other gives up under a point a week). Suggestions only.
"""
import html, json, os
from collections import defaultdict
from facts import load as _load, optimal as _optimal
import strength as S

esc = lambda s: html.escape(str(s))
LINE = [("QB", ["QB"]), ("RB", ["RB"]), ("RB", ["RB"]), ("WR", ["WR"]), ("WR", ["WR"]), ("TE", ["TE"]), ("FLEX", ["RB", "WR", "TE"])]


def lg(t, size="lg-sm"): return f'<i class="lg lg-{t} {size}" aria-hidden="true"></i>'


def _weeks(W):
    SD = {}
    for k in range(1, W + 1):
        f = f"data/week{k}_raw.txt"
        if not os.path.exists(f):
            return None
        m, slots, t_, sched, ros, tx, lu = _load(f)
        sc = {}
        for gm in sched:
            if gm["wk"] == k and gm["away"]:
                sc[gm["home"]], sc[gm["away"]] = gm["hp"], gm["ap"]
        SD[k] = dict(score=sc, ros=ros, tx=tx, opt={t: _optimal(ros[t], slots)[0] for t in ros})
    return SD


def _lineup(ps, val):
    ps = sorted(ps, key=lambda p: -val(p)); used = set(); rows = []
    for s, el in LINE:
        x = next((p for p in ps if p["key"] not in used and p["pos"] in el), None)
        if x:
            used.add(x["key"])
        rows.append((s, x))
    return rows


def _grade(r):  # r = rank fraction, 1 = best
    return "A" if r >= 0.8 else "B" if r >= 0.6 else "C" if r >= 0.4 else "D" if r >= 0.2 else "F"


def _pct(vals):
    """team -> 0..1 rank fraction (ties share the higher rank); 1 = best."""
    s = sorted(vals.values())
    n = len(s)
    return {t: (s.index(v) / (n - 1) if n > 1 else 1.0) for t, v in vals.items()}


# ------------------------------------------------------------------ report card
def report_card(short, W):
    SD = _weeks(W)
    if not SD:
        return ""
    X = S.compute(short, W); d = X["d"]; teams = X["teams"]; sh = X["short"]
    eff, bench = {}, {}
    for t in teams:
        r = [SD[k]["score"][t] / SD[k]["opt"][t] for k in SD if SD[k]["opt"].get(t)]
        eff[t] = 100 * sum(r) / len(r)
        bench[t] = sum(SD[k]["opt"][t] - SD[k]["score"][t] for k in SD)
    adds = {}
    for k in SD:
        for tx in SD[k]["tx"]:
            if tx["kind"] in ("free agent", "waiver"):
                for mv in tx["moves"]:
                    if mv.startswith("ADD:"):
                        adds.setdefault((tx["team"], mv[4:]), k)
    wpts, nadd = defaultdict(float), defaultdict(int)
    for (t, n), k0 in adds.items():
        nadd[t] += 1
        for k in range(k0, W + 1):
            for p in SD[k]["ros"].get(t, []):
                if p["name"] == n and p["slot"] not in ("BE", "IR"):
                    wpts[t] += p["pts"]
    roster = {t: sum(r[2] for r in X["res"]["ros"][t]) for t in teams}  # best lineup, rest-of-season pts/wk (incl. K, D/ST)
    trd = json.load(open("data/trades.json"))["trades"] if os.path.exists("data/trades.json") else []
    trd = [x for x in trd if x.get("period") is None or x["period"] <= W]
    byname = {p["name"]: p for p in d.P}
    tval = defaultdict(float); ntr = defaultdict(int)
    for x in trd:
        for team in set(x["teams"]):
            ntr[team] += 1
            for i in x["items"]:
                v = byname.get(i["player"], {}).get("ros", 0.0)
                if i["to"] == team:
                    tval[team] += v
                elif i.get("from") == team:
                    tval[team] -= v
    pe, pw, pr = _pct(eff), _pct({t: wpts[t] for t in teams}), _pct(roster)
    pt = _pct({t: tval[t] for t in teams if ntr[t]}) if any(ntr.values()) else {}
    rows = []
    for t in teams:
        if t in pt:
            sc = 0.35 * pe[t] + 0.20 * pw[t] + 0.30 * pr[t] + 0.15 * pt[t]
        else:
            sc = 0.40 * pe[t] + 0.25 * pw[t] + 0.35 * pr[t]
        rows.append((sc, t))
    rows.sort(reverse=True)
    best = rows[0][1]
    html_rows = []
    for i, (sc, t) in enumerate(rows, 1):
        parts = [("Lineups", _grade(pe[t]), f'{eff[t]:.1f}% of best', f'{bench[t]:.0f} pts benched'),
                 ("Waivers", _grade(pw[t]), f'{wpts[t]:.0f} pts started', f'{nadd[t]} pickup{"s" if nadd[t] != 1 else ""}'),
                 ("Roster", _grade(pr[t]), f'{roster[t]:.0f} pts/wk', 'best lineup, rest of season')]
        if t in pt:
            parts.append(("Trades", _grade(pt[t]), f'{tval[t]:+.1f} pts/wk', f'{ntr[t]} trade{"s" if ntr[t] != 1 else ""}'))
        sub = "".join(f'<span class="rc-p"><b class="rc-g g-{g}">{g}</b><span><em>{k}</em>{a}<small>{b}</small></span></span>' for k, g, a, b in parts)
        html_rows.append(f'<div class="rc-row"><span class="rc-big g-{_grade(sc)}">{_grade(sc)}</span>'
                         f'<span class="rc-t">{lg(t)}<b>{esc(sh[t])}</b><small class="num">#{i} · {round(sc * 100)} of 100</small></span>'
                         f'<span class="rc-parts">{sub}</span></div>')
    w_note = ("Lineups 35%, waivers 20%, roster 30%, trades 15% for teams with a completed trade; others " if any(ntr.values()) else "")
    return (f'<section class="sec" id="report-card"><div class="sec-head"><h2>Manager Report Card</h2>'
            f'<span class="kicker">Weeks 1–{W} · graded against the league</span></div>'
            f'<div class="rc">{"".join(html_rows)}</div>'
            f'<p class="note-s">Lineups: actual score as a share of the best possible lineup each week. Waivers: points pickups scored while starting. '
            f'Roster: rest-of-season points per week of the current best lineup (the Roster Radar values). '
            f'{w_note}Weights: lineups 40%, waivers 25%, roster 35%. Each part is graded by rank against the other managers: top fifth A, bottom fifth F. '
            f'{"Trades are graded once a trade is completed." if not any(ntr.values()) else ""}</p></section>')


# ------------------------------------------------------------------ one-man show
def one_man(short, W):
    SD = _weeks(W)
    if not SD:
        return ""
    sh = {int(k): v for k, v in short.items()}
    rows = []
    for t in sorted(sh):
        c = defaultdict(float)
        for k in SD:
            for p in SD[k]["ros"].get(t, []):
                if p["slot"] not in ("BE", "IR"):
                    c[p["name"]] += p["pts"]
        tot = sum(c.values())
        if tot <= 0:
            continue
        top = sorted(c.items(), key=lambda x: -x[1])
        rows.append(dict(t=t, top=top[0][0], pts=top[0][1], share=100 * top[0][1] / tot,
                         next2=100 * sum(v for _, v in top[1:3]) / tot, n2=[n for n, _ in top[1:3]], tot=tot))
    if not rows:
        return ""
    rows.sort(key=lambda r: -r["share"])
    sc = 100 / max(r["share"] + r["next2"] for r in rows) * 0.98
    even = 100 / 9
    body = "".join(
        f'<div class="om-row"><span class="om-t">{lg(r["t"])}<b>{esc(sh[r["t"]])}</b></span>'
        f'<span class="om-bar"><i class="om-1" style="width:{r["share"] * sc:.1f}%" title="{esc(r["top"])}: {r["pts"]:.1f} of {r["tot"]:.1f} pts"></i>'
        f'<i class="om-2" style="width:{r["next2"] * sc:.1f}%" title="{esc(", ".join(r["n2"]))}"></i><span class="om-even" style="left:{even * sc:.1f}%"></span></span>'
        f'<span class="om-v"><b class="num">{r["share"]:.1f}%</b>{esc(r["top"])}<small class="num">top 3: {r["share"] + r["next2"]:.0f}%</small></span></div>'
        for r in rows)
    return (f'<section class="sec" id="one-man-show"><div class="sec-head"><h2>One-Man Show</h2>'
            f'<span class="kicker">Share of starting-lineup points from the top scorer · weeks 1–{W}</span></div>'
            f'<div class="om-key"><span><i class="om-1"></i>Top scorer</span><span><i class="om-2"></i>Next two</span><span><i class="om-ev"></i>Even share (1 of 9 slots)</span></div>'
            f'<div class="om">{body}</div>'
            f'<p class="note-s">Points scored in each team&#39;s starting lineup, weeks 1–{W}, whoever started. The higher the blue bar, the more one injury would hurt.</p></section>')


# ------------------------------------------------------------------ trade matchmaker
def matchmaker(short, W):
    X = S.compute(short, W); d = X["d"]; sh = X["short"]; teams = X["teams"]
    own = [p for p in d.P if p.get("owner")]
    roster = {t: [p for p in own if p["owner"] == t] for t in teams}
    val = lambda p: p["ros"]
    tot = lambda ps: sum(val(x) for _, x in _lineup(ps, val) if x)
    base = {t: tot(roster[t]) for t in teams}
    ecr = lambda p: (d.ros_by.get(p["key"]) or {}).get("rank_ecr")
    close = lambda e1, e2, k, f: abs(e1 - e2) <= max(k, f * min(e1, e2))
    deals = []
    for a in teams:
        for b in teams:
            if b <= a:
                continue
            for x in roster[a]:
                ex = ecr(x)
                if not ex:
                    continue
                for y in roster[b]:
                    if x["pos"] == y["pos"]:
                        continue
                    ey = ecr(y)
                    if not ey or not close(ex, ey, 24, 0.5):
                        continue
                    ga = tot([p for p in roster[a] if p is not x] + [y]) - base[a]
                    gb = tot([p for p in roster[b] if p is not y] + [x]) - base[b]
                    if max(ga, gb) <= 0.05:
                        continue
                    # tier 1: both gain 0.3+, ranks close; tier 2: both gain, ranks fairly close; tier 3: one side gains, the other gives up little
                    if ga >= 0.3 and gb >= 0.3 and close(ex, ey, 12, 0.25):
                        tier = 1
                    elif ga > 0.05 and gb > 0.05:
                        tier = 2
                    elif min(ga, gb) >= -1.0:
                        tier = 3
                    else:
                        continue
                    deals.append(dict(a=a, b=b, x=x, y=y, ga=ga, gb=gb, ex=ex, ey=ey, tier=tier))
    key = lambda z: (z["tier"], -min(z["ga"], z["gb"]) if z["tier"] < 3 else -max(z["ga"], z["gb"]))
    deals.sort(key=key)
    used, pairs, top, seen = set(), set(), [], defaultdict(int)

    def ok(z):
        return z["x"]["key"] not in used and z["y"]["key"] not in used and (z["a"], z["b"]) not in pairs

    def take(z):
        used.update({z["x"]["key"], z["y"]["key"]}); pairs.add((z["a"], z["b"])); top.append(z)
        seen[z["a"]] += 1; seen[z["b"]] += 1
    # every team gets at least one idea (user, 2026-10-19). Teams with the fewest options pick first; a tier-3 idea
    # only counts for the team that gains from it.
    def opts(t):
        return [z for z in deals if ok(z) and ((z["a"] == t and (z["tier"] < 3 or z["ga"] > 0)) or (z["b"] == t and (z["tier"] < 3 or z["gb"] > 0)))]
    for _ in range(len(teams)):
        need = [t for t in teams if not seen[t] and opts(t)]
        if not need:
            break
        t = min(need, key=lambda t: (len(opts(t)), t))
        o = opts(t)  # prefer a real gain (0.3+ pts/wk) for this team, then the better tier, then a partner not used yet
        other = lambda z: z["b"] if z["a"] == t else z["a"]
        mine = lambda z: z["ga"] if z["a"] == t else z["gb"]
        take(min(o, key=lambda z: (mine(z) < 0.3, z["tier"], min(seen[other(z)], 2), key(z))))
    for z in deals:  # then the best remaining win-wins, up to 12 ideas, no team more than twice
        if len(top) >= 12:
            break
        if z["tier"] == 1 and ok(z) and seen[z["a"]] < 2 and seen[z["b"]] < 2:
            take(z)
    top.sort(key=key)
    missing = [t for t in teams if not seen[t]]
    if not top:
        cards = '<article class="tm-card empty"><h3>No easy fits</h3><span class="kicker">No one-for-one swap helps both lineups this week</span></article>'
    else:
        side = lambda t, p, e: (f'<div class="tm-side">{lg(t, "lg-sm")}<span class="kicker">{esc(sh[t])} sends</span>'
                                f'<b>{esc(p["name"])}</b><small class="num">{esc(p["pos"])} · {esc(p["team"])} · ROS #{e} overall</small></div>')
        gain = lambda v: f'<b class="num{" neg" if v < 0 else ""}">{v:+.1f}</b>'
        tag = {1: "Win-win", 2: "Small win-win", 3: "Even swap"}
        cards = "".join(
            f'<article class="tm-card t{z["tier"]}"><span class="tm-tier">{tag[z["tier"]]}</span><div class="tm-body">{side(z["a"], z["x"], z["ex"])}<span class="tm-arrow" aria-hidden="true">⇄</span>{side(z["b"], z["y"], z["ey"])}</div>'
            f'<div class="tm-foot"><span>{esc(sh[z["a"]])} {gain(z["ga"])}</span><span>{esc(sh[z["b"]])} {gain(z["gb"])}</span></div></article>'
            for z in top)
    return (f'<section class="sec" id="matchmaker"><div class="sec-head"><h2>Trade Matchmaker</h2>'
            f'<span class="kicker">One-for-one swaps for every team · suggestions, not rumors</span></div>'
            f'<div class="tm-grid">{cards}</div>'
            f'<p class="note-s">One-for-one swaps of players at different positions, judged by how much each team&#39;s best starting lineup '
            f'(QB, 2 RB, 2 WR, TE, FLEX) scores per week for the rest of the season. '
            f'Numbers = points per week each lineup gains (or gives up). Every team gets at least one idea: win-wins first (both gain), then smaller win-wins with '
            f'ranks a little further apart, then even swaps where one team gains and the other gives up less than a point a week. Each player and each pair of teams appears once'
            f'{"; no fit found for " + ", ".join(esc(sh[t]) for t in missing) if missing else ""}.</p></section>')


# ------------------------------------------------------------------ matchup of the week
def matchup(short, W, F, records):
    nw = F.get("next_week") or []
    if not nw:
        return ""
    g = min(nw, key=lambda n: n["spread"])
    X = S.compute(short, W); d = X["d"]; sh = X["short"]
    a, b = g["fav"], g["dog"]
    nxt = W + 1
    rawp = S.raw_proj(W)
    sched = json.load(open("data/players/nfl_schedule.json")) if os.path.exists("data/players/nfl_schedule.json") else None

    def pj(p):
        if p.get("inj") in ("OUT", "INJURY_RESERVE"):
            return 0.0
        if sched and nxt in sched.get("byes", {}).get(p["team"], []):
            return 0.0
        v = S.proj_for(d, p, nxt, rawp)
        return v or 0.0
    lines = {}
    for t in (a, b):
        ps = [p for p in d.P if p.get("owner") == t]
        lines[t] = [(s, x, pj(x) if x else 0.0) for s, x in _lineup(ps, pj)]
    # kickers and defenses: ESPN's projection for that week (data/players/espn_kdst.json); the best one each team rosters
    kf = "data/players/espn_kdst.json"
    KD = json.load(open(kf)) if os.path.exists(kf) else []
    for t in (a, b):
        for pos in ("D/ST", "K"):
            c = [x for x in KD if x.get("owner") == t and x["pos"] == pos and x.get("proj", {}).get(str(nxt)) is not None]
            best = max(c, key=lambda x: x["proj"][str(nxt)], default=None)
            lines[t].append((pos, {"name": best["name"]} if best else None, float(best["proj"][str(nxt)]) if best else 0.0))
    has_kd = all(lines[t][-1][1] and lines[t][-2][1] for t in (a, b))
    tot = {t: sum(v for _, _, v in lines[t]) for t in (a, b)}
    mx = max(v for t in (a, b) for _, _, v in lines[t]) or 1
    rows = ""
    labels = ["QB", "RB1", "RB2", "WR1", "WR2", "TE", "FLEX", "D/ST", "K"]
    for i, lab in enumerate(labels):
        (_, xa, va), (_, xb, vb) = lines[a][i], lines[b][i]
        wa = va >= vb
        rows += (f'<div class="mw-row"><span class="mw-a{" win" if wa else ""}"><em>{esc(xa["name"]) if xa else "—"}</em><i style="width:{va / mx * 100:.1f}%"></i><b class="num">{va:.1f}</b></span>'
                 f'<span class="mw-s">{lab}</span>'
                 f'<span class="mw-b{" win" if not wa else ""}"><b class="num">{vb:.1f}</b><i style="width:{vb / mx * 100:.1f}%"></i><em>{esc(xb["name"]) if xb else "—"}</em></span></div>')
    sa, sb = X["score"]["ros"][a], X["score"]["ros"][b]
    svg = (f'<svg class="rd-svg mw-svg" viewBox="0 0 240 240" role="img" aria-label="{esc(sh[a])} and {esc(sh[b])} rest-of-season lineup strength by slot">'
           f'{S.frame()}<polygon class="mw-pa" points="{S.poly(sa)}"/><polygon class="mw-pb" points="{S.poly(sb)}"/></svg>')
    rec = lambda t: records.get(t, "")
    head = (f'<div class="mw-head"><div class="mw-team mw-ta">{lg(a, "lg-lg")}<b>{esc(sh[a])}</b><small class="num">{rec(a)}</small></div>'
            f'<div class="mw-mid"><span class="kicker">Spread</span><b class="num">{(esc(sh[a]) + " −" + format(g["spread"], "g")) if g["spread"] else "Pick&#39;em"}</b><small class="num">O/U {g["ou"]:g}</small></div>'
            f'<div class="mw-team mw-tb">{lg(b, "lg-lg")}<b>{esc(sh[b])}</b><small class="num">{rec(b)}</small></div></div>')
    return (f'<section class="sec" id="matchup"><div class="sec-head"><h2>Matchup of the Week</h2>'
            f'<span class="kicker">Week {nxt} · the closest spread on the board</span></div>{head}'
            f'<div class="mw-grid"><figure class="mw-fig">{svg}<figcaption class="mw-key"><span><i class="mw-ka"></i>{esc(sh[a])}</span><span><i class="mw-kb"></i>{esc(sh[b])}</span>'
            f'<span>Roster Radar, rest of season · dashed ring = league average</span></figcaption></figure>'
            f'<div class="mw-list"><span class="kicker">Week {nxt} projected points, slot by slot</span>{rows}'
            f'<div class="mw-row mw-tot"><span class="mw-a"><b class="num">{tot[a]:.1f}</b></span><span class="mw-s">Total</span><span class="mw-b"><b class="num">{tot[b]:.1f}</b></span></div></div></div>'
            f'<p class="note-s">Each team&#39;s best projected lineup for week {nxt}: QB through FLEX use the blended projection (consensus and ESPN); '
            f'kickers and defenses use ESPN&#39;s projection. Byes and players ruled out count zero.'
            f'{"" if has_kd else " ESPN projections for kickers and defenses were not available for this edition, so those slots show zero."}</p></section>')


# ------------------------------------------------------------------ power rankings (animated)
def race(short, W):
    """Power Rankings (animated, user 2026-10-20): each team's crest slides up or down the all-play power ranking
    week by week. All-play = your score against every other team's score that week, summed over the season
    (same rule as the Pecking Order); points for breaks ties. The real record sits beside it so the order
    isn't mistaken for the standings. Plays once when scrolled into view; Play replays, week buttons jump."""
    sh = {int(k): v for k, v in short.items()}
    aw = {t: 0 for t in sh}; al = {t: 0 for t in sh}; w = {t: 0 for t in sh}; l = {t: 0 for t in sh}; pf = {t: 0.0 for t in sh}; weeks = []
    for k in range(1, W + 1):
        f = f"data/week{k}_raw.txt"
        if not os.path.exists(f):
            return ""
        sc = {}
        for g in _load(f)[3]:
            if g["wk"] == k and g["away"]:
                h, a = g["home"], g["away"]; sc[h], sc[a] = g["hp"], g["ap"]
                if g["hp"] > g["ap"]: w[h] += 1; l[a] += 1
                elif g["ap"] > g["hp"]: w[a] += 1; l[h] += 1
        for t in sh:
            pf[t] += sc[t]
            aw[t] += sum(sc[t] > sc[o] for o in sc if o != t); al[t] += sum(sc[t] < sc[o] for o in sc if o != t)
        order = sorted(sh, key=lambda t: (-aw[t], -pf[t]))
        weeks.append({str(t): [i + 1, aw[t], al[t], w[t], l[t]] for i, t in enumerate(order)})
    n = len(sh); fin = weeks[-1]
    rows = "".join(
        f'<div class="sr-row" data-t="{t}" style="transform:translateY({(fin[str(t)][0] - 1) * 100}%)">'
        f'<b class="sr-rk num">{fin[str(t)][0]}</b>{lg(t, "lg-md")}<span class="sr-nm"><b>{esc(sh[t])}</b><small class="sr-rec num">{fin[str(t)][3]}–{fin[str(t)][4]} record</small></span>'
        f'<span class="sr-ap num">{fin[str(t)][1]}–{fin[str(t)][2]}</span>'
        f'<em class="sr-mv"></em></div>' for t in sorted(sh))
    btns = "".join(f'<button type="button" class="pt" data-w="{k}" aria-pressed="{str(k == W).lower()}">Wk {k}</button>' for k in range(1, W + 1))
    data = json.dumps({"weeks": weeks, "n": n}, separators=(",", ":"))
    return (f'<section class="sec" id="power"><div class="sec-head"><h2>Power Rankings</h2>'
            f'<span class="kicker">Week by week · ranked by all-play, not record</span></div>'
            f'<div class="sr-ctl"><button type="button" class="pt sr-play" aria-label="Play the season">▶ Play</button>'
            f'<div class="sr-wks" role="group" aria-label="Week">{btns}</div><span class="sr-now kicker" aria-live="polite">After week {W}</span></div>'
            f'<div class="sr-board" style="--n:{n}"><div class="sr-head"><span>#</span><span></span><span>Team · record</span><span>All-play</span><span>Move</span></div>'
            f'<div class="sr-list" role="list">{rows}</div></div>'
            f'<p class="note-s">All-play: each week every team&#39;s score is checked against all 11 others, so a team that would beat anyone ranks high even after an unlucky draw. '
            f'Points for breaks ties. The record column is the real one. Plays once when you scroll here; press Play to watch again or pick a week. The arrow compares with the week before.</p>'
            f'<script type="application/json" id="sr-data">{data}</script>'
            '''<script>(function(){
var s=document.getElementById('power'),src=document.getElementById('sr-data');if(!s||!src)return;
var D=JSON.parse(src.textContent),W=D.weeks,rows=[].slice.call(s.querySelectorAll('.sr-row')),btns=[].slice.call(s.querySelectorAll('.sr-wks .pt')),now=s.querySelector('.sr-now'),play=s.querySelector('.sr-play'),timer=null;
var still=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
function show(k){var d=W[k-1],p=k>1?W[k-2]:null;
  rows.forEach(function(r){var v=d[r.dataset.t];r.style.transform='translateY('+((v[0]-1)*100)+'%)';
    r.querySelector('.sr-rk').textContent=v[0];r.querySelector('.sr-ap').textContent=v[1]+'\\u2013'+v[2];r.querySelector('.sr-rec').textContent=v[3]+'\\u2013'+v[4]+' record';
    var m=p?p[r.dataset.t][0]-v[0]:0,e=r.querySelector('.sr-mv');e.className='sr-mv '+(m>0?'up':m<0?'dn':'eq');e.textContent=m>0?'\\u25B2'+m:m<0?'\\u25BC'+(-m):'\\u2013';
    r.classList.toggle('lead',v[0]===1)});
  btns.forEach(function(b){b.setAttribute('aria-pressed',String(+b.dataset.w===k))});now.textContent='After week '+k;}
function stop(){if(timer){clearInterval(timer);timer=null}play.textContent='\\u25B6 Play'}
function run(){stop();if(still){show(W.length);return}var k=1;show(k);play.textContent='\\u25A0 Stop';
  timer=setInterval(function(){k++;if(k>W.length){stop();return}show(k)},1500)}
play.addEventListener('click',function(){timer?stop():run()});
btns.forEach(function(b){b.addEventListener('click',function(){stop();show(+b.dataset.w)})});
show(W.length);
if('IntersectionObserver' in window&&!still){var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){io.disconnect();setTimeout(run,300)}})},{threshold:.35});io.observe(s.querySelector('.sr-board'))}
})();</script></section>''')
