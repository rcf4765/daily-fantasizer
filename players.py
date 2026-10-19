"""The Daily Fantasizer: Player Stats tab (PPR).

build(short_names) -> HTML for the Player Stats tab pane, from data/players/*.json (fetch_players.py).
Used by render.py for the weekly edition; `python3 players.py --patch FILE...` swaps a fresh pane into
already-built pages (between <!--PS--> and <!--/PS-->) for the midweek refresh.

Sources stay in the background: the page shows one blended number, not who said what.
"""
import html, json, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data", "players")
POS = ["QB", "RB", "WR", "TE"]
TOP = {"QB": 16, "RB": 30, "WR": 36, "TE": 16}
esc = html.escape
TEAMFIX = {"LA": "LAR", "WAS": "WSH", "JAC": "JAX", "LVR": "LV", "SFO": "SF", "KCC": "KC", "GBP": "GB", "NOS": "NO", "TBB": "TB", "NEP": "NE"}


def norm(n):
    n = n.lower().replace("’", "'")
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", n)
    return re.sub(r"[^a-z]", "", n)


def load(name, default=None):
    p = os.path.join(D, name)
    return json.load(open(p)) if os.path.exists(p) else default


def f1(x): return "–" if x is None else f"{x:.1f}"
def pct(x): return "–" if x is None else f"{x * 100:.0f}%"


def lg(t, size="lg-sm"): return f'<i class="lg lg-{t} {size}" aria-hidden="true"></i>'


class Data:
    def __init__(self, short):
        self.short = {int(k): v for k, v in short.items()}
        self.meta = load("meta.json", {})
        self.P = load("espn_players.json", [])
        self.U = load("usage.json", [])
        self.ros = load("fp_ros.json", {"players": []})
        self.lean = load("fp_lean.json", {"pos": {}})
        self.final = sorted(self.meta.get("final_weeks", []))
        self.live = self.meta.get("espn_week")  # week on the field (may be partly played)
        # next week = the first week not yet final; jump past the live week once its
        # successor's consensus ranks are out (FantasyPros posts them Monday/Tuesday)
        self.next = (max(self.final) + 1) if self.final else 1
        up = self.meta.get("upcoming")
        if up and up > self.next and load(f"fp_week{up}.json"):
            self.next = up
        self.fp = {w: load(f"fp_week{w}.json") for w in range(1, self.next + 1)}
        self.by = {}
        for p in self.P:
            p["key"] = norm(p["name"]) + "|" + p["pos"]
            p["act"] = {int(k): v for k, v in p["act"].items()}
            p["proj"] = {int(k): v for k, v in p["proj"].items()}
            self.by[p["key"]] = p
        # usage (snap %, target share, air-yard share) keyed the same way; team breaks name ties
        self.use = {}
        for u in self.U:
            k = norm(u["name"]) + "|" + u["pos"]
            if k in self.use and self.by.get(k) and self.by[k]["team"] != TEAMFIX.get(u["team"], u["team"]):
                continue
            self.use[k] = {int(w): v for w, v in u["wk"].items()}
        # consensus ranks per week: key -> {week: row}
        self.ecr = {}
        for w, f in self.fp.items():
            if not f:
                continue
            for pos, rows in f["pos"].items():
                for r in rows:
                    self.ecr.setdefault(norm(r["player_name"]) + "|" + pos, {})[w] = r
        self.ros_by = {norm(r["player_name"]) + "|" + r["player_position_id"]: r for r in self.ros["players"] if r["player_position_id"] in POS}
        self.lean_by = {}
        for pos, rows in self.lean.get("pos", {}).items():
            for r in rows:
                self.lean_by[norm(r["name"]) + "|" + pos] = r
        self.weeks_played = sorted({w for p in self.P for w in p["act"]})
        self._season()

    def games(self, p):
        return [w for w in sorted(p["act"]) if w in self.weeks_played and (
            p["act"][w]["tgt"] or p["act"][w]["ru_att"] or p["act"][w]["pa_att"] or p["act"][w]["pts"])]

    def _season(self):
        for p in self.P:
            g = self.games(p); n = len(g); p["g"] = n
            a = lambda k, ws=g: sum(p["act"][w][k] for w in ws)
            u = self.use.get(p["key"], {})
            p["ppg"] = a("pts") / n if n else 0
            l3 = g[-3:]
            p["l3"] = a("pts", l3) / len(l3) if l3 else 0
            p["tgt_g"] = a("tgt") / n if n else 0
            p["car_g"] = a("ru_att") / n if n else 0
            p["rec_g"] = a("rec") / n if n else 0
            p["att_g"] = a("pa_att") / n if n else 0
            p["tch_g"] = p["car_g"] + p["rec_g"]
            vals = lambda k, ws=g: [u[w][k] for w in ws if w in u and u[w].get(k) is not None]
            m = lambda xs: sum(xs) / len(xs) if xs else None
            p["snap"] = m(vals("snap")); p["ts"] = m(vals("ts")); p["ays"] = m(vals("ays"))
            p["ts_l3"] = m(vals("ts", l3)); p["snap_l3"] = m(vals("snap", l3))
            p["ay_g"] = (sum(vals("ay")) / n) if n and vals("ay") else 0.0
        self._expected()

    def _expected(self):
        """Expected PPR per game from volume: least squares of PPR/g on targets/g, carries/g and
        air yards/g (receivers) or pass attempts/g and carries/g (QBs), fit per position on every
        player with 3+ games. Residual = actual - expected (positive = scoring above his volume)."""
        for pos in POS:
            ps = [p for p in self.P if p["pos"] == pos and p["g"] >= 3]
            if len(ps) < 8:
                for p in ps: p["xp"] = None
                continue
            feats = (lambda p: [1, p["att_g"], p["car_g"]]) if pos == "QB" else (lambda p: [1, p["tgt_g"], p["car_g"], p["ay_g"]])
            X = [feats(p) for p in ps]; y = [p["ppg"] for p in ps]
            beta = ols(X, y)
            for p in self.P:
                if p["pos"] == pos:
                    p["xp"] = sum(b * x for b, x in zip(beta, feats(p))) if p["g"] >= 3 else None
                    p["res"] = (p["ppg"] - p["xp"]) if p.get("xp") is not None else None

    def owner(self, p):
        o = p.get("owner") or 0
        if not o:
            return '<span class="own fa">FA</span>'
        return f'<span class="own" title="{esc(self.short.get(o, ""))}">{lg(o)}<em>{esc(self.short.get(o, ""))}</em></span>'

    def pname(self, p, sub=True):
        inj = p.get("inj", "ACTIVE")
        tag = f' <span class="inj">{esc(inj[0] if inj in ("QUESTIONABLE", "DOUBTFUL", "OUT") else "IR" if inj == "INJURY_RESERVE" else inj[:1])}</span>' if inj not in ("ACTIVE", "NORMAL", None) else ""
        s = f'<small>{esc(p["pos"])} · {esc(p["team"])}</small>' if sub else ""
        return f'<span class="pn"><b>{esc(p["name"])}{tag}</b>{s}</span>'


