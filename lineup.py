"""Optimal Lineup (Player Stats > Compare Players; user 2026-10-28).

"Add an optimal lineup tab that is only visible to me. Consider every stat at each position and suggest the best
lineup for the coming week. As accurate as possible."

Who sees it: only a device that claimed the owner's team (league.json `owner_team`) in Rule Changes, i.e. the
`fz-team` sign-in in localStorage. Everyone else never sees the tab button or the panel. It is hidden, not secret:
the numbers are in the page source, like every roster on the site.

How the projection is chosen (re-checked every build, so it follows the data as the season goes):
1. Every QB/RB/WR/TE starts from the blended projection (mean of the FantasyPros consensus and ESPN), the same
   number the rest of Player Stats uses.
2. Back-test: for every player-week from week 3 to the edition week, rebuild what we knew before that week
   (season PPR/g, last 3, target-share and snap trends, the opponent's points allowed to the position, the Vegas
   implied team total, FantasyPros vs ESPN disagreement) and fit those as adjustments to the blend (ridge, leave
   one week out). The adjustments are used only if they beat the plain blend out of sample by 1%+; otherwise the
   blend stands. (Through week 7 they didn't: last-3 form picked the right player in close calls less often than
   a coin flip, and matchup / Vegas were already priced into the consensus.)
3. Uncertainty from the same back-test: the miss grows with the projection (sd = a + b x projection, fit on the
   residuals); QBs separately; kickers and D/STs from ESPN's own misses in the weekly dumps.
4. Injury status (ESPN): out / IR / suspended = 0; doubtful counts 30%; questionable 93% (inactives come 90
   minutes before kickoff, so most of the risk is in-game). Byes = 0.

The lineup: every legal QB / 2 RB / 2 WR / TE / FLEX / D/ST / K from the owner's roster is scored and the one
with the best chance to beat this week's opponent wins (their best projected lineup, same model; normal model
of both totals, QB and his own pass catchers correlated). That is nearly always the highest projected total;
when it isn't, the page says why. Also shown: every bench player's chance to outscore the starter he'd replace,
a pivot plan for questionable starters (only a backup who kicks off at the same time or later can still be
swapped in), and free agents who'd beat a starter.

Built inside the Player Stats pane (players.build), so the midweek `players.yml` refreshes (Tue-Thu, Sat,
Sunday 11:47am) keep it current with the latest projections and injury news.
"""
import html, itertools, json, math, os
from collections import defaultdict
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/Detroit")
except Exception:  # pragma: no cover
    _ET = None

esc = lambda s: html.escape(str(s))
POS = ["QB", "RB", "WR", "TE"]
SLOT_ORDER = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "D/ST", "K"]
OUT = {"OUT", "INJURY_RESERVE", "SUSPENSION"}
PPLAY = {"QUESTIONABLE": 0.93, "DOUBTFUL": 0.30}
RHO = {"WR": 0.35, "TE": 0.30, "RB": 0.12}      # QB with his own pass catchers / backs
FEATS = ["Last 3", "Season PPR/g", "Matchup", "Vegas total", "Target share trend", "Snap trend", "FantasyPros vs ESPN"]
SQ2PI = math.sqrt(math.pi / 2)


def _last(n):
    parts = [w for w in n.replace(" D/ST", "").split(" ") if w not in ("Jr.", "Sr.", "II", "III", "IV", "V")]
    return parts[-1] if parts else n


def lg(t, size="lg-sm"): return f'<i class="lg lg-{t} {size}" aria-hidden="true"></i>'
def f1(x): return "–" if x is None else f"{x:.1f}"
def pc(x): return "–" if x is None else f"{x * 100:.0f}%"
def Phi(z): return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _sched():
    f = "data/players/nfl_schedule.json"
    return json.load(open(f)) if os.path.exists(f) else {}


def _games(sch, w):
    """team -> opponent, home, kickoff, Vegas implied total (team and opponent), game total, for week w."""
    G = {}
    for g in sch.get("games", []):
        if g.get("week") != w:
            continue
        tot, sp = g.get("total"), g.get("spread")
        hi = (tot + sp) / 2 if tot is not None and sp is not None else None
        ai = (tot - sp) / 2 if tot is not None and sp is not None else None
        G[g["home"]] = {"opp": g["away"], "home": True, "ko": g.get("kickoff"), "imp": hi, "oimp": ai, "tot": tot}
        G[g["away"]] = {"opp": g["home"], "home": False, "ko": g.get("kickoff"), "imp": ai, "oimp": hi, "tot": tot}
    return G


def _ko(iso):
    if not iso:
        return ""
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        t = t.astimezone(_ET) if _ET else t
        h = t.strftime("%I").lstrip("0")
        return f'{t.strftime("%a")} {h}:{t.strftime("%M")}{"a" if t.hour < 12 else "p"}'
    except Exception:
        return ""


def _allowed(d, upto):
    """Defense -> {pos: PPR per game allowed}, weeks < upto; and league averages."""
    T = _sched().get("teams", {})
    allow = defaultdict(lambda: defaultdict(float)); gm = defaultdict(set)
    for p in d.P:
        for k in d.games(p):
            if k >= upto:
                continue
            o = (T.get(p["team"], {}).get(str(k)) or {}).get("opp")
            if o:
                allow[o][p["pos"]] += p["act"][k]["pts"]; gm[o].add(k)
    dv = {o: {ps: allow[o][ps] / len(gm[o]) for ps in POS} for o in allow if gm[o]}
    avg = {ps: (sum(v[ps] for v in dv.values()) / len(dv)) if dv else 0 for ps in POS}
    return dv, avg


