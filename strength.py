"""Roster Radar: one radar chart per team, one spoke per lineup slot (QB, RB1, RB2, WR1, WR2, TE,
FLEX, D/ST, K), with a switch between the season so far and the rest of the season.
Added 2026-10-19 at the user's request.

Player value (points per game):
- Season (weeks 1..N): PPR points per game played through the edition week (players.Data, same
  numbers as the Player Stats tab).
- Rest of season: FantasyPros ROS consensus position rank turned into points with this season's
  scoring curve (the rank-k player at a position is worth what the k-th best scorer at that
  position has averaged, 3+ games). Players the consensus doesn't rank: half PPR/g, half
  volume-expected PPR/g, capped below the last ranked player; injured reserve counts a quarter.
- K and D/ST: season view = season points per game from the weekly ESPN dumps, pulled toward the
  league average by two games of prior so a single big week doesn't dominate. Rest-of-season view =
  ESPN's weekly projections for the coming weeks (falls back to the season number without them).

Lineup: each team's best player fills QB, RB1, RB2, WR1, WR2, TE, then FLEX (best RB/WR/TE left),
using current rosters (QB-TE from the player data, K and D/ST from espn_kdst.json or week N's roster).
Slot strength = 75% the starter + 25% the first backup at that position (user: depth counts, but
less than quality). Scaled per slot so 50 = league average and 0/100 = the furthest team below/above.
"""
import html, json, math, os
from collections import defaultdict
from facts import load as _load
import players as _players

SLOTS = ["QB", "RB1", "RB2", "WR1", "WR2", "TE", "FLEX", "D/ST", "K"]
ELIG = {"QB": ["QB"], "RB1": ["RB"], "RB2": ["RB"], "WR1": ["WR"], "WR2": ["WR"], "TE": ["TE"], "FLEX": ["RB", "WR", "TE"],
        "D/ST": ["D/ST"], "K": ["K"]}
Q, DEP = 0.75, 0.25
MODES = [("season", "Weeks 1–{W}"), ("ros", "Rest of season")]
esc = lambda s: html.escape(str(s))


def _kdst(W):
    """team -> [(name, pos, season value, rest-of-season value)] for kickers and D/STs.
    Season: points per game over weeks 1..W from the raw dumps, with two games of league-average prior.
    Rest of season: ESPN's weekly projections for the coming weeks (data/players/espn_kdst.json, user 2026-10-19:
    "default to ESPN projections"); falls back to the season value when ESPN has none.
    Owners come from espn_kdst.json when present (current rosters, like QB-TE), else from week W's dump."""
    tot = defaultdict(lambda: [0.0, 0]); pos = {}; owner = defaultdict(list)
    for k in range(1, W + 1):
        f = f"data/week{k}_raw.txt"
        if not os.path.exists(f):
            continue
        ros = _load(f)[4]
        for t, pl in ros.items():
            for p in pl:
                if p["pos"] not in ("K", "D/ST"):
                    continue
                pos[p["name"]] = p["pos"]
                if not (p["pts"] == 0 and p["proj"] == 0):  # 0 points on a 0 projection = bye / no game
                    tot[p["name"]][0] += p["pts"]; tot[p["name"]][1] += 1
                if k == W and p["slot"] != "IR":
                    owner[t].append(p["name"])
    mu = {}
    for ps in ("K", "D/ST"):
        names = [n for n in tot if pos[n] == ps]
        mu[ps] = sum(tot[n][0] for n in names) / max(1, sum(tot[n][1] for n in names))
    season = lambda n, ps: (tot[n][0] + 2 * mu[ps]) / (tot[n][1] + 2) if n in tot else mu[ps]
    rosv = {}
    kf = "data/players/espn_kdst.json"
    if os.path.exists(kf):
        KD = json.load(open(kf))
        owner = defaultdict(list)
        for x in KD:
            pos[x["name"]] = x["pos"]
            if x.get("owner"):
                owner[x["owner"]].append(x["name"])
            fut = [v for w, v in x.get("proj", {}).items() if int(w) > W and v > 0]
            if fut:
                rosv[x["name"]] = sum(fut) / len(fut)
    return {t: [(n, pos[n], season(n, pos[n]), rosv.get(n, season(n, pos[n]))) for n in ns] for t, ns in owner.items()}


_CACHE = {}