def ols(X, y):
    k = len(X[0])
    A = [[sum(r[i] * r[j] for r in X) + (1e-6 if i == j else 0) for j in range(k)] for i in range(k)]
    b = [sum(r[i] * t for r, t in zip(X, y)) for i in range(k)]
    for c in range(k):  # Gauss-Jordan
        piv = max(range(c, k), key=lambda r: abs(A[r][c])); A[c], A[piv] = A[piv], A[c]; b[c], b[piv] = b[piv], b[c]
        for r in range(k):
            if r != c and A[c][c]:
                f = A[r][c] / A[c][c]
                A[r] = [a - f * x for a, x in zip(A[r], A[c])]; b[r] -= f * b[c]
    return [b[i] / A[i][i] if A[i][i] else 0 for i in range(k)]


def postabs(name, panes, default="WR"):
    """Position switcher (radio-free: buttons + data-pos, handled by one small script)."""
    btns = "".join(f'<button type="button" class="pt" data-pos="{p}" aria-pressed="{str(p == default).lower()}">{p}</button>' for p in panes)
    body = "".join(f'<div class="pp" data-pos="{p}"{"" if p == default else " hidden"}>{h}</div>' for p, h in panes.items())
    return f'<div class="ps-group" data-group="{name}"><div class="pts" role="group" aria-label="Position">{btns}</div>{body}</div>'


def sec(id_, title, kicker, body):
    return f'<section class="sec" id="{id_}"><div class="sec-head"><h2>{title}</h2><span class="kicker">{kicker}</span></div>{body}</section>'


