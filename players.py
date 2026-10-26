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
    def __init__(self, short, week=None):
        """week = the edition's week. The tab then covers games through that week and looks
        ahead to week + 1 (user, 2026-10-19: the week 5 paper shows week 5 stats and week 6
        rankings; Tuesday's week 6 paper rolls to week 6 stats and week 7 rankings)."""
        self.short = {int(k): v for k, v in short.items()}
        self.meta = load("meta.json", {})
        self.P = load("espn_players.json", [])
        self.U = load("usage.json", [])
        self.ros = load("fp_ros.json", {"players": []})
        self.lean = load("fp_lean.json", {"pos": {}})
        self.final = sorted(self.meta.get("final_weeks", []))
        self.live = self.meta.get("espn_week")  # week on the field (may be partly played)
        if week:
            self.cap = int(week)
            self.final = [w for w in self.final if w <= self.cap]
            self.next = self.cap + 1
        else:  # no edition week given: follow the live data
            self.cap = None
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
        self.weeks_played = sorted({w for p in self.P for w in p["act"] if self.cap is None or w <= self.cap})
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


def build(short_names, week=None):
    d = Data(short_names, week)
    if not d.P:
        return ""
    played = d.weeks_played
    last = max(played) if played else 0
    live_note = (f"weeks 1–{last}" + ("" if last in d.final else f", week {last} through Sunday")) if last else ""
    out = []
    fpN0 = d.fp.get(d.next) or {}
    out.append(f'<section class="ps-hero" aria-label="Player stats"><span class="kicker">The PPR player desk</span><h2>Player <span>Stats</span></h2>'
               f'<div class="ps-sub"><span>Player lookup {esc(live_note)}</span><span>Week {d.next} rankings &amp; start/sit</span><span>Rest of season</span><span>Rankings vs. actuals</span></div>'
               f'<nav class="ps-jump" aria-label="Player stats sections">'
               + "".join(f'<a href="#{a}">{t}</a>' for a, t in [("ps-lookup", "Player lookup"), ("ps-volume", "Volume vs. scoring"), ("ps-steady", "Steady or streaky"), ("ps-trend", "Trend lines"), ("ps-next", f"Week {d.next} ranks"), ("ps-proj", "Projections"), ("ps-defense", "Defense matchups"), ("ps-startsit", "Start/sit"), ("ps-faceoff", "Face-off"), ("ps-ros", "Rest of season"), ("ps-variance", "Ranks vs. actuals")])
               + '</nav></section>')

    # ---------- 1. Player Lookup (lookup.py; replaced the Current Data board, user 2026-10-26) ----------
    import lookup
    own_t = int(d.meta.get("owner_team") or (json.load(open(os.path.join(HERE, "league.json"))).get("owner_team") if os.path.exists(os.path.join(HERE, "league.json")) else 1) or 1)
    try:
        out.append(lookup.section(d, d.cap or (max(d.final) if d.final else (max(d.weeks_played) if d.weeks_played else 1)), d.short, own_t))
    except Exception as e:  # never lose the tab over one section
        print("player lookup skipped:", e)

    # ---------- 2. volume vs scoring (interactive: search, filters, tooltips) ----------
    cand = [p for p in d.P if p["pos"] in ("RB", "WR", "TE") and p.get("xp") is not None and p["xp"] >= 4]
    cand.sort(key=lambda p: -p["xp"])
    if cand:
        ranked = cand[:70]  # hot/cold lists come from the 70 biggest-volume players, as before
        hot = sorted(ranked, key=lambda p: -p["res"])[:6]; cold = sorted(ranked, key=lambda p: p["res"])[:6]
        lab = {p["key"] for p in hot[:4] + cold[:4]}
        lo = 0; hi = math.ceil(max(max(p["xp"], p["ppg"]) for p in cand) / 5) * 5
        X = lambda v: (v - lo) / (hi - lo) * 100; Y = lambda v: 100 - (max(v, lo) - lo) / (hi - lo) * 100
        info = []
        dots = []
        for i, p in enumerate(cand):
            o = p.get("owner") or 0
            info.append({"n": p["name"], "pos": p["pos"], "tm": p["team"], "o": o, "on": d.short.get(o, "Free agent") if o else "Free agent",
                         "g": p["g"], "ppg": round(p["ppg"], 1), "xp": round(p["xp"], 1), "r": round(p["res"], 1),
                         "tg": round(p["tgt_g"], 1), "cg": round(p["car_g"], 1), "ts": None if p["ts"] is None else round(p["ts"] * 100),
                         "sn": None if p["snap"] is None else round(p["snap"] * 100), "inj": p.get("inj", "ACTIVE")})
            dots.append(f'<button type="button" class="vd p-{p["pos"]}{" lab" if p["key"] in lab else ""}{" fa" if not o else ""}" data-i="{i}" data-k="{esc(p["key"])}" '
                        f'style="left:{X(p["xp"]):.1f}%;top:{Y(p["ppg"]):.1f}%" aria-label="{esc(p["name"])}, {p["ppg"]:.1f} PPR per game, expected {p["xp"]:.1f}">'
                        + (f'<em>{esc(short_name(p["name"]))}</em>' if p["key"] in lab else "") + '</button>')
        ticks = "".join(f'<span style="left:{X(v):.0f}%">{v}</span>' for v in range(0, hi + 1, 5))
        names = "".join(f'<option value="{esc(x["n"])}">' for x in sorted(info, key=lambda x: x["n"]))
        controls = ('<div class="vs-ctl"><label class="vs-find"><span class="kicker">Find a player</span>'
                    '<input type="search" id="vs-q" list="vs-names" placeholder="Type a name…" autocomplete="off"></label>'
                    f'<datalist id="vs-names">{names}</datalist>'
                    '<div class="vs-f" role="group" aria-label="Positions">'
                    + "".join(f'<button type="button" class="pt" data-f="{x}" aria-pressed="true"><i class="sw p-{x}"></i>{x}</button>' for x in ("RB", "WR", "TE"))
                    + '<button type="button" class="pt" data-f="FA" aria-pressed="false">Free agents only</button></div></div>')
        chart = (f'<div class="vs-wrap"><span class="sc-y">PPR points per game</span><div class="vs" id="vs-plot">'
                 f'<svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><line x1="0" y1="100" x2="100" y2="0" class="vs-eq"/></svg>'
                 f'<span class="q q2">Scoring above<br>his volume</span><span class="q q4">Volume not<br>cashing in yet</span>{"".join(dots)}'
                 '<div class="vs-tip" id="vs-tip" role="status" hidden></div></div>'
                 f'<div class="vs-x">{ticks}</div><span class="sc-x"><span>Expected PPR/g from volume</span></span></div>'
                 '<div class="legend"><span><i class="sw p-RB"></i>RB</span><span><i class="sw p-WR"></i>WR</span><span><i class="sw p-TE"></i>TE</span><span><i class="sw vs-sw"></i>points = volume</span></div>'
                 f'<script type="application/json" id="vs-data">{json.dumps(info, separators=(",", ":")).replace("</", "<\\/")}</script>')
        li = lambda ps, cls: "".join(f'<button type="button" class="rw-row" data-k="{esc(p["key"])}">{d.owner(p)}{d.pname(p)}<span class="rw-v num {cls}">{p["res"]:+.1f}</span><span class="rw-s num">{p["ppg"]:.1f} vs {p["xp"]:.1f}</span></button>' for p in ps)
        lists = (f'<div class="rw"><h3>Running hot</h3><p class="note-s">Scoring more than his volume supports. Sell-high watch.</p>{li(hot, "up")}</div>'
                 f'<div class="rw"><h3>Running cold</h3><p class="note-s">Volume is there, points aren\'t yet. Buy-low watch.</p>{li(cold, "dn")}</div>')
        out.append(sec("ps-volume", "Volume vs. Scoring", "The regression watch",
                       f'{controls}<div class="vs-grid"><div>{chart}</div><div class="rw-col">{lists}</div></div>'
                       f'<p class="note-s">Hover or tap a dot for the player; search to find anyone; tap a hot/cold name to spot him on the chart. Expected points come from a fit of PPR points per game on targets, carries and air yards per game across every player at the position with 3+ games. {len(cand)} RB/WR/TE plotted (3+ games, 4+ expected PPR/g); the hot and cold lists use the 70 with the most volume.</p>'))

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
    seen = set()

    def cand(p, r):
        e = (r or {}).get("e") or {}
        ln = d.lean_by.get(p["key"]) if d.lean.get("week") == N else None
        inj = p.get("inj", "ACTIVE")
        pr = r["proj"] if r else 0.0
        st = "" if pr > 0 else ("out" if inj in ("OUT", "INJURY_RESERVE", "SUSPENSION") else "bye")
        cands.append({"k": p["key"], "n": p["name"], "pos": p["pos"], "tm": p["team"], "o": p.get("owner") or 0,
                      "pr": round(pr, 1), "lo": round(r["lo"], 1) if r else 0.0, "hi": round(r["hi"], 1) if r else 0.0,
                      "rk": e.get("pos_rank") or (f"{p['pos']}{r['rank']}" if r and pr > 0 else "–"), "rmin": e.get("rank_min"), "rmax": e.get("rank_max"),
                      "gr": e.get("start_sit_grade"), "opp": opp(r) if r else "", "ppg": round(p["ppg"], 1), "l3": round(p["l3"], 1),
                      "ts": None if p["ts_l3"] is None else round(p["ts_l3"] * 100), "sn": None if p["snap_l3"] is None else round(p["snap_l3"] * 100),
                      "inj": inj, "st": st, "ln": (1 if ln and ln["analyst"] < ln["ecr"] else -1 if ln else 0)})
        seen.add(p["key"])

    # every player on a league roster (bye and injured players included, so nobody is missing),
    # plus every free agent with a real projection this week
    for pos in POS:
        for r in rows_by_pos[pos]:
            if (r["p"].get("owner") or r["proj"] >= 1) and r["p"]["key"] not in seen:
                cand(r["p"], r if r["proj"] > 0 else None)
    for p in d.P:
        if p.get("owner") and p["key"] not in seen:
            cand(p, None)
    cands.sort(key=lambda c: (c["o"] == 0, c["o"], ["QB", "RB", "WR", "TE"].index(c["pos"]), -c["pr"], c["n"]))
    own = int(d.meta.get("owner_team") or 1)
    mine = [c for c in cands if c["o"] == own and c["pos"] in ("RB", "WR", "TE") and not c["st"]]
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
        cut = {"QB": 24, "RB": 48, "WR": 60, "TE": 24}
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
        beats = sorted(L, key=lambda x: -(x["pts"] - (x["proj"] or 0)))[:10]
        busts = sorted(L, key=lambda x: (x["pts"] - (x["proj"] or 0)))[:10]
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
        under = sorted(A, key=lambda a: -a["apd"])[:12]; over = sorted(A, key=lambda a: a["apd"])[:12]
        trow = lambda a: (f'<tr><td>{d.pname(a["p"])}</td><td>{d.owner(a["p"])}</td><td class="n">{a["n"]}</td><td class="n">{a["p"]["pos"]}{a["rk"] / a["n"]:.0f}</td>'
                          f'<td class="n">{a["p"]["pos"]}{a["fin"] / a["n"]:.0f}</td><td class="n"><b class="{"up" if a["apd"] > 0 else "dn"}">{a["apd"]:+.1f}</b></td></tr>')
        th = '<thead><tr><th>Player</th><th>Owner</th><th class="n">Wks</th><th class="n">Avg rank</th><th class="n">Avg finish</th><th class="n">Pts vs proj</th></tr></thead>'
        season = (f'<div class="twocol2"><div><h3>Underrated all season</h3><div class="tbl-wrap"><table class="pst sm">{th}<tbody>{"".join(trow(a) for a in under)}</tbody></table></div></div>'
                  f'<div><h3>Overrated all season</h3><div class="tbl-wrap"><table class="pst sm">{th}<tbody>{"".join(trow(a) for a in over)}</tbody></table></div></div></div>')
        out.append(sec("ps-variance", "Rankings vs. Actuals", f"Weeks {min(graded)}–{lw} graded",
                       f'<div class="rum-stats rs5">{tiles}</div>{bv}{season}'
                       f'<p class="note-s">Every week\'s consensus PPR ranks (top 60 WR, 48 RB, 24 QB, 24 TE) graded against where each player actually finished at his position (look up any player above for his week-by-week grades). Variance = actual points minus projected points; rank arrows read ranked → finished. Underrated/overrated lists need 3+ graded weeks.</p>'))

    # Trend Lines and Defense Matchups (desk.py, added 2026-10-19): slotted after Player Lookup and Start/Sit
    import desk
    W_ = d.cap or (max(d.final) if d.final else (max(d.weeks_played) if d.weeks_played else 1))
    extra = desk.sections(d, W_, short_names)
    def after(id_, html_):
        if not html_:
            return
        for i, h in enumerate(out):
            if h.startswith(f'<section class="sec" id="{id_}"'):
                out.insert(i + 1, html_); return
        out.append(html_)
    extra.update(desk.sections2(d, W_, short_names, int(d.meta.get("owner_team") or (json.load(open("league.json")).get("owner_team") if os.path.exists("league.json") else 1) or 1)))
    after("ps-lookup", extra.get("trend")); after("ps-volume", extra.get("steady"))
    after("ps-startsit", extra.get("defense")); after("ps-startsit", extra.get("faceoff"))
    # Reading order (user, 2026-10-19: "order the pages so the data makes sense as you scroll"):
    # season so far -> next week -> rest of season -> how the rankings did
    ORDER = ["ps-lookup", "ps-volume", "ps-steady", "ps-trend",
             "ps-next", "ps-proj", "ps-defense", "ps-startsit", "ps-faceoff",
             "ps-ros", "ps-variance"]
    secs = {}
    for h in list(out):
        for id_ in ORDER:
            if h.startswith(f'<section class="sec" id="{id_}"'):
                secs[id_] = h; out.remove(h); break
    out.extend(secs[i] for i in ORDER if i in secs)
    out.append(SCRIPT)
    out.append(desk.SCRIPT)
    out.append(lookup.SCRIPT)
    # the tab carries its own styles, so a midweek --patch also updates them
    import mobile  # phone card layout for the tables (tags each cell with its role and column label)
    return "<!--PS-->\n<style>" + CSS + desk.CSS + lookup.CSS + "</style>\n" + mobile.tag("\n".join(out)) + "\n<!--/PS-->"


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
  (function(){
    var plot=document.getElementById('vs-plot'),src=document.getElementById('vs-data');if(!plot||!src)return;
    var info=JSON.parse(src.textContent),tip=document.getElementById('vs-tip'),q=document.getElementById('vs-q');
    var dots=[].slice.call(plot.querySelectorAll('.vd')),pinned=null,show={RB:1,WR:1,TE:1},faOnly=false;
    function e(s){return String(s==null?'':s).replace(/[&<>"]/g,function(m){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]})}
    function html(p){
      var own=p.o?'<i class="lg lg-'+p.o+'"></i>'+e(p.on):'<span class="own fa">FA</span>';
      var inj=(p.inj&&p.inj!=='ACTIVE'&&p.inj!=='NORMAL')?' <span class="inj">'+e(p.inj.replace('_',' ').toLowerCase())+'</span>':'';
      var cls=p.r>0?'up':p.r<0?'dn':'';
      return '<span class="kicker">'+e(p.pos)+' · '+e(p.tm)+' · '+p.g+' games</span><b class="nm">'+e(p.n)+'</b>'+inj+
        '<span class="tt-own">'+own+'</span>'+
        '<span>'+p.ppg.toFixed(1)+' PPR/g vs '+p.xp.toFixed(1)+' expected <span class="tt-v '+cls+'">'+(p.r>0?'+':'')+p.r.toFixed(1)+'</span></span>'+
        '<span class="tt-g"><span><em>Tgt/g</em><b>'+p.tg.toFixed(1)+'</b></span><span><em>Carries/g</em><b>'+p.cg.toFixed(1)+'</b></span>'+
        '<span><em>Tgt share</em><b>'+(p.ts==null?'–':p.ts+'%')+'</b></span><span><em>Snap %</em><b>'+(p.sn==null?'–':p.sn+'%')+'</b></span></span>';
    }
    function place(d){
      var p=info[+d.dataset.i];tip.innerHTML=html(p);tip.hidden=false;
      var x=parseFloat(d.style.left),y=parseFloat(d.style.top);
      tip.style.left=tip.style.right=tip.style.top=tip.style.bottom='';
      if(x>55)tip.style.right=(100-x+2)+'%';else tip.style.left=(x+2)+'%';
      if(y>55)tip.style.bottom=(100-y+2)+'%';else tip.style.top=(y+2)+'%';
    }
    function hide(){if(pinned){place(pinned)}else{tip.hidden=true}}
    function pin(d){
      dots.forEach(function(x){x.classList.toggle('on',x===d)});
      document.querySelectorAll('button.rw-row').forEach(function(r){r.classList.toggle('on',!!d&&r.dataset.k===d.dataset.k)});
      pinned=d;if(d){place(d)}else{tip.hidden=true}
    }
    function filter(){
      var t=(q.value||'').trim().toLowerCase(),hits=[];
      dots.forEach(function(d){
        var p=info[+d.dataset.i],vis=show[p.pos]&&(!faOnly||!p.o);
        d.classList.toggle('off',!vis);
        var m=t&&vis&&p.n.toLowerCase().indexOf(t)>=0;if(m)hits.push(d);
        d.classList.toggle('hit',!!m);d.classList.toggle('dim',!!t&&!m);
      });
      plot.classList.toggle('searching',!!t);
      if(pinned&&pinned.classList.contains('off'))pin(null);
      if(t&&hits.length===1)pin(hits[0]);else if(t&&pinned&&hits.indexOf(pinned)<0)pin(null);
    }
    // the nearest visible dot to the pointer (snaps, so crowded spots and fingers work)
    function near(ev,max){
      var best=null,bd=max*max;
      dots.forEach(function(d){
        if(d.classList.contains('off'))return;
        var r=d.getBoundingClientRect(),dx=r.left+r.width/2-ev.clientX,dy=r.top+r.height/2-ev.clientY,dd=dx*dx+dy*dy;
        if(dd<bd){bd=dd;best=d}
      });
      return best;
    }
    var hov=null;
    plot.addEventListener('pointermove',function(ev){
      if(ev.pointerType!=='mouse')return;
      var d=near(ev,22);if(d===hov)return;hov=d;
      dots.forEach(function(x){x.classList.toggle('hov',x===d)});
      if(d)place(d);else hide();
    });
    plot.addEventListener('pointerleave',function(){hov=null;dots.forEach(function(x){x.classList.remove('hov')});hide()});
    dots.forEach(function(d){
      d.addEventListener('focus',function(){place(d)});
      d.addEventListener('blur',hide);
    });
    document.addEventListener('click',function(ev){
      if(pinned&&!plot.contains(ev.target)&&!ev.target.closest('button.rw-row,.vs-ctl'))pin(null);
    });
    plot.addEventListener('click',function(ev){
      var d=ev.detail===0&&ev.target.classList.contains('vd')?ev.target:near(ev,30);  // detail 0 = keyboard
      pin(d&&pinned!==d?d:null);
    });
    q.addEventListener('input',filter);
    document.querySelectorAll('.vs-f .pt').forEach(function(b){b.addEventListener('click',function(){
      var on=b.getAttribute('aria-pressed')!=='true';b.setAttribute('aria-pressed',on?'true':'false');
      if(b.dataset.f==='FA')faOnly=on;else show[b.dataset.f]=on?1:0;filter();
    })});
    document.querySelectorAll('button.rw-row').forEach(function(r){r.addEventListener('click',function(){
      var d=plot.querySelector('.vd[data-k="'+r.dataset.k+'"]');if(!d)return;
      if(d.classList.contains('off')){var p=info[+d.dataset.i];show[p.pos]=1;faOnly=false;
        document.querySelectorAll('.vs-f .pt').forEach(function(b){if(b.dataset.f===p.pos)b.setAttribute('aria-pressed','true');if(b.dataset.f==='FA')b.setAttribute('aria-pressed','false')});
        q.value='';filter();}
      pin(pinned===d?null:d);
      if(window.innerWidth<760)plot.scrollIntoView({block:'center',behavior:'smooth'});
    })});
  })();
  var el=document.getElementById('ss-data'); if(!el)return;
  var D=JSON.parse(el.textContent),C=D.c,T=D.teams,byk={};C.forEach(function(c){byk[c.k]=c});
  var A=document.getElementById('ss-a'),B=document.getElementById('ss-b'),O=document.getElementById('ss-out');
  function opts(sel){
    var groups={};C.forEach(function(c){var g=c.o?T[c.o]:'Free agents';(groups[g]=groups[g]||[]).push(c)});
    Object.keys(groups).forEach(function(g){
      var og=document.createElement('optgroup');og.label=g;
      groups[g].forEach(function(c){var o=document.createElement('option');o.value=c.k;o.textContent=c.n+' ('+c.pos+', '+c.tm+')'+(c.st==='bye'?' · no game':c.st==='out'?' · out':'');og.appendChild(o)});
      sel.appendChild(og);
    });
  }
  opts(A);opts(B);
  if(D.def.length===2){A.value=D.def[0];B.value=D.def[1]}else if(C.length>1){A.value=C[0].k;B.value=C[1].k}
  function e(s){return String(s==null?'':s).replace(/[&<>"]/g,function(m){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]})}
  function score(c){if(c.st)return -1000;var s=c.pr+0.35*c.lo+(c.ts?c.ts*0.04:0)+(c.sn?c.sn*0.01:0);if(c.inj==='OUT'||c.inj==='INJURY_RESERVE')s-=100;if(c.inj==='DOUBTFUL')s-=8;if(c.inj==='QUESTIONABLE')s-=1.5;return s}
  function card(c,win){
    var inj=(c.inj&&c.inj!=='ACTIVE'&&c.inj!=='NORMAL')?'<span class="inj">'+e(c.inj.replace('_',' ').toLowerCase())+'</span>':'';
    var ln=c.ln>0?'<span class="flag">Contrarian lean: higher</span>':c.ln<0?'<span class="flag dn">Contrarian lean: lower</span>':'';
    return '<div class="ss-card'+(win?' win':'')+'"><div class="ss-top">'+(win?'<span class="fs-tag">Start</span>':'<span class="ss-sit">Sit</span>')+(c.o?'<i class="lg lg-'+c.o+' lg-sm"></i>':'<span class="own fa">FA</span>')+'</div>'+
      '<h3>'+e(c.n)+'</h3><span class="kicker">'+e(c.pos)+' · '+e(c.tm)+(c.opp?' · '+e(c.opp):'')+'</span>'+inj+
      (c.st?'<div class="ss-big"><b class="num">0.0</b><span>'+(c.st==='bye'?'no game this week<br><em>bye</em>':'not playing<br><em>ruled out</em>')+'</span></div>':
      '<div class="ss-big"><b class="num">'+c.pr.toFixed(1)+'</b><span>projected PPR<br><em class="num">range '+c.lo.toFixed(1)+'–'+c.hi.toFixed(1)+'</em></span></div>')+
      '<div class="ss-stats"><span><em>Rank</em><b class="num">'+e(c.rk)+'</b></span><span><em>Rank range</em><b class="num">'+(c.rmin?e(c.rmin)+'–'+e(c.rmax):'–')+'</b></span><span><em>Grade</em><b class="num">'+e(c.gr||'–')+'</b></span>'+
      '<span><em>PPR/g</em><b class="num">'+c.ppg.toFixed(1)+'</b></span><span><em>Last 3</em><b class="num">'+c.l3.toFixed(1)+'</b></span><span><em>Tgt share L3</em><b class="num">'+(c.ts==null?'–':c.ts+'%')+'</b></span></div>'+ln+'</div>';
  }
  function go(){
    var a=byk[A.value],b=byk[B.value];if(!a||!b){O.innerHTML='';return}
    if(a.k===b.k){O.innerHTML='<p class="note-s">Pick two different players.</p>';return}
    var sa=score(a),sb=score(b),w=sa>=sb?a:b,l=w===a?b:a,gap=Math.abs(sa-sb);
    var why=(a.st&&b.st)?'Neither one plays this week.':l.st?'Easy call: '+e(l.n)+(l.st==='bye'?' has no game this week.':' is out.'):gap<1?'Coin flip. Go with the higher floor: '+e(w.n)+'.':gap<3?'Lean '+e(w.n)+'.':'Clear call: start '+e(w.n)+'.';
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
.vs{grid-column:2;position:relative;aspect-ratio:1.1;touch-action:manipulation;cursor:crosshair;border-left:2px solid var(--rule);border-bottom:2px solid var(--rule);background:linear-gradient(var(--line) 1px,transparent 1px) 0 0/100% 20%,linear-gradient(90deg,var(--line) 1px,transparent 1px) 0 0/20% 100%}
.vs svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible}
.vs-eq{stroke:var(--muted);stroke-width:1.5;stroke-dasharray:4 4;vector-effect:non-scaling-stroke}
.vs-x{grid-column:2;position:relative;height:16px;font-family:var(--mono);font-size:.64rem;color:var(--muted)}
.vs-x span{position:absolute;transform:translateX(-50%)}
.vs-wrap .sc-x{grid-column:2}
.vd{appearance:none;padding:0;cursor:pointer;position:absolute;width:11px;height:11px;border-radius:50%;transform:translate(-50%,-50%);border:1.5px solid var(--sheet);z-index:1;transition:opacity .15s,transform .15s}
.vd::after{content:"";position:absolute;inset:-6px;border-radius:50%}
.vd.lab{width:13px;height:13px;border-color:var(--ink);z-index:2}
.vd em{position:absolute;left:12px;top:-4px;font-style:normal;font-family:var(--body);color:var(--ink);font-size:.66rem;font-weight:600;white-space:nowrap;background:var(--sheet);padding:0 3px;line-height:1.3;pointer-events:none}
.vd.hov,.vd:focus-visible,.vd.on{transform:translate(-50%,-50%) scale(1.6);z-index:4;border-color:var(--ink);outline:none}
.vd.hit{transform:translate(-50%,-50%) scale(1.5);z-index:3;border-color:var(--ink)}
.vd.dim{opacity:.15}
.vd.off{display:none}
.vs.searching .vd em{display:none}
.vs.searching .vd.hit em,.vd.on em{display:block}
.vs-tip{position:absolute;z-index:6;width:min(230px,70%);background:var(--sheet);border:2px solid var(--rule);box-shadow:4px 4px 0 var(--rule);padding:10px 12px;display:grid;gap:6px;pointer-events:none;font-size:.82rem}
.vs-tip[hidden]{display:none}
.vs-tip b.nm{font-family:var(--display);font-weight:900;font-size:1.25rem;text-transform:uppercase;line-height:1}
.vs-tip .kicker{font-size:.6rem}
.vs-tip .tt-own{display:flex;align-items:center;gap:6px;font-size:.78rem}
.vs-tip .tt-own .lg{width:18px;height:18px}
.vs-tip .tt-g{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px 8px;border-top:1px dashed var(--line);padding-top:6px}
.vs-tip .tt-g span{display:grid;font-family:var(--mono)}
.vs-tip .tt-g em{font-style:normal;font-size:.56rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.vs-tip .tt-g b{font-size:.9rem}
.vs-tip .tt-v{font-family:var(--mono);font-weight:600}
.vs-ctl{display:flex;flex-wrap:wrap;align-items:end;gap:10px 18px}
.vs-find{display:grid;gap:4px;flex:1 1 240px;max-width:360px}
.vs-find input{font:inherit;font-size:.95rem;padding:8px 10px;border:2px solid var(--rule);background:var(--sheet);color:var(--ink);width:100%}
.vs-find input:focus{outline:3px solid var(--hi);outline-offset:1px}
.vs-f{display:flex;flex-wrap:wrap;gap:4px}
.vs-f .pt{display:inline-flex;align-items:center;gap:6px}
.vs-f .pt .sw{border:1.5px solid var(--sheet)}
.vs-f .pt[aria-pressed="false"]{opacity:.55}
.vs-f .pt[data-f="FA"][aria-pressed="false"]{opacity:1}
.vs-f .pt[data-f="FA"][aria-pressed="true"]{background:var(--hi);color:var(--hi-ink);border-color:var(--hi)}
button.rw-row{appearance:none;background:none;border:0;border-bottom:1px solid var(--line);width:100%;text-align:left;font:inherit;color:inherit;cursor:pointer}
button.rw-row:hover,button.rw-row.on{background:var(--paper)}
button.rw-row:focus-visible{outline:3px solid var(--hi);outline-offset:-3px}
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

tr[hidden]{display:none}
@media (max-width:760px){
  .vs-tip{position:fixed;left:12px!important;right:12px!important;top:auto!important;bottom:12px!important;width:auto;z-index:50}
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
    # python3 players.py [--week N] [--patch FILE...]
    args = sys.argv[1:]
    week = None
    if args[:1] == ["--week"]:
        week = int(args[1]); args = args[2:]
    lgj = json.load(open(os.path.join(HERE, "league.json")))
    pane = build(lgj["short_names"], week)
    if args[:1] == ["--patch"]:
        for f in args[1:]:
            patch(f, pane)
    else:
        print(pane)