def _ridge(X, y, lam):
    k = len(X[0])
    A = [[sum(x[i] * x[j] for x in X) + (lam if i == j else 0) for j in range(k)] for i in range(k)]
    b = [sum(x[i] * t for x, t in zip(X, y)) for i in range(k)]
    for c in range(k):
        piv = max(range(c, k), key=lambda r: abs(A[r][c])); A[c], A[piv] = A[piv], A[c]; b[c], b[piv] = b[piv], b[c]
        for r in range(k):
            if r != c and A[c][c]:
                f = A[r][c] / A[c][c]; A[r] = [a - f * x for a, x in zip(A[r], A[c])]; b[r] -= f * b[c]
    return [b[i] / A[i][i] if A[i][i] else 0 for i in range(k)]


def _feats(r):
    b = r["base"]
    return [r["l3"] - b, r["ppg"] - b, b * (r["mr"] - 1), b * (r["it"] - 1), b * r["ts"], b * r["sn"],
            (r["fp"] - r["es"]) if r["fp"] is not None and r["es"] is not None else 0.0]


def _row(d, p, w, prev, fp, es, dv, avg, imp, mimp, T):
    """What we knew about player p before week w (prev = his games before w)."""
    vals = [x for x in (fp, es) if x is not None]
    base = sum(vals) / len(vals)
    pts = [p["act"][k]["pts"] for k in prev]
    u = d.use.get(p["key"], {})
    m = lambda xs: sum(xs) / len(xs) if xs else None
    get = lambda key, ws: [u[k][key] for k in ws if k in u and u[k].get(key) is not None]
    tsl, tsa, sl, sa = m(get("ts", prev[-3:])), m(get("ts", prev)), m(get("snap", prev[-3:])), m(get("snap", prev))
    opp = (T.get(p["team"], {}).get(str(w)) or {}).get("opp")
    mr = (dv[opp][p["pos"]] / avg[p["pos"]]) if opp in dv and avg.get(p["pos"]) else 1.0
    return {"base": base, "fp": fp, "es": es, "ppg": m(pts) or 0.0, "l3": m(pts[-3:]) or 0.0,
            "ts": (tsl - tsa) if tsl is not None and tsa is not None else 0.0,
            "sn": (sl - sa) if sl is not None and sa is not None else 0.0,
            "mr": mr, "it": (imp.get(p["team"]) or mimp) / mimp if mimp else 1.0}


def calibrate(d, W):
    """Back-test weeks 3..W. Returns the error model, any adopted adjustments and the numbers for the page."""
    import strength as S
    rawp = S.raw_proj(W)
    sch = _sched(); T = sch.get("teams", {})
    rows = []
    for w in range(3, W + 1):
        G = _games(sch, w); imp = {t: g["imp"] for t, g in G.items() if g["imp"] is not None}
        mimp = sum(imp.values()) / len(imp) if imp else 0
        dv, avg = _allowed(d, w)
        for p in d.P:
            gs = d.games(p)
            if w not in gs:
                continue
            prev = [k for k in gs if k < w]
            if len(prev) < 2:
                continue
            e = d.ecr.get(p["key"], {}).get(w)
            fp = float(e["r2p_pts"]) if e and e.get("r2p_pts") not in (None, "") else None
            es = rawp.get(p["name"], {}).get(w)
            if fp is None and es is None:
                continue
            r = _row(d, p, w, prev, fp, es, dv, avg, imp, mimp, T)
            if r["base"] < 3:
                continue
            r.update(w=w, pos=p["pos"], y=p["act"][w]["pts"])
            rows.append(r)
    cal = {"weeks": [3, W], "n": len(rows), "adj": {}, "sd": {}, "rep": {}}
    for grp, ps in (("skill", ("RB", "WR", "TE")), ("QB", ("QB",))):
        R = [r for r in rows if r["pos"] in ps]
        if len(R) < 40:
            cal["sd"][grp] = (3.5, 0.3) if grp == "skill" else (6.5, 0.0)
            continue
        # error model: |miss| grows with the projection
        X = [[1, r["base"]] for r in R]; y = [abs(r["y"] - r["base"]) * SQ2PI for r in R]
        a, b = _ridge(X, y, 1e-6)
        if grp == "QB":  # few QBs: one number
            a, b = (sum(y) / len(y), 0.0)
        cal["sd"][grp] = (max(a, 1.0), max(b, 0.0))
        # do the adjustments beat the blend out of sample?
        mae_b = sum(abs(r["y"] - r["base"]) for r in R) / len(R)
        best = None
        for lam in (1000, 5000):
            err = n = 0
            for w in range(3, W + 1):
                tr = [r for r in R if r["w"] != w]; te = [r for r in R if r["w"] == w]
                if not te or len(tr) < 30:
                    continue
                beta = _ridge([_feats(r) for r in tr], [r["y"] - r["base"] for r in tr], lam)
                for r in te:
                    err += abs(r["y"] - r["base"] - sum(bb * x for bb, x in zip(beta, _feats(r)))); n += 1
            if n and (best is None or err / n < best[0]):
                best = (err / n, lam)
        rep = {"n": len(R), "blend": mae_b, "adj": best[0] if best else None,
               "l3": sum(abs(r["y"] - r["l3"]) for r in R) / len(R)}
        both = [r for r in R if r["fp"] is not None and r["es"] is not None]
        if both:
            rep["fp"] = sum(abs(r["y"] - r["fp"]) for r in both) / len(both)
            rep["es"] = sum(abs(r["y"] - r["es"]) for r in both) / len(both)
            rep["blend_both"] = sum(abs(r["y"] - r["base"]) for r in both) / len(both)
        if best and best[0] < 0.99 * mae_b:
            cal["adj"][grp] = _ridge([_feats(r) for r in R], [r["y"] - r["base"] for r in R], best[1])
        cal["rep"][grp] = rep
    # close calls: when two skill players are projected within 3 points, how often does each signal pick the winner?
    cc = {"base": [0, 0], "l3": [0, 0]}
    for w in range(3, W + 1):
        R = [r for r in rows if r["w"] == w and r["pos"] != "QB"]
        for x, z in itertools.combinations(R, 2):
            if abs(x["base"] - z["base"]) > 3 or x["y"] == z["y"]:
                continue
            for k in cc:
                cc[k][1] += 1; cc[k][0] += (x[k] > z[k]) == (x["y"] > z["y"])
    cal["close"] = {k: (v[0] / v[1] if v[1] else None) for k, v in cc.items()}
    # kickers and D/STs: ESPN's own misses in the weekly dumps
    from facts import load as _load
    miss = defaultdict(list)
    for k in range(1, W + 1):
        f = f"data/week{k}_raw.txt"
        if not os.path.exists(f):
            continue
        for t, pl in _load(f)[4].items():
            for x in pl:
                if x["pos"] in ("K", "D/ST") and x["proj"] > 0 and x["slot"] not in ("IR",):
                    miss[x["pos"]].append(x["pts"] - x["proj"])
    for ps, dflt in (("K", 4.5), ("D/ST", 6.0)):
        m = miss.get(ps) or []
        cal["sd"][ps] = (math.sqrt(sum(e * e for e in m) / len(m)) if len(m) >= 20 else dflt, 0.0)
    return cal