def build(short_names):
    d = Data(short_names)
    if not d.P:
        return ""
    played = d.weeks_played
    last = max(played) if played else 0
    live_note = (f"weeks 1–{last}" + ("" if last in d.final else f", week {last} through Sunday")) if last else ""
    out = []
    fpN0 = d.fp.get(d.next) or {}
    out.append(f'<section class="ps-hero" aria-label="Player stats"><span class="kicker">The PPR player desk</span><h2>Player <span>Stats</span></h2>'
               f'<div class="ps-sub"><span>Usage {esc(live_note)}</span><span>Week {d.next} rankings &amp; start/sit</span><span>Rest of season</span><span>Rankings vs. actuals</span></div>'
               f'<nav class="ps-jump" aria-label="Player stats sections">'
               + "".join(f'<a href="#{a}">{t}</a>' for a, t in [("ps-current", "Current data"), ("ps-volume", "Volume vs. scoring"), ("ps-proj", "Projections"), ("ps-startsit", "Start/sit"), ("ps-next", f"Week {d.next} ranks"), ("ps-ros", "Rest of season"), ("ps-variance", "Ranks vs. actuals")])
               + '</nav></section>')

    # ---------- 1. current data: usage board ----------
    panes = {}
    for pos in ["WR", "RB", "TE", "QB"]:
        ps = sorted([p for p in d.P if p["pos"] == pos and p["g"] >= 2], key=lambda p: -p["ppg"])[:TOP[pos]]
        if pos == "QB":
            head = '<th>#</th><th>Player</th><th>Owner</th><th class="n">G</th><th class="n">Pass att/g</th><th class="n">Carries/g</th><th class="n">Snap %</th><th class="n">PPR/g</th><th class="n">Last 3</th>'
            rows = "".join(f'<tr><td class="rk2">{i}</td><td>{d.pname(p)}</td><td>{d.owner(p)}</td><td class="n">{p["g"]}</td><td class="n">{f1(p["att_g"])}</td><td class="n">{f1(p["car_g"])}</td><td class="n">{pct(p["snap"])}</td><td class="n"><b>{f1(p["ppg"])}</b></td><td class="n">{trend(p)}</td></tr>' for i, p in enumerate(ps, 1))
        else:
            mx = max((p["ts"] or 0) for p in ps) or 1
            head = '<th>#</th><th>Player</th><th>Owner</th><th class="n">G</th><th class="n">Snap %</th><th>Target share</th><th class="n">Tgt/g</th><th class="n">Touches/g</th><th class="n">Air-yd share</th><th class="n">PPR/g</th><th class="n">Last 3</th>'
            rows = "".join(f'<tr><td class="rk2">{i}</td><td>{d.pname(p)}</td><td>{d.owner(p)}</td><td class="n">{p["g"]}</td><td class="n">{pct(p["snap"])}</td>'
                           f'<td><span class="tsb"><i style="width:{(p["ts"] or 0) / mx * 100:.0f}%"></i><em class="num">{pct(p["ts"])}</em></span></td>'
                           f'<td class="n">{f1(p["tgt_g"])}</td><td class="n">{f1(p["tch_g"])}</td><td class="n">{pct(p["ays"]) if pos != "RB" else "–"}</td><td class="n"><b>{f1(p["ppg"])}</b></td><td class="n">{trend(p)}</td></tr>' for i, p in enumerate(ps, 1))
        panes[pos] = f'<div class="tbl-wrap"><table class="pst"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>'
    out.append(sec("ps-current", "Current Data", f"PPR usage, {live_note}",
                   postabs("cur", panes) + '<p class="note-s">Ranked by PPR points per game played (2+ games). Snap % and shares are per-game averages. Last 3 = PPR per game over his last three games, arrow vs. season.</p>'))

    # ---------- 2. volume vs scoring ----------
    cand = [p for p in d.P if p["pos"] in ("RB", "WR", "TE") and p.get("xp") is not None and p["xp"] >= 6]
    cand.sort(key=lambda p: -p["xp"]); cand = cand[:70]
    if cand:
        hot = sorted(cand, key=lambda p: -p["res"])[:6]; cold = sorted(cand, key=lambda p: p["res"])[:6]
        lab = {p["key"] for p in hot[:4] + cold[:4]}
        lo = 0; hi = math.ceil(max(max(p["xp"], p["ppg"]) for p in cand) / 5) * 5
        X = lambda v: (v - lo) / (hi - lo) * 100; Y = lambda v: 100 - (v - lo) / (hi - lo) * 100
        dots = "".join(f'<span class="vd p-{p["pos"]}{" lab" if p["key"] in lab else ""}" style="left:{X(p["xp"]):.1f}%;top:{Y(p["ppg"]):.1f}%" title="{esc(p["name"])}: {p["ppg"]:.1f} PPR/g on volume worth {p["xp"]:.1f}">'
                       + (f'<em>{esc(short_name(p["name"]))}</em>' if p["key"] in lab else "") + '</span>' for p in cand)
        ticks = "".join(f'<span style="left:{X(v):.0f}%">{v}</span>' for v in range(0, hi + 1, 5))
        chart = (f'<div class="vs-wrap"><span class="sc-y">PPR points per game</span><div class="vs">'
                 f'<svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><line x1="0" y1="100" x2="100" y2="0" class="vs-eq"/></svg>'
                 f'<span class="q q2">Scoring above<br>his volume</span><span class="q q4">Volume not<br>cashing in yet</span>{dots}</div>'
                 f'<div class="vs-x">{ticks}</div><span class="sc-x"><span>Expected PPR/g from volume</span></span></div>'
                 '<div class="legend"><span><i class="sw p-RB"></i>RB</span><span><i class="sw p-WR"></i>WR</span><span><i class="sw p-TE"></i>TE</span><span><i class="sw vs-sw"></i>points = volume</span></div>')
        li = lambda ps, cls: "".join(f'<div class="rw-row">{d.owner(p)}{d.pname(p)}<span class="rw-v num {cls}">{p["res"]:+.1f}</span><span class="rw-s num">{p["ppg"]:.1f} vs {p["xp"]:.1f}</span></div>' for p in ps)
        lists = (f'<div class="rw"><h3>Running hot</h3><p class="note-s">Scoring more than his volume supports. Sell-high watch.</p>{li(hot, "up")}</div>'
                 f'<div class="rw"><h3>Running cold</h3><p class="note-s">Volume is there, points aren\'t yet. Buy-low watch.</p>{li(cold, "dn")}</div>')
        out.append(sec("ps-volume", "Volume vs. Scoring", "The regression watch",
                       f'<div class="vs-grid"><div>{chart}</div><div class="rw-col">{lists}</div></div>'
                       '<p class="note-s">Expected points come from a fit of PPR points per game on targets, carries and air yards per game across every player at the position with 3+ games. Dots: the 70 skill players with the most volume.</p>'))

    # ---------- 3/4/5. next week: projections, start/sit, rankings ----------
    N = d.next
    fpN = d.fp.get(N)
    has_fp = bool(fpN and fpN.get("pos"))
    early = has_fp and (fpN.get("experts") or 0) < 10
    rows_by_pos = {}
    for pos in POS:
        lst = []
        for p in d.P:
            if p["pos"] != pos:
                continue
            e = d.ecr.get(p["key"], {}).get(N) if has_fp else None
            vals = []
            if e and e.get("r2p_pts") not in (None, ""):
                vals.append(float(e["r2p_pts"]))
            if p["proj"].get(N):
                vals.append(p["proj"][N])
            if not vals:
                continue
            pr = sum(vals) / len(vals)
            lst.append({"p": p, "e": e, "proj": pr, "lo": min(vals), "hi": max(vals)})
        if has_fp:
            lst = [r for r in lst if r["e"]] + [r for r in lst if not r["e"]]
            lst.sort(key=lambda r: (r["e"]["rank_ecr"] if r["e"] else 9999, -r["proj"]))
        else:
            lst.sort(key=lambda r: -r["proj"])
        for i, r in enumerate(lst, 1):
            r["rank"] = i
        rows_by_pos[pos] = lst

    def opp(r):
        if r["e"] and r["e"].get("player_opponent"):
            return r["e"]["player_opponent"]
        return ""

    # 3. projections (top by projected points)
    panes = {}
    for pos in ["WR", "RB", "TE", "QB"]:
        lst = sorted(rows_by_pos[pos], key=lambda r: -r["proj"])[:TOP[pos]]
        if not lst:
            panes[pos] = '<p class="note-s">Projections post early in the week.</p>'; continue
        mx = max(r["hi"] for r in lst) or 1
        panes[pos] = '<div class="pj">' + "".join(
            f'<div class="pj-row"><span class="rk2">{i}</span>{d.pname(r["p"])}{d.owner(r["p"])}<span class="pj-opp num">{esc(opp(r))}</span>'
            f'<span class="pj-t"><i class="pj-rng" style="left:{r["lo"] / mx * 100:.1f}%;width:{max(0.6, (r["hi"] - r["lo"]) / mx * 100):.1f}%"></i><i class="pj-dot" style="left:{r["proj"] / mx * 100:.1f}%"></i></span>'
            f'<b class="num">{r["proj"]:.1f}</b></div>' for i, r in enumerate(lst, 1)) + '</div>'
    out.append(sec("ps-proj", f"Week {N} Projections", "PPR points, blended",
                   postabs("proj", panes) + '<div class="legend"><span><i class="sw pj-sw-d"></i>Blended projection</span><span><i class="sw pj-sw-r"></i>Range across projections</span></div>'
                   + ("" if has_fp and not early else f'<p class="note-s">Early numbers. Most of the consensus for week {N} lands Tuesday to Thursday; this tab refreshes as it does.</p>')))

    # 4. start / sit assist (interactive)
    cands = []
    for pos in POS:
        for r in rows_by_pos[pos][:{"QB": 32, "RB": 70, "WR": 90, "TE": 36}[pos]]:
            p = r["p"]; e = r["e"] or {}
            ln = d.lean_by.get(p["key"]) if d.lean.get("week") == N else None
            cands.append({"k": p["key"], "n": p["name"], "pos": pos, "tm": p["team"], "o": p.get("owner") or 0,
                          "pr": round(r["proj"], 1), "lo": round(r["lo"], 1), "hi": round(r["hi"], 1),
                          "rk": e.get("pos_rank") or f"{pos}{r['rank']}", "rmin": e.get("rank_min"), "rmax": e.get("rank_max"),
                          "gr": e.get("start_sit_grade"), "opp": opp(r), "ppg": round(p["ppg"], 1), "l3": round(p["l3"], 1),
                          "ts": None if p["ts_l3"] is None else round(p["ts_l3"] * 100), "sn": None if p["snap_l3"] is None else round(p["snap_l3"] * 100),
                          "inj": p.get("inj", "ACTIVE"),
                          "ln": (1 if ln and ln["analyst"] < ln["ecr"] else -1 if ln else 0)})
    cands.sort(key=lambda c: (c["o"] == 0, c["o"], -c["pr"]))
    own = int(d.meta.get("owner_team") or 1)
    mine = [c for c in cands if c["o"] == own and c["pos"] in ("RB", "WR", "TE")]
    mine.sort(key=lambda c: -c["pr"])
    pair = None
    if len(mine) >= 2:  # the closest call among his likely FLEX options (projected 3rd-6th best skill players)
        pool = mine[2:7] if len(mine) > 3 else mine
        best = min(((a, b) for i, a in enumerate(pool) for b in pool[i + 1:]), key=lambda ab: abs(ab[0]["pr"] - ab[1]["pr"]), default=None)
        pair = best
    ss = {"teams": {str(k): v for k, v in d.short.items()}, "c": cands, "def": [pair[0]["k"], pair[1]["k"]] if pair else [], "wk": N}
    out.append(sec("ps-startsit", "Start / Sit Assist", f"Week {N} · pick two",
                   f'<div class="ssa" id="ssa"><div class="ss-pick"><label><span class="kicker">Player A</span><select id="ss-a"></select></label>'
                   f'<span class="ss-vs">vs.</span><label><span class="kicker">Player B</span><select id="ss-b"></select></label></div>'
                   f'<div class="ss-out" id="ss-out" aria-live="polite"></div></div>'
                   f'<script type="application/json" id="ss-data">{json.dumps(ss, separators=(",", ":")).replace("</", "<\\/")}</script>'
                   '<p class="note-s">The call weighs the blended projection first, then the floor (low end of the projections), recent target share and snaps. Grades and rank ranges come from the consensus. "Contrarian lean" means a tracked analyst ranks him well away from consensus this week.</p>'))

    # 5. next week rankings
    panes = {}
    for pos in ["WR", "RB", "TE", "QB"]:
        lst = rows_by_pos[pos][:TOP[pos]]
        rows = "".join(
            f'<tr{" class=\"avail\"" if not (r["p"].get("owner") or 0) else ""}><td class="rk2">{r["rank"]}</td><td>{d.pname(r["p"])}</td><td>{d.owner(r["p"])}</td><td class="num">{esc(opp(r))}</td>'
            f'<td class="n">{(r["e"] or {}).get("rank_min") or "–"}–{(r["e"] or {}).get("rank_max") or "–"}</td><td class="n">{grade((r["e"] or {}).get("start_sit_grade"))}</td><td class="n"><b>{r["proj"]:.1f}</b></td></tr>'
            for r in lst)
        panes[pos] = (f'<div class="tbl-wrap"><table class="pst"><thead><tr><th>#</th><th>Player</th><th>Owner</th><th>Opp</th><th class="n">Rank range</th><th class="n">Grade</th><th class="n">Proj</th></tr></thead><tbody>{rows}</tbody></table></div>'
                      if lst else '<p class="note-s">Rankings post early in the week.</p>')
    out.append(sec("ps-next", f"Week {N} Rankings", "Consensus, PPR · yellow = free agent in our league",
                   postabs("next", panes) + ("" if has_fp else f'<p class="note-s">Consensus week {N} ranks aren\'t posted yet; until they are, this list is ordered by projection.</p>')))

    # 6. rest of season
    panes = {}; fa_best = []
    for pos in ["WR", "RB", "TE", "QB"]:
        rs = [r for r in d.ros["players"] if r["player_position_id"] == pos]
        rs.sort(key=lambda r: r["rank_ecr"])
        rows = []
        for i, r in enumerate(rs[:TOP[pos]], 1):
            p = d.by.get(norm(r["player_name"]) + "|" + pos)
            if p is None:
                continue
            mv = r.get("player_ecr_delta")
            mvh = f'<span class="mv {"up" if mv and mv > 0 else "dn" if mv and mv < 0 else "eq"}">{("▲" + str(mv)) if mv and mv > 0 else ("▼" + str(-mv)) if mv and mv < 0 else "–"}</span>'
            rows.append(f'<tr{" class=\"avail\"" if not p.get("owner") else ""}><td class="rk2">{i}</td><td>{d.pname(p)}</td><td>{d.owner(p)}</td><td class="n">{r.get("pos_rank", "")}</td><td class="n">{r.get("rank_ecr")}</td><td>{mvh}</td><td class="n">{f1(p["ppg"])}</td><td class="n">{f1(p.get("xp"))}</td></tr>')
        for r in rs:
            p = d.by.get(norm(r["player_name"]) + "|" + pos)
            if p is not None and not p.get("owner") and r["rank_ecr"] <= 160:
                fa_best.append((r["rank_ecr"], p, r))
        panes[pos] = f'<div class="tbl-wrap"><table class="pst"><thead><tr><th>#</th><th>Player</th><th>Owner</th><th class="n">Pos rank</th><th class="n">Overall</th><th>Move</th><th class="n">PPR/g</th><th class="n">Expected</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    fa_best.sort(key=lambda x: x[0])
    fa_html = "".join(f'<div class="fa-c"><span class="kicker">{esc(r["pos_rank"] or p["pos"])} · overall {r["rank_ecr"]}</span><b>{esc(p["name"])}</b><small>{esc(p["team"])} · {f1(p["ppg"])} PPR/g</small></div>' for _, p, r in fa_best[:6])
    out.append(sec("ps-ros", "Rest-of-Season Rankings", f"Consensus, PPR · updated {esc(str(d.ros.get('updated') or ''))}",
                   (f'<div class="fa-best"><span class="fs-tag">On our wire</span>{fa_html}</div>' if fa_html else "")
                   + postabs("ros", panes)
                   + '<p class="note-s">Move = change in consensus overall rank since last week. Expected = PPR/g his volume supports (see Volume vs. Scoring). Yellow rows are free agents in our league.</p>'))

    # ---------- 7. rankings vs actuals ----------
    graded = [w for w in d.final if d.fp.get(w)]
    if graded:
        finish = {}  # (week, pos) -> {key: finish rank}
        for w in graded:
            for pos in POS:
                ps = sorted([p for p in d.P if p["pos"] == pos and w in p["act"]], key=lambda p: -p["act"][w]["pts"])
                finish[(w, pos)] = {p["key"]: i for i, p in enumerate(ps, 1)}
        recs = []  # one per ranked player-week (top-36 ranked RB/WR, top-18 QB/TE)
        cut = {"QB": 18, "RB": 36, "WR": 36, "TE": 18}
        for w in graded:
            for pos in POS:
                for r in d.fp[w]["pos"].get(pos, []):
                    pr = int(re.sub(r"\D", "", r.get("pos_rank") or "") or 0)
                    if not pr or pr > cut[pos]:
                        continue
                    k = norm(r["player_name"]) + "|" + pos
                    p = d.by.get(k)
                    if p is None or w not in p["act"]:
                        continue
                    fin = finish[(w, pos)].get(k)
                    proj = float(r["r2p_pts"]) if r.get("r2p_pts") not in (None, "") else None
                    recs.append({"w": w, "pos": pos, "p": p, "rk": pr, "fin": fin, "var": pr - fin,
                                 "proj": proj, "pts": p["act"][w]["pts"]})
        lw = max(graded)
        L = [x for x in recs if x["w"] == lw]
        beats = sorted(L, key=lambda x: -(x["pts"] - (x["proj"] or 0)))[:6]
        busts = sorted(L, key=lambda x: (x["pts"] - (x["proj"] or 0)))[:6]
        # accuracy: median absolute rank miss and projection miss by position, last week and season
        def mae(xs, f): xs = [abs(f(x)) for x in xs if f(x) is not None]; return sum(xs) / len(xs) if xs else None
        tiles = "".join(f'<div class="rs"><span>{pos} ranks</span><b class="num">{f1(mae([x for x in recs if x["pos"] == pos], lambda x: x["var"]))}</b>'
                        f'<small>spots off on average · wk {lw}: {f1(mae([x for x in L if x["pos"] == pos], lambda x: x["var"]))}</small></div>' for pos in POS)
        pv = mae(recs, lambda x: (x["pts"] - x["proj"]) if x["proj"] is not None else None)
        tiles += f'<div class="rs hot"><span>Projection miss</span><b class="num">{f1(pv)}</b><small>PPR points per player-week</small></div>'
        card = lambda x, cls: (f'<div class="bv-row">{d.owner(x["p"])}{d.pname(x["p"])}<span class="bv-r num">{x["pos"]}{x["rk"]} → {x["pos"]}{x["fin"]}</span>'
                               f'<span class="bv-p num">{x["pts"]:.1f} <em>proj {f1(x["proj"])}</em></span><span class="bv-v num {cls}">{x["pts"] - (x["proj"] or 0):+.1f}</span></div>')
        bv = (f'<div class="bv"><div><h3>Week {lw}: beat the ranking</h3>{"".join(card(x, "up") for x in beats)}</div>'
              f'<div><h3>Week {lw}: missed the ranking</h3>{"".join(card(x, "dn") for x in busts)}</div></div>')
        # season: who the rankings get wrong
        agg = {}
        for x in recs:
            a = agg.setdefault(x["p"]["key"], {"p": x["p"], "n": 0, "v": 0, "rk": 0, "fin": 0, "pd": 0, "pn": 0})
            a["n"] += 1; a["v"] += x["var"]; a["rk"] += x["rk"]; a["fin"] += x["fin"]
            if x["proj"] is not None:
                a["pd"] += x["pts"] - x["proj"]; a["pn"] += 1
        A = [a for a in agg.values() if a["n"] >= 3]
        for a in A:
            a["av"] = a["v"] / a["n"]; a["apd"] = a["pd"] / a["pn"] if a["pn"] else 0
        under = sorted(A, key=lambda a: -a["apd"])[:8]; over = sorted(A, key=lambda a: a["apd"])[:8]
        trow = lambda a: (f'<tr><td>{d.pname(a["p"])}</td><td>{d.owner(a["p"])}</td><td class="n">{a["n"]}</td><td class="n">{a["p"]["pos"]}{a["rk"] / a["n"]:.0f}</td>'
                          f'<td class="n">{a["p"]["pos"]}{a["fin"] / a["n"]:.0f}</td><td class="n"><b class="{"up" if a["apd"] > 0 else "dn"}">{a["apd"]:+.1f}</b></td></tr>')
        th = '<thead><tr><th>Player</th><th>Owner</th><th class="n">Wks</th><th class="n">Avg rank</th><th class="n">Avg finish</th><th class="n">Pts vs proj</th></tr></thead>'
        season = (f'<div class="twocol2"><div><h3>Underrated all season</h3><div class="tbl-wrap"><table class="pst sm">{th}<tbody>{"".join(trow(a) for a in under)}</tbody></table></div></div>'
                  f'<div><h3>Overrated all season</h3><div class="tbl-wrap"><table class="pst sm">{th}<tbody>{"".join(trow(a) for a in over)}</tbody></table></div></div></div>')
        out.append(sec("ps-variance", "Rankings vs. Actuals", f"Weeks {min(graded)}–{lw} graded",
                       f'<div class="rum-stats rs5">{tiles}</div>{bv}{season}'
                       f'<p class="note-s">Every week\'s consensus PPR ranks (top 36 RB/WR, top 18 QB/TE) graded against where each player actually finished at his position. Variance = actual points minus projected points; rank arrows read ranked → finished.</p>'))

    out.append(f'<p class="note-s ps-foot">Updated {esc(d.meta.get("fetched", ""))} UTC. Blends public consensus rankings and projections with ESPN data; usage from play-by-play charting.</p>')
    out.append(SCRIPT)
    return "<!--PS-->\n" + "\n".join(out) + "\n<!--/PS-->"