def ros_values(d):
    """Sets p["ros"] on every player in players.Data d: rest-of-season points per game (see module doc)."""
    if getattr(d, "_ros_done", False):
        return
    curve = defaultdict(list)
    for p in d.P:
        if p["g"] >= 3:
            curve[p["pos"]].append(p["ppg"])
    for ps in curve:
        curve[ps].sort(reverse=True)
    cv = lambda ps, r: curve[ps][min(max(r, 1), len(curve[ps])) - 1] if curve[ps] else 0.0
    rk = {}
    for k, r in d.ros_by.items():
        try:
            rk[k] = int("".join(c for c in (r.get("pos_rank") or "") if c.isdigit()))
        except ValueError:
            pass
    last = defaultdict(int)
    for k, r in rk.items():
        last[k.split("|")[1]] = max(last[k.split("|")[1]], r)
    for p in d.P:
        if p["key"] in rk:
            v = cv(p["pos"], rk[p["key"]])
        else:
            xp = p.get("xp")
            v = (0.5 * p["ppg"] + 0.5 * xp) if xp is not None else p["ppg"]
            if p.get("inj") == "INJURY_RESERVE":
                v *= 0.25
            v = min(v, cv(p["pos"], last[p["pos"]] + 1))
        p["ros"] = v
        p["ros_rank"] = rk.get(p["key"])
    d._ros_done = True


def compute(short, W):
    """Shared by build() and teams.py: players.Data, lineup rows per mode/team, and 0-100 slot scores."""
    if (W, tuple(sorted(short.items()))) in _CACHE:
        return _CACHE[(W, tuple(sorted(short.items())))]
    d = _players.Data(short, W)
    ros_values(d)
    shortI = {int(k): v for k, v in short.items()}
    P = [p for p in d.P if p.get("owner")]
    KD = _kdst(W)
    teams = sorted(shortI)
    res = {}  # mode -> team -> list of (slot, starter, sval, backup, bval, raw)
    for mode, val in (("season", lambda p: p["ppg"]), ("ros", lambda p: p["ros"])):
        res[mode] = {}
        for t in teams:
            pool = [(p["name"], p["pos"], val(p)) for p in P if p["owner"] == t] + [(n, ps, sv if mode == "season" else rv) for n, ps, sv, rv in KD.get(t, [])]
            pool.sort(key=lambda x: -x[2])
            used, start = set(), {}
            for s in SLOTS:
                start[s] = next((x for x in pool if x[0] not in used and x[1] in ELIG[s]), None)
                if start[s]:
                    used.add(start[s][0])
            rows = []
            for s in SLOTS:
                b = next((x for x in pool if x[0] not in used and x[1] in ELIG[s]), None)
                sv = start[s][2] if start[s] else 0.0; bv = b[2] if b else 0.0
                rows.append((s, start[s][0] if start[s] else None, sv, b[0] if b else None, bv, Q * sv + DEP * bv))
            res[mode][t] = rows
    score = {}
    for mode in res:
        score[mode] = {t: [] for t in teams}
        for i in range(len(SLOTS)):
            xs = {t: res[mode][t][i][5] for t in teams}
            a = sum(xs.values()) / len(xs); m = max(abs(x - a) for x in xs.values()) or 1
            for t in teams:
                score[mode][t].append(round(50 + 50 * (xs[t] - a) / m))
    out = dict(d=d, res=res, score=score, teams=teams, short=shortI, kd=KD)
    _CACHE[(W, tuple(sorted(short.items())))] = out
    return out


# ---- radar geometry (also used by teams.py for the Matchup of the Week overlay) ----
N_ = len(SLOTS); C_, R_ = 120, 76
ANG = [(-90 + i * 360 / N_) * math.pi / 180 for i in range(N_)]


def pt(v, i, r=R_):
    k = r * (6 + v * 0.94) / 100
    return C_ + math.cos(ANG[i]) * k, C_ + math.sin(ANG[i]) * k


def poly(vs):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(v, i) for i, v in enumerate(vs)))


def frame():
    f = "".join(f'<polygon class="rd-ring{" avg" if r == 50 else ""}" points="{poly([r] * N_)}"/>' for r in (25, 50, 75, 100))
    f += "".join(f'<line class="rd-ax" x1="{C_}" y1="{C_}" x2="{pt(100, i)[0]:.1f}" y2="{pt(100, i)[1]:.1f}"/>' for i in range(N_))
    for i, s in enumerate(SLOTS):
        x, y = pt(100, i, R_ + 18)
        a = "middle" if abs(x - C_) < 4 else ("start" if x > C_ else "end")
        f += f'<text class="rd-lb" x="{x:.1f}" y="{y + 4:.1f}" text-anchor="{a}">{s}</text>'
    return f