def project(d, W, cal):
    """key -> projection for week N = W + 1 with mean, sd, status and every stat the page shows."""
    import lookup as L
    N = W + 1
    sch = _sched(); T = sch.get("teams", {}); byes = sch.get("byes", {})
    G = _games(sch, N); imp = {t: g["imp"] for t, g in G.items() if g["imp"] is not None}
    mimp = sum(imp.values()) / len(imp) if imp else 0
    dv, avg = _allowed(d, N)
    rank = {}
    for ps in POS:
        for i, o in enumerate(sorted(dv, key=lambda o: -dv[o][ps]), 1):
            rank[(o, ps)] = i
    adv = L.adv_totals(d, W)
    out = {}
    for p in d.P:
        e = d.ecr.get(p["key"], {}).get(N) or {}
        fp = float(e["r2p_pts"]) if e.get("r2p_pts") not in (None, "") else None
        es = p["proj"].get(N)
        g = G.get(p["team"]) or {}
        bye = N in byes.get(p["team"], []) or not g
        inj = p.get("inj") or "ACTIVE"
        if fp is None and es is None and not p.get("owner"):
            continue
        prev = [k for k in d.games(p) if k <= W]
        if fp is None and es is None:
            r = None; mu = 0.0
        else:
            r = _row(d, p, N, prev, fp, es, dv, avg, imp, mimp, T)
            mu = r["base"]
            grp = "QB" if p["pos"] == "QB" else "skill"
            beta = cal["adj"].get(grp)
            if beta:
                mu = max(0.0, mu + sum(b * x for b, x in zip(beta, _feats(r))))
        a, b = cal["sd"]["QB" if p["pos"] == "QB" else "skill"]
        sd = a + b * mu if mu > 0 else 0.0
        st = ""
        if bye:
            mu, sd, st = 0.0, 0.0, "bye"
        elif inj in OUT:
            mu, sd, st = 0.0, 0.0, "out"
        elif inj in PPLAY:
            q = PPLAY[inj]
            sd = math.sqrt(q * sd * sd + q * (1 - q) * mu * mu)
            mu *= q
            st = inj[0]
        elif mu <= 0:
            st = "none"
        opp = g.get("opp")
        t = adv.get(p["key"], {})
        ng = len(prev)
        out[p["key"]] = {
            "k": p["key"], "n": p["name"], "pos": p["pos"], "tm": p["team"], "o": p.get("owner") or 0, "inj": inj, "st": st,
            "mu": mu, "sd": sd, "fp": fp, "es": es, "base": r["base"] if r else None,
            "rk": e.get("pos_rank"), "rmin": e.get("rank_min"), "rmax": e.get("rank_max"), "gr": e.get("start_sit_grade"),
            "opp": opp, "home": g.get("home"), "ko": g.get("ko"), "imp": g.get("imp"), "tot": g.get("tot"),
            "mr": (dv[opp][p["pos"]] / avg[p["pos"]]) if opp in dv and avg.get(p["pos"]) else None,
            "mrk": rank.get((opp, p["pos"])), "nd": len(dv),
            "ppg": p["ppg"], "l3": p["l3"], "xp": p.get("xp"), "g": p["g"],
            "ts": p["ts"], "ts3": p["ts_l3"], "sn": p["snap"], "sn3": p["snap_l3"],
            "tg": p["tgt_g"], "tch": p["tch_g"], "att": p["att_g"], "car": p["car_g"],
            "rz": ((t.get("rzt") or 0) + (t.get("rzc") or 0)) / ng if ng else None,
        }
    return out