def trend(p):
    if not p["g"]:
        return "–"
    d_ = p["l3"] - p["ppg"]
    cls = "up" if d_ > 1 else "dn" if d_ < -1 else "eq"
    arrow = "▲" if cls == "up" else "▼" if cls == "dn" else "•"
    return f'<span class="tr {cls}">{p["l3"]:.1f} {arrow}</span>'


def grade(g):
    if not g:
        return "–"
    c = "ga" if g[0] == "A" else "gb" if g[0] == "B" else "gc" if g[0] == "C" else "gd"
    return f'<span class="gr {c}">{esc(g)}</span>'


def short_name(n):
    parts = n.replace(" Jr.", "").replace(" Sr.", "").replace(" III", "").replace(" II", "").split(" ")
    return f"{parts[0][0]}. {parts[-1]}" if len(parts) > 1 else n


SCRIPT = r"""<script>
(function(){
  document.querySelectorAll('.ps-group').forEach(function(g){
    var b=g.querySelectorAll('.pt'),p=g.querySelectorAll('.pp');
    b.forEach(function(x){x.addEventListener('click',function(){
      b.forEach(function(y){y.setAttribute('aria-pressed',y===x?'true':'false')});
      p.forEach(function(q){q.hidden=q.dataset.pos!==x.dataset.pos});
    })});
  });
  var el=document.getElementById('ss-data'); if(!el)return;
  var D=JSON.parse(el.textContent),C=D.c,T=D.teams,byk={};C.forEach(function(c){byk[c.k]=c});
  var A=document.getElementById('ss-a'),B=document.getElementById('ss-b'),O=document.getElementById('ss-out');
  function opts(sel){
    var groups={};C.forEach(function(c){var g=c.o?T[c.o]:'Free agents';(groups[g]=groups[g]||[]).push(c)});
    Object.keys(groups).forEach(function(g){
      var og=document.createElement('optgroup');og.label=g;
      groups[g].forEach(function(c){var o=document.createElement('option');o.value=c.k;o.textContent=c.n+' ('+c.pos+', '+c.tm+')';og.appendChild(o)});
      sel.appendChild(og);
    });
  }
  opts(A);opts(B);
  if(D.def.length===2){A.value=D.def[0];B.value=D.def[1]}else if(C.length>1){A.value=C[0].k;B.value=C[1].k}
  function e(s){return String(s==null?'':s).replace(/[&<>"]/g,function(m){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]})}
  function score(c){var s=c.pr+0.35*c.lo+(c.ts?c.ts*0.04:0)+(c.sn?c.sn*0.01:0);if(c.inj==='OUT'||c.inj==='INJURY_RESERVE')s-=100;if(c.inj==='DOUBTFUL')s-=8;if(c.inj==='QUESTIONABLE')s-=1.5;return s}
  function card(c,win){
    var inj=(c.inj&&c.inj!=='ACTIVE'&&c.inj!=='NORMAL')?'<span class="inj">'+e(c.inj.replace('_',' ').toLowerCase())+'</span>':'';
    var ln=c.ln>0?'<span class="flag">Contrarian lean: higher</span>':c.ln<0?'<span class="flag dn">Contrarian lean: lower</span>':'';
    return '<div class="ss-card'+(win?' win':'')+'"><div class="ss-top">'+(win?'<span class="fs-tag">Start</span>':'<span class="ss-sit">Sit</span>')+(c.o?'<i class="lg lg-'+c.o+' lg-sm"></i>':'<span class="own fa">FA</span>')+'</div>'+
      '<h3>'+e(c.n)+'</h3><span class="kicker">'+e(c.pos)+' · '+e(c.tm)+(c.opp?' · '+e(c.opp):'')+'</span>'+inj+
      '<div class="ss-big"><b class="num">'+c.pr.toFixed(1)+'</b><span>projected PPR<br><em class="num">range '+c.lo.toFixed(1)+'–'+c.hi.toFixed(1)+'</em></span></div>'+
      '<div class="ss-stats"><span><em>Rank</em><b class="num">'+e(c.rk)+'</b></span><span><em>Rank range</em><b class="num">'+(c.rmin?e(c.rmin)+'–'+e(c.rmax):'–')+'</b></span><span><em>Grade</em><b class="num">'+e(c.gr||'–')+'</b></span>'+
      '<span><em>PPR/g</em><b class="num">'+c.ppg.toFixed(1)+'</b></span><span><em>Last 3</em><b class="num">'+c.l3.toFixed(1)+'</b></span><span><em>Tgt share L3</em><b class="num">'+(c.ts==null?'–':c.ts+'%')+'</b></span></div>'+ln+'</div>';
  }
  function go(){
    var a=byk[A.value],b=byk[B.value];if(!a||!b){O.innerHTML='';return}
    if(a.k===b.k){O.innerHTML='<p class="note-s">Pick two different players.</p>';return}
    var sa=score(a),sb=score(b),w=sa>=sb?a:b,l=w===a?b:a,gap=Math.abs(sa-sb);
    var why=gap<1?'Coin flip. Go with the higher floor: '+e(w.n)+'.':gap<3?'Lean '+e(w.n)+'.':'Clear call: start '+e(w.n)+'.';
    O.innerHTML='<p class="ss-verdict">'+why+'</p><div class="ss-cards">'+card(a,w===a)+card(b,w===b)+'</div>';
  }
  A.addEventListener('change',go);B.addEventListener('change',go);go();
})();
</script>"""