def build(short, W):
    if not os.path.exists("data/players/meta.json"):
        return ""
    X = compute(short, W)
    res, score, teams, short = X["res"], X["score"], X["teams"], X["short"]
    # ---- drawing ----
    n = N_
    frame_ = frame()
    nm = lambda x: esc(x) if x else "—"
    order = sorted(teams, key=lambda t: -(sum(score["season"][t]) + sum(score["ros"][t])))
    cards = []
    for t in order:
        shapes, sums, lists = "", "", ""
        for mode, _ in MODES:
            sc = score[mode][t]; rows = res[mode][t]
            dots = "".join(f'<circle class="rd-dot" cx="{pt(v, i)[0]:.1f}" cy="{pt(v, i)[1]:.1f}" r="4"><title>{SLOTS[i]} {v}: {nm(rows[i][1])} {rows[i][2]:.1f}'
                           f'{f" · backup {esc(rows[i][3])} {rows[i][4]:.1f}" if rows[i][3] else " · no backup"}</title></circle>' for i, v in enumerate(sc))
            shapes += f'<g class="m-{mode}"><polygon class="rd-team" points="{poly(sc)}"/>{dots}</g>'
            hi = max(range(n), key=lambda i: sc[i]); lo = min(range(n), key=lambda i: sc[i])
            sums += f'<span class="m-{mode}">Best <b>{SLOTS[hi]}</b> · weakest <b>{SLOTS[lo]}</b></span>'
            lists += f'<div class="rd-list m-{mode}">' + "".join(
                f'<span class="rd-s">{s}</span><span class="rd-p">{nm(r[1])}<small>{"backup " + esc(r[3]) if r[3] else "no backup"}</small></span>'
                f'<b class="num">{sc[i]}</b>' for i, (s, r) in enumerate(zip(SLOTS, rows))) + '</div>'
        aria = "; ".join(f"{lab.format(W=W)}: " + ", ".join(f"{s} {v}" for s, v in zip(SLOTS, score[mode][t])) for mode, lab in MODES)
        cards.append(f'<article class="rd-card"><div class="rd-h"><i class="lg lg-{t} lg-sm" aria-hidden="true"></i><h3>{esc(short[t])}</h3></div>'
                     f'<p class="rd-sum">{sums}</p>'
                     f'<svg class="rd-svg" viewBox="0 0 240 240" role="img" aria-label="{esc(short[t])} lineup strength. {esc(aria)}">{frame_}{shapes}</svg>'
                     f'<details class="rd-more"><summary>Lineup</summary>{lists}</details></article>')
    btns = "".join(f'<button type="button" class="pt" data-m="{m}" aria-pressed="{str(i == 0).lower()}">{esc(l.format(W=W))}</button>' for i, (m, l) in enumerate(MODES))
    return (f'<section class="sec rd" id="roster-radar" data-m="season"><div class="sec-head"><h2>Roster Radar</h2>'
            f'<span class="kicker">Lineup strength by slot · 50 = league average</span></div>'
            f'<div class="rd-bar"><div class="rd-tg" role="group" aria-label="Time frame">{btns}</div>'
            f'<span class="rd-key"><i class="sw-team"></i>Team <i class="sw-avg"></i>League average <i class="sw-max"></i>Best in league</span></div>'
            f'<div class="rd-grid">{"".join(cards)}</div>'
            f'<p class="note-s"><span class="m-season">Weeks 1–{W}: current rosters, scored on PPR points per game so far (a player&#39;s full season counts, wherever he played it). </span>'
            f'<span class="m-ros">Rest of season: consensus rankings turned into points per game using this season&#39;s scoring at each rank. </span>'
            f'Best player fills each slot, FLEX takes the best RB/WR/TE left. Each slot is 75% the starter and 25% his first backup. '
            f'Kickers and defenses: season points per game in the weeks 1–{W} view, ESPN&#39;s projections for the coming weeks in the rest-of-season view. Hover a dot or open Lineup for the players.</p>'
            '<script>(function(){var s=document.getElementById("roster-radar");if(!s)return;var b=s.querySelectorAll(".rd-tg .pt");'
            'b.forEach(function(x){x.addEventListener("click",function(){s.dataset.m=x.dataset.m;'
            'b.forEach(function(y){y.setAttribute("aria-pressed",y===x?"true":"false")})})})})();</script></section>')


if __name__ == "__main__":
    import sys
    LG = json.load(open("league.json"))
    out = build(LG["short_names"], int(sys.argv[1]))
    print(len(out))


# ---- weekly projections (shared by Matchup of the Week and the Player Stats trend lines) ----
_RAWP = {}


def raw_proj(W):
    """name -> {week: ESPN projection at the time} for every player on a league roster, weeks 1..W (from the raw dumps)."""
    if W in _RAWP:
        return _RAWP[W]
    out = defaultdict(dict)
    for k in range(1, W + 1):
        f = f"data/week{k}_raw.txt"
        if os.path.exists(f):
            for t, pl in _load(f)[4].items():
                for p in pl:
                    out[p["name"]][k] = p["proj"]
    _RAWP[W] = out
    return out


def proj_for(d, p, w, rawp):
    """Blended projection for week w: mean of the FantasyPros consensus projection and ESPN's (as the
    Player Stats tab does). Past weeks use ESPN's projection from that week's dump when the player was rostered."""
    vals = []
    e = d.ecr.get(p["key"], {}).get(w)
    if e and e.get("r2p_pts") not in (None, ""):
        vals.append(float(e["r2p_pts"]))
    espn = p["proj"].get(w)
    if espn is None:
        espn = rawp.get(p["name"], {}).get(w)
    if espn is not None:
        vals.append(float(espn))
    return sum(vals) / len(vals) if vals else None