def kdst(W, cal, owner=None):
    """Kickers and D/STs: ESPN's projection for week N, sd from ESPN's misses, season points per game from the dumps."""
    from facts import load as _load
    N = W + 1
    f = "data/players/espn_kdst.json"
    if not os.path.exists(f):
        return {}
    G = _games(_sched(), N)
    tot = defaultdict(lambda: [0.0, 0])
    for k in range(1, W + 1):
        fr = f"data/week{k}_raw.txt"
        if os.path.exists(fr):
            for t, pl in _load(fr)[4].items():
                for x in pl:
                    if x["pos"] in ("K", "D/ST") and not (x["pts"] == 0 and x["proj"] == 0):
                        tot[x["name"]][0] += x["pts"]; tot[x["name"]][1] += 1
    out = {}
    for x in json.load(open(f)):
        pr = x.get("proj", {}).get(str(N))
        if pr is None:
            continue
        g = G.get(x["team"]) or {}
        st = "bye" if not g or pr == 0 else ""
        sd = cal["sd"][x["pos"]][0] if pr > 0 else 0.0
        out[x["name"]] = {"k": "kd|" + x["name"], "n": x["name"], "pos": x["pos"], "tm": x["team"], "o": x.get("owner") or 0,
                          "inj": "ACTIVE", "st": st, "mu": float(pr), "sd": sd, "es": float(pr),
                          "ppg": (tot[x["name"]][0] / tot[x["name"]][1]) if tot[x["name"]][1] else None,
                          "opp": g.get("opp"), "home": g.get("home"), "ko": g.get("ko"), "imp": g.get("imp"), "oimp": g.get("oimp"), "tot": g.get("tot")}
    return out


def _cov(a, b):
    """QB with his own pass catchers / backs move together."""
    if a["tm"] != b["tm"] or a["tm"] in ("FA", None):
        return 0.0
    if a["pos"] == "QB" and b["pos"] in RHO:
        return RHO[b["pos"]] * a["sd"] * b["sd"]
    if b["pos"] == "QB" and a["pos"] in RHO:
        return RHO[a["pos"]] * a["sd"] * b["sd"]
    return 0.0


def _stats(lu):
    mu = sum(x["mu"] for x in lu)
    var = sum(x["sd"] ** 2 for x in lu) + 2 * sum(_cov(a, b) for a, b in itertools.combinations(lu, 2))
    return mu, var


EMPTY = lambda pos: {"k": "empty|" + pos, "n": "Empty slot", "pos": pos, "tm": "", "o": 0, "inj": "ACTIVE", "st": "empty", "mu": 0.0, "sd": 0.0}


def optimize(sk, kd, opp=None):
    """Exact search over every legal lineup. opp = (mean, variance) of the opponent's total: then the lineup with the
    best chance to win is chosen (ties: more points). Returns (by win chance, by points); each = (slots, mean, var)."""
    by = defaultdict(list)
    for x in sk:
        by[x["pos"]].append(x)
    for ps in by:
        by[ps].sort(key=lambda x: -x["mu"]); by[ps] = by[ps][:7]
    for ps, n in (("QB", 1), ("RB", 3), ("WR", 3), ("TE", 1)):
        while len(by[ps]) < n:
            by[ps].append(EMPTY(ps))
    kk = sorted([x for x in kd if x["pos"] == "K"], key=lambda x: -x["mu"])[:1] or [EMPTY("K")]
    dd = sorted([x for x in kd if x["pos"] == "D/ST"], key=lambda x: -x["mu"])[:1] or [EMPTY("D/ST")]
    best_p = best_w = None
    for qb in by["QB"][:3]:
        for rb in itertools.combinations(by["RB"], 2):
            for wr in itertools.combinations(by["WR"], 2):
                for te in by["TE"][:4]:
                    used = {qb["k"], te["k"], *[x["k"] for x in rb + wr]}
                    for fx in [x for x in by["RB"] + by["WR"] + by["TE"] if x["k"] not in used]:
                        slots = [qb, rb[0], rb[1], wr[0], wr[1], te, fx, dd[0], kk[0]]
                        mu, var = _stats(slots)
                        if best_p is None or mu > best_p[1] + 1e-9:
                            best_p = (slots, mu, var)
                        if opp:
                            pw = Phi((mu - opp[0]) / math.sqrt(max(var + opp[1], 1e-6)))
                            if best_w is None or pw > best_w[3] + 1e-9 or (abs(pw - best_w[3]) <= 1e-9 and mu > best_w[1]):
                                best_w = (slots, mu, var, pw)
    return (best_w[:3] if best_w else best_p), best_p


def _pwin(a, b):
    """Chance player a outscores player b (independent normals)."""
    s = math.sqrt(a["sd"] ** 2 + b["sd"] ** 2)
    if s <= 0:
        return 1.0 if a["mu"] > b["mu"] else 0.0 if a["mu"] < b["mu"] else 0.5
    return Phi((a["mu"] - b["mu"]) / s)


# ------------------------------------------------------------------ page
def _sub(x):
    bits = [esc(x["tm"])] if x.get("tm") else []
    if x.get("opp"):
        bits.append(("vs. " if x.get("home") else "@ ") + esc(x["opp"]))
    if x.get("ko"):
        bits.append(esc(_ko(x["ko"])))
    if x["st"] == "bye":
        bits.append("bye")
    return " · ".join(bits)