CSS = r"""
/* player stats */
.ps-hero{display:grid;gap:12px;padding:24px 22px 18px;background:radial-gradient(var(--dot) 1.4px,transparent 1.6px) 0 0/9px 9px,var(--paper);border:3px solid var(--rule);border-top:10px solid var(--honolulu)}
.ps-hero h2{font-size:clamp(2.8rem,9vw,5.6rem);font-weight:900;text-transform:uppercase}
.ps-hero h2 span{color:var(--blue)}
.ps-hero .kicker{color:var(--ink)}
.ps-sub{display:flex;flex-wrap:wrap;gap:6px 22px;font-family:var(--mono);font-size:.78rem}
.ps-jump{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}
.ps-jump a{font-family:var(--mono);font-size:.7rem;letter-spacing:.06em;text-transform:uppercase;color:var(--ink);text-decoration:none;border:1.5px solid var(--rule);padding:3px 8px;background:var(--sheet)}
.ps-jump a:hover{background:var(--ink);color:var(--sheet)}
.pts{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:10px}
.pt{appearance:none;font-family:var(--mono);font-size:.74rem;font-weight:600;letter-spacing:.08em;padding:5px 12px;border:2px solid var(--rule);background:var(--sheet);color:var(--ink);cursor:pointer}
.pt[aria-pressed="true"]{background:var(--ink);color:var(--sheet)}
.pt:focus-visible{outline:3px solid var(--hi);outline-offset:1px}
.pp[hidden]{display:none}
.ps-group,.pp{min-width:0;display:grid}
.pp[hidden]{display:none}
table.pst{min-width:680px}
table.pst.sm{min-width:520px}
td.rk2,.rk2{font-family:var(--display);font-weight:900;font-size:1.25rem;line-height:1;width:2.2ch}
.pn{display:grid;line-height:1.2;min-width:0}
.pn b{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pn small{font-family:var(--mono);font-size:.62rem;color:var(--muted);letter-spacing:.04em}
.inj{font-family:var(--mono);font-size:.6rem;font-weight:600;color:#fff;background:var(--red);padding:0 4px;border-radius:2px;vertical-align:.12em;text-transform:uppercase}
.own{display:inline-flex;align-items:center;gap:5px;font-size:.78rem;white-space:nowrap}
.own .lg{width:20px;height:20px}
.own em{font-style:normal;color:var(--muted)}
.own.fa{font-family:var(--mono);font-size:.62rem;font-weight:600;letter-spacing:.06em;background:var(--hi);color:var(--hi-ink);padding:1px 6px}
tr.avail{background:color-mix(in srgb,var(--hi) 22%,transparent)}
.tsb{display:grid;grid-template-columns:70px auto;align-items:center;gap:6px}
.tsb i{display:block;height:8px;background:var(--honolulu);border-radius:0 3px 3px 0}
.tsb em{font-style:normal;font-size:.8rem}
.tr{font-family:var(--mono);font-size:.8rem;white-space:nowrap}
.tr.up,b.up,.up{color:var(--honolulu)}.tr.dn,b.dn,.dn{color:var(--red)}.tr.eq{color:var(--muted)}
/* volume vs scoring */
.vs-grid{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:28px;align-items:start}
.vs-wrap{display:grid;grid-template-columns:22px minmax(0,1fr);gap:4px}
.vs-wrap .sc-y{grid-row:1}
.vs{grid-column:2;position:relative;aspect-ratio:1.1;border-left:2px solid var(--rule);border-bottom:2px solid var(--rule);background:linear-gradient(var(--line) 1px,transparent 1px) 0 0/100% 20%,linear-gradient(90deg,var(--line) 1px,transparent 1px) 0 0/20% 100%}
.vs svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible}
.vs-eq{stroke:var(--muted);stroke-width:1.5;stroke-dasharray:4 4;vector-effect:non-scaling-stroke}
.vs-x{grid-column:2;position:relative;height:16px;font-family:var(--mono);font-size:.64rem;color:var(--muted)}
.vs-x span{position:absolute;transform:translateX(-50%)}
.vs-wrap .sc-x{grid-column:2}
.vd{position:absolute;width:10px;height:10px;border-radius:50%;transform:translate(-50%,-50%);border:1.5px solid var(--sheet);z-index:1}
.vd.lab{width:13px;height:13px;border-color:var(--ink);z-index:2}
.vd em{position:absolute;left:12px;top:-4px;font-style:normal;font-size:.66rem;font-weight:600;white-space:nowrap;background:var(--sheet);padding:0 3px;line-height:1.3}
.p-RB{background:var(--honolulu)}.p-WR{background:var(--blue)}.p-TE{background:var(--hi)}
.sw.p-RB,.sw.p-WR,.sw.p-TE{width:10px;height:10px;border-radius:50%}
.sw.vs-sw{height:0;border-top:2px dashed var(--muted);border-radius:0}
.rw-col{display:grid;gap:22px}
.rw{display:grid;gap:6px}
.rw h3,.bv h3,.twocol2 h3{font-size:1.45rem;font-weight:800;text-transform:uppercase}
.rw-row,.bv-row{display:grid;grid-template-columns:auto minmax(0,1fr) auto auto;gap:8px;align-items:center;padding:6px 0;border-bottom:1px solid var(--line)}
.rw-row .own em,.bv-row .own em{display:none}
.rw-v,.bv-v{font-weight:600;font-size:1rem;text-align:right;min-width:3.4em}
.rw-s{font-size:.72rem;color:var(--muted);text-align:right}
/* projections */
.pj{display:grid;gap:2px}
.pj-row{display:grid;grid-template-columns:2.6ch minmax(130px,1.2fr) minmax(90px,.8fr) 64px minmax(0,2fr) 44px;gap:10px;align-items:center;padding:5px 0;border-bottom:1px solid var(--line)}
.pj-opp{font-size:.74rem;color:var(--muted)}
.pj-t{position:relative;height:14px;background:var(--paper)}
.pj-rng{position:absolute;top:4px;height:6px;background:var(--silver);border-radius:3px}
.pj-dot{position:absolute;top:0;width:14px;height:14px;margin-left:-7px;border-radius:50%;background:var(--blue);border:2px solid var(--sheet)}
.pj-row>b{text-align:right}
.own{justify-self:start;width:max-content}
.pst.sm .own em{display:none}
.pst.sm .pn b{max-width:22ch}
.sw.pj-sw-d{width:10px;height:10px;border-radius:50%;background:var(--blue)}.sw.pj-sw-r{background:var(--silver);height:6px}
/* start / sit */
.ssa{display:grid;gap:16px}
.ss-pick{display:flex;flex-wrap:wrap;align-items:end;gap:10px 16px}
.ss-pick label{display:grid;gap:4px;flex:1 1 240px;min-width:0}
.ss-pick select{font:inherit;font-size:.95rem;padding:8px 10px;border:2px solid var(--rule);background:var(--sheet);color:var(--ink);width:100%;min-width:0}
.ss-vs{font-family:var(--display);font-weight:900;font-size:1.6rem;padding-bottom:6px}
.ss-verdict{font-family:var(--display);font-weight:900;font-size:clamp(1.5rem,4vw,2.2rem);text-transform:uppercase;line-height:1}
.ss-cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:10px}
.ss-card{border:2px solid var(--rule);padding:14px;display:grid;gap:8px;align-content:start;background:var(--sheet)}
.ss-card.win{border-top:8px solid var(--blue)}
.ss-card:not(.win){border-top:8px solid var(--silver)}
.ss-card h3{font-size:1.7rem;font-weight:900;text-transform:uppercase}
.ss-top{display:flex;justify-content:space-between;align-items:center}
.ss-sit{font-family:var(--display);font-weight:900;font-size:.95rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);border:2px solid var(--silver);padding:1px 8px}
.ss-big{display:flex;align-items:center;gap:10px}
.ss-big b{font-size:2.6rem;line-height:1}
.ss-big span{font-family:var(--mono);font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.ss-big em{font-style:normal;text-transform:none;letter-spacing:0}
.ss-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;border-top:1px dashed var(--line);padding-top:8px}
.ss-stats span{display:grid}
.ss-stats em{font-style:normal;font-family:var(--mono);font-size:.6rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.ss-stats b{font-size:1rem}
.flag.dn{background:var(--silver);color:var(--silver-ink)}
.gr{font-family:var(--mono);font-weight:600;font-size:.78rem;padding:1px 6px;border-radius:2px}
.gr.ga{background:var(--blue);color:#fff}.gr.gb{background:var(--honolulu-2);color:#151a24}.gr.gc{background:var(--silver);color:#151a24}.gr.gd{background:var(--red);color:#fff}
/* ros */
.fa-best{display:flex;flex-wrap:wrap;gap:10px;align-items:stretch;padding:12px;border:2px dashed var(--rule);background:radial-gradient(var(--dot) 1.2px,transparent 1.4px) 0 0/8px 8px,var(--sheet)}
.fa-best .fs-tag{align-self:center}
.fa-c{display:grid;line-height:1.2;padding:4px 10px;border-left:4px solid var(--hi);min-width:150px}
.fa-c b{font-size:.95rem}.fa-c small{font-size:.74rem;color:var(--muted)}
/* variance */
.rum-stats.rs5{grid-template-columns:repeat(5,minmax(0,1fr))}
.bv{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:28px}
.bv-row{grid-template-columns:auto minmax(0,1fr) auto auto auto}
.bv-r{font-size:.74rem;color:var(--muted);white-space:nowrap}
.bv-p{font-size:.84rem;text-align:right;white-space:nowrap}.bv-p em{font-style:normal;color:var(--muted);font-size:.7rem}
.twocol2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:28px}
.ps-foot{border-top:1px dashed var(--line);padding-top:8px}
@media (max-width:760px){
  .vs-grid,.bv,.twocol2,.ss-cards{grid-template-columns:minmax(0,1fr)}
  .pj-row{grid-template-columns:2.6ch minmax(0,1fr) 54px 44px;gap:6px}
  .pj-row .own,.pj-row .pj-t{display:none}
  .bv-row{grid-template-columns:auto minmax(0,1fr) auto auto}
  .bv-r{display:none}
  .rum-stats.rs5{grid-template-columns:repeat(2,minmax(0,1fr))}
  .ss-vs{display:none}
}
"""


def patch(path, pane):
    s = open(path, encoding="utf-8").read()
    a, b = s.find("<!--PS-->"), s.find("<!--/PS-->")
    if a < 0 or b < 0:
        print("no Player Stats markers in", path); return False
    s = s[:a] + pane + s[b + len("<!--/PS-->"):]
    open(path, "w", encoding="utf-8").write(s)
    print("patched", path); return True


if __name__ == "__main__":
    lgj = json.load(open(os.path.join(HERE, "league.json")))
    pane = build(lgj["short_names"])
    if sys.argv[1:2] == ["--patch"]:
        for f in sys.argv[2:]:
            patch(f, pane)
    else:
        print(pane)