def _tag(x):
    if x["st"] in ("out",):
        return ' <span class="inj">O</span>'
    if x["inj"] == "INJURY_RESERVE":
        return ' <span class="inj">IR</span>'
    if x["st"] in ("Q", "D"):
        return f' <span class="inj">{x["st"]}</span>'
    return ""


def _box(label, val, sub=""):
    return f'<div class="lu-b"><span>{label}</span><b class="num">{val}</b>{f"<small>{sub}</small>" if sub else ""}</div>'


def _every(x):
    """Every stat that bears on his week, grouped the same way for every player at the position."""
    if x["pos"] in ("K", "D/ST"):
        b = [_box("ESPN proj", f1(x.get("es"))), _box("Season pts/g", f1(x.get("ppg"))),
             _box("Floor / ceiling", f'{f1(max(0, x["mu"] - .84 * x["sd"]))}–{f1(x["mu"] + .84 * x["sd"])}')]
        if x.get("imp") is not None:
            b.append(_box("Team total", f1(x["imp"]), f'game O/U {f1(x.get("tot"))}'))
            if x["pos"] == "D/ST":
                b.append(_box("Opp. total", f1(x.get("oimp")), "lower is better"))
        return "".join(b)
    mr = x.get("mr")
    mtxt = (f'#{x["mrk"]} of {x["nd"]}' if x.get("mrk") else "–")
    msub = (f'{(mr - 1) * 100:+.0f}% vs avg' if mr else "")
    b = [_box("Projection", f1(x["mu"]), f'blend {f1(x.get("base"))}' if x.get("base") is not None and abs((x.get("base") or 0) - x["mu"]) > .05 else ""),
         _box("FantasyPros", f1(x.get("fp"))), _box("ESPN", f1(x.get("es"))),
         _box("Consensus", esc(x.get("rk") or "–"), f'range {x.get("rmin") or "–"}–{x.get("rmax") or "–"}' + (f' · grade {esc(x["gr"])}' if x.get("gr") else "")),
         _box("Floor / ceiling", f'{f1(max(0, x["mu"] - .84 * x["sd"]))}–{f1(x["mu"] + .84 * x["sd"])}', "20th–80th pct"),
         _box(f'Matchup vs {x["pos"]}', mtxt, msub),
         _box("Team total", f1(x.get("imp")), f'game O/U {f1(x.get("tot"))}' if x.get("tot") is not None else ""),
         _box("PPR/g", f1(x.get("ppg")), f'{x.get("g") or 0} games'),
         _box("Last 3", f1(x.get("l3"))),
         _box("Expected", f1(x.get("xp")), "PPR/g from volume")]
    if x["pos"] == "QB":
        b += [_box("Pass att/g", f1(x.get("att"))), _box("Rush att/g", f1(x.get("car")))]
    else:
        b += [_box("Target share", pc(x.get("ts")), f'last 3 {pc(x.get("ts3"))}'),
              _box("Snaps", pc(x.get("sn")), f'last 3 {pc(x.get("sn3"))}'),
              _box("Touches/g" if x["pos"] == "RB" else "Targets/g", f1(x.get("tch") if x["pos"] == "RB" else x.get("tg"))),
              _box("Red zone/g", f1(x.get("rz")), "targets + carries")]
    return "".join(b)


def _rowhtml(slot, x, mx, extra=""):
    lo, hi = max(0.0, x["mu"] - .84 * x["sd"]), x["mu"] + .84 * x["sd"]
    s = lambda v: min(100.0, v / mx * 100) if mx else 0
    bar = (f'<span class="lu-bar" aria-hidden="true"><i class="lu-rg" style="left:{s(lo):.1f}%;width:{max(.8, s(hi) - s(lo)):.1f}%"></i>'
           f'<i class="lu-mu" style="left:{s(x["mu"]):.1f}%"></i></span>') if x["mu"] > 0 else '<span class="lu-bar lu-z" aria-hidden="true"></span>'
    cls = " lu-off" if x["st"] in ("bye", "out", "empty", "none") else ""
    return (f'<details class="lu-r{cls}"><summary><span class="lu-slot s-{esc(slot.replace("/", ""))}">{esc(slot)}</span>'
            f'<span class="lu-who"><b>{esc(x["n"])}{_tag(x)}</b><small>{_sub(x)}{extra}</small></span>{bar}'
            f'<b class="lu-pts num">{f1(x["mu"])}</b></summary><div class="lu-x">{_every(x) if x["st"] != "empty" else "<p class=note-s>Nobody healthy to play here. See the wire below.</p>"}</div></details>')


def section(d, W, short, own_team):
    N = W + 1
    cal = calibrate(d, W)
    P = project(d, W, cal)
    K = kdst(W, cal)
    mine = [x for x in P.values() if x["o"] == own_team]
    mykd = [x for x in K.values() if x["o"] == own_team]
    if not mine:
        return ""
    # this week's opponent (league schedule)
    opp_id = None
    try:
        for g in json.load(open("data/schedule.json"))["games"]:
            if g["wk"] == N and own_team in (g["home"], g["away"]):
                opp_id = g["away"] if g["home"] == own_team else g["home"]
    except Exception:
        pass
    opp = None
    if opp_id:
        _, ob = optimize([x for x in P.values() if x["o"] == opp_id], [x for x in K.values() if x["o"] == opp_id])
        opp = ob
    (slots, mu, var), (pslots, pmu, pvar) = optimize(mine, mykd, (opp[1], opp[2]) if opp else None)
    pw = Phi((mu - opp[1]) / math.sqrt(max(var + opp[2], 1e-6))) if opp else None
    mx = max([x["mu"] + .84 * x["sd"] for x in slots + mine + mykd] + [1])
    started = {x["k"] for x in slots}
    names = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "D/ST", "K"]

    # bench: who he'd replace and his chance to outscore that starter
    bench = sorted([x for x in mine + mykd if x["k"] not in started], key=lambda x: -x["mu"])
    def rival(b):
        ok = [s for i, s in enumerate(slots) if s["pos"] == b["pos"] or (names[i] == "FLEX" and b["pos"] in ("RB", "WR", "TE"))]
        return min(ok, key=lambda s: s["mu"]) if ok else None
    close = []
    brows = []
    for b in bench:
        r = rival(b)
        if r is None or b["st"] in ("bye", "out", "none"):
            why = {"bye": " · on bye", "out": " · ruled out", "none": " · no projection"}.get(b["st"], "")
            brows.append(_rowhtml("BN", b, mx, why)); continue
        p = _pwin(b, r)
        if p >= 0.40:
            close.append((b, r, p))
        brows.append(_rowhtml("BN", b, mx, f' · {p * 100:.0f}% to outscore {esc(_last(r["n"]) if r["n"] != "Empty slot" else "the empty slot")}'))

    # pivots for questionable / doubtful starters: a backup who kicks off at the same time or later
    piv = []
    for i, s in enumerate(slots):
        if s["st"] not in ("Q", "D"):
            continue
        elig = [b for b in bench if b["st"] not in ("bye", "out", "none") and (b["pos"] == s["pos"] or (names[i] == "FLEX" and b["pos"] in ("RB", "WR", "TE")))]
        later = [b for b in elig if (b.get("ko") or "") >= (s.get("ko") or "")]
        best = max(later or elig, key=lambda b: b["mu"]) if elig else None
        if best:
            ok = best in later
            piv.append(f'<li><b>{esc(s["n"])}</b> is {"questionable" if s["st"] == "Q" else "doubtful"} ({esc(_ko(s.get("ko")))}). '
                       + (f'If he\'s inactive (90 min before kickoff), start <b>{esc(best["n"])}</b> ({f1(best["mu"])}, {esc(_ko(best.get("ko")))}).'
                          if ok else f'Your best backup, <b>{esc(best["n"])}</b>, plays earlier ({esc(_ko(best.get("ko")))}), so decide before that kickoff.')
                       + '</li>')

    # if the win-chance lineup differs from the most-points lineup, say why
    swap = ""
    if [x["k"] for x in slots] != [x["k"] for x in pslots]:
        a = [x for x in slots if x["k"] not in {y["k"] for y in pslots}]
        b = [x for x in pslots if x["k"] not in started]
        if a and b:
            swap = (f'<p class="lu-note">Most projected points would start {esc(b[0]["n"])} ({f1(b[0]["mu"])}); {esc(a[0]["n"])} '
                    f'({f1(a[0]["mu"])}) gives you the better chance to win this matchup ({"more upside as the underdog" if pw is not None and pw < .5 else "a safer floor as the favorite"}).</p>')

    # free agents who'd beat a starter
    fa = [x for x in list(P.values()) + list(K.values()) if not x["o"] and x["st"] not in ("bye", "out", "none") and x["mu"] > 0]
    ups = []
    for x in fa:
        r = rival(x)
        if r and x["mu"] - r["mu"] >= 1.0:
            ups.append((x["mu"] - r["mu"], x, r))
    ups.sort(key=lambda t: -t[0])
    seen = set(); fa_html = ""
    for g, x, r in ups:
        if r["k"] in seen and len(seen) >= 3:
            continue
        seen.add(r["k"])
        fa_html += (f'<div class="lu-fa"><span class="lu-slot s-{esc(x["pos"].replace("/", ""))}">{esc(x["pos"])}</span><span class="lu-who"><b>{esc(x["n"])}{_tag(x)}</b>'
                    f'<small>{_sub(x)} · over {esc(r["n"])} ({f1(r["mu"])})</small></span><b class="lu-gain num">+{g:.1f}</b></div>')
        if fa_html.count('class="lu-fa"') >= 5:
            break
    wr = None
    try:
        wr = json.load(open("data/players/waivers.json"))["current"]["order"].get(str(own_team))
    except Exception:
        pass

    # hero
    sname = lambda t: esc(short.get(t, f"Team {t}"))
    hero = (f'<div class="lu-hero"><div class="lu-team">{lg(own_team, "lg-md")}<span><small>You</small><b class="num">{mu:.1f}</b></span></div>')
    if opp:
        hero += (f'<div class="lu-meter"><span class="kicker">Win chance</span><b class="num">{pw * 100:.0f}%</b>'
                 f'<span class="lu-track"><i style="width:{pw * 100:.0f}%"></i></span><small class="num">{mu - opp[1]:+.1f} pts · your range ±{.84 * math.sqrt(var):.0f}</small></div>'
                 f'<div class="lu-team lu-them"><span><small>{sname(opp_id)}</small><b class="num">{opp[1]:.1f}</b></span>{lg(opp_id, "lg-md")}</div>')
    hero += '</div>'
    lineup = "".join(_rowhtml(names[i], s, mx) for i, s in enumerate(slots))
    oppfold = ""
    if opp:
        oppfold = (f'<details class="lu-fold"><summary>{sname(opp_id)}\'s best projected lineup · {opp[1]:.1f}</summary><div class="lu-list">'
                   + "".join(_rowhtml(names[i], s, mx) for i, s in enumerate(opp[0])) + '</div></details>')

    # how this works, with the back-test numbers
    rs, rq = cal["rep"].get("skill", {}), cal["rep"].get("QB", {})
    used = "adjusted" if cal["adj"] else "plain"
    cc = cal["close"]
    how = (f'<details class="fo-how lu-how"><summary>How this works</summary><div class="note-s">'
           f'<p><b>Projection.</b> Each player starts from the blended projection (FantasyPros consensus and ESPN, averaged). '
           f'Every build re-tests weeks {cal["weeks"][0]}–{cal["weeks"][1]} ({cal["n"]} player-weeks): {", ".join(FEATS)} are tried as adjustments, '
           f'and kept only if they beat the blend on weeks they weren\'t fit on. This week the {used} blend is used'
           + (f' (RB/WR/TE miss: blend {rs["blend"]:.2f} pts, with adjustments {rs["adj"]:.2f}, last-3 average {rs["l3"]:.2f}' if rs.get("adj") is not None else "")
           + (f'; QB: {rq["blend"]:.2f} vs {rq["adj"]:.2f}' if rq.get("adj") is not None else "") + ")."
           + (f' Average miss when both sources posted a number, RB/WR/TE: blend {rs["blend_both"]:.2f}, FantasyPros alone {rs["fp"]:.2f}, ESPN alone {rs["es"]:.2f}.' if rs.get("fp") else "")
           + (f' In close calls (projections within 3 points) the blend picked the higher scorer {cc["base"] * 100:.0f}% of the time; last-3 form, {cc["l3"] * 100:.0f}%.' if cc.get("base") and cc.get("l3") else "")
           + '</p>'
           f'<p><b>Range.</b> Floor and ceiling are the 20th and 80th percentile, from how far projections missed in this league\'s data '
           f'(RB/WR/TE about {cal["sd"]["skill"][0]:.1f} + {cal["sd"]["skill"][1]:.2f} × projection; QB {cal["sd"]["QB"][0]:.1f}; K {cal["sd"]["K"][0]:.1f}; D/ST {cal["sd"]["D/ST"][0]:.1f}). '
           f'Questionable counts {PPLAY["QUESTIONABLE"] * 100:.0f}% of his projection, doubtful {PPLAY["DOUBTFUL"] * 100:.0f}%, out, IR and byes zero. Kickers and defenses use ESPN\'s projection.</p>'
           f'<p><b>Lineup.</b> Every legal QB / 2 RB / 2 WR / TE / FLEX / D/ST / K from your roster is scored against {sname(opp_id) if opp_id else "your opponent"}\'s best projected lineup, '
           f'and the one with the best chance to win is shown (a QB and his own receivers count as linked). Bench percentages = his chance to outscore the starter he\'d replace. '
           f'Tap any player for every stat behind his number. Refreshes Tuesday to Thursday, Saturday and Sunday 11:47am with new projections and injury news.</p></div></details>')

    upd = esc(d.meta.get("fetched", ""))
    body = ('<div class="lu">' + hero + swap
            + f'<div class="lu-list" aria-label="Starting lineup">{lineup}</div>'
            + (f'<div class="lu-watch"><span class="fs-tag">Watch before kickoff</span><ul>{"".join(piv)}</ul></div>' if piv else "")
            + (f'<div class="lu-close"><span class="fs-tag">Close calls</span>' + "".join(
                f'<p><b>{esc(r["n"])}</b> over <b>{esc(b["n"])}</b>: {f1(r["mu"])} vs {f1(b["mu"])}, {esc(_last(b["n"]))} wins it {p * 100:.0f}% of the time.</p>' for b, r, p in close[:3]) + '</div>' if close else "")
            + f'<details class="lu-fold" open><summary>Bench · {len(bench)}</summary><div class="lu-list">{"".join(brows)}</div></details>'
            + (f'<details class="lu-fold"><summary>On the wire · would start for you</summary><div class="lu-list">{fa_html}</div>'
               + (f'<p class="note-s">You\'re {wr} of 12 on waivers. Gains are projected points over the starter he\'d replace this week.</p>' if wr else "") + '</details>' if fa_html else "")
            + oppfold + how
            + f'<p class="note-s lu-upd">Week {N} · data as of {upd} UTC · only shown on your signed-in phone</p></div>')
    return (f'<section class="sec" id="ps-lineup"><div class="sec-head"><h2>Optimal Lineup</h2>'
            f'<span class="kicker">Week {N} · your team only</span></div>{body}</section>')


# Shown only on a device signed in as the owner team (Rule Changes sign-in, localStorage "fz-team").
GATE = r"""<script>
(function(){
  var OWN=%d;
  function chk(){var m=null;try{m=JSON.parse(localStorage.getItem('fz-team')||'null')}catch(e){}
    var on=!!(m&&m.key&&+m.team===OWN);document.documentElement.classList.toggle('fz-owner',on);
    if(!on){var p=document.getElementById('ps-lineup');if(p&&!p.hidden){var g=p.closest('.cmb'),b=g&&g.querySelector('.cmb-sw button');if(b)b.click()}}}
  chk();document.addEventListener('visibilitychange',function(){if(!document.hidden)chk()});window.addEventListener('storage',chk);
})();
</script>"""

CSS = r"""
html:not(.fz-owner) #ps-lineup,html:not(.fz-owner) .cmb-sw button[data-k="ps-lineup"]{display:none!important}
.lu{display:grid;gap:12px;min-width:0}
.lu-hero{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:12px;padding:14px;background:var(--honolulu);color:#fff;border:3px solid var(--rule)}
.lu-team{display:flex;align-items:center;gap:10px}.lu-them{justify-content:flex-end;text-align:right}
.lu-team small{display:block;font-family:var(--mono);font-size:.62rem;letter-spacing:.08em;text-transform:uppercase;opacity:.85}
.lu-team b{font-family:var(--display);font-size:2.2rem;line-height:1}
.lu-meter{display:grid;justify-items:center;gap:4px;min-width:130px}
.lu-meter .kicker{color:#fff;opacity:.85}.lu-meter>b{font-family:var(--display);font-size:2.6rem;line-height:1;color:var(--hi)}
.lu-track{display:block;width:100%;height:8px;background:rgba(255,255,255,.3);border-radius:4px;overflow:hidden}.lu-track i{display:block;height:100%;background:var(--hi)}
.lu-meter small{font-family:var(--mono);font-size:.62rem;opacity:.9}
.lu-note{margin:0;padding:10px 12px;border-left:4px solid var(--hi);background:var(--sheet);font-size:.9rem}
.lu-list{display:grid;gap:0;border:2px solid var(--rule);background:var(--sheet)}
.lu-r{border-bottom:1px solid var(--line)}.lu-r:last-child{border-bottom:0}
.lu-r>summary{list-style:none;display:grid;grid-template-columns:44px minmax(0,1.4fr) minmax(70px,1fr) 52px;align-items:center;gap:10px;padding:9px 10px;cursor:pointer}
.lu-r>summary::-webkit-details-marker{display:none}
.lu-r[open]>summary{background:var(--paper)}
.lu-slot{font-family:var(--mono);font-weight:700;font-size:.68rem;text-align:center;padding:4px 0;border-radius:3px;background:var(--rule);color:var(--sheet)}
.lu-slot.s-QB{background:#b3261e;color:#fff}.lu-slot.s-RB{background:var(--honolulu);color:#fff}.lu-slot.s-WR{background:var(--blue);color:#fff}
.lu-slot.s-TE{background:#c47a12;color:#fff}.lu-slot.s-FLEX{background:var(--hi);color:var(--hi-ink)}.lu-slot.s-DST,.lu-slot.s-K{background:var(--silver);color:var(--silver-ink)}
.lu-slot.s-BN{background:transparent;color:var(--muted);box-shadow:inset 0 0 0 1.5px var(--line)}
.lu-who{min-width:0}.lu-who b{display:block;font-size:.95rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lu-who small{display:block;font-family:var(--mono);font-size:.64rem;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lu-bar{position:relative;height:10px;background:var(--heat0);border-radius:5px}
.lu-rg{position:absolute;top:0;bottom:0;background:var(--honolulu-2);border-radius:5px}
.lu-mu{position:absolute;top:-3px;width:4px;height:16px;margin-left:-2px;background:var(--rule);border-radius:2px}
.lu-pts{font-family:var(--display);font-size:1.5rem;text-align:right;line-height:1}
.lu-off .lu-who b,.lu-off .lu-pts{color:var(--muted)}.lu-off .lu-who b{text-decoration:line-through}
.lu-x{display:grid;grid-template-columns:repeat(auto-fill,minmax(118px,1fr));gap:6px;padding:4px 10px 12px}
.lu-b{display:grid;gap:1px;padding:7px 8px;background:var(--paper);border-radius:3px;min-width:0}
.lu-b span{font-family:var(--mono);font-size:.58rem;letter-spacing:.05em;text-transform:uppercase;color:var(--muted)}
.lu-b b{font-size:1rem}.lu-b small{font-family:var(--mono);font-size:.6rem;color:var(--muted)}
.lu-watch,.lu-close{padding:10px 12px;border:2px solid var(--rule);background:var(--sheet)}
.lu-watch ul{margin:6px 0 0;padding-left:18px;display:grid;gap:4px;font-size:.9rem}.lu-close p{margin:6px 0 0;font-size:.9rem}
.lu-watch{border-color:var(--red)}
.lu-fold>summary{cursor:pointer;font-family:var(--mono);font-size:.72rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;padding:8px 0}
.lu-fa{display:grid;grid-template-columns:44px minmax(0,1fr) 56px;align-items:center;gap:10px;padding:9px 10px;border-bottom:1px solid var(--line)}
.lu-fa:last-child{border-bottom:0}.lu-gain{font-family:var(--display);font-size:1.3rem;text-align:right;color:var(--blue)}
.lu-upd{margin:0}
@media (max-width:760px),(hover:none) and (pointer:coarse) and (max-width:1100px){
  .lu-hero{grid-template-columns:1fr 1fr;padding:12px}.lu-meter{grid-column:1/-1;order:3;min-width:0}
  .lu-team b{font-size:1.8rem}
  .lu-r>summary{grid-template-columns:40px minmax(0,1fr) 46px;gap:8px;padding:9px 8px}
  .lu-r>summary .lu-bar{grid-column:2/4;grid-row:2;height:7px}
  .lu-x{grid-template-columns:repeat(2,minmax(0,1fr));padding:4px 8px 10px}
  .lu-fa{grid-template-columns:40px minmax(0,1fr) 48px;padding:9px 8px}
  .lu-who small{white-space:normal}
}
"""
