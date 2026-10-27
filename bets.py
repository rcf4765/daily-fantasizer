"""The Daily Fantasizer: the Betting tab (user, 2026-10-26: "experiment ... like sports betting apps, but with that
week's points, up to 50").

A side game. ESPN scores are never touched; the paper shows a "with bets" score and standings next to the real ones.

Rules (user's choices, 2026-10-26)
- Each team may stake up to MAX_STAKE (5; was 50 until the user cut it on 2026-10-27) of its week-N points in total
  that week, across any number of slips.
- A slip is 1..MAX_LEGS legs (a parlay when 2+). Sportsbook odds: favorites pay less, long shots and parlays more.
  Win = the slip's profit is added to that week's score (capped at MAX_WIN); loss = the stake is subtracted.
  A pushed or voided leg drops out of the parlay; a slip with nothing left is a push (0).
- Each leg locks at its game's kickoff. League-matchup legs lock at the week's first NFL kickoff.
- Markets: player props (fantasy points, yards, receptions, touchdowns), our league's matchups (moneyline, spread,
  total) and real NFL games (moneyline, spread, total).

Lines
- NFL: the sportsbook lines nflverse carries (data/players/nfl_schedule.json "games", fetched with the player data).
- League: each team's best projected lineup for the week (blended projections, ESPN for K and D/ST, same as Matchup of
  the Week). Win chance = normal model with the league's week-to-week swing; spread/total at -110.
- Props: fantasy points at the blended projection; yards and receptions at 60% season / 40% last-3 per-game average;
  O/U at -110 with the line on a half point so it can't push. Touchdowns: Poisson chance from his TD rate (two
  games of position-average prior), priced with a 5% house edge.

Files
- data/bets/lines{N}.json: the week-N board (built with the week N-1 edition) -> copied to docs/bets/ so the league
  office server can check every leg's odds and lock time when a bet is placed (it never trusts the page's numbers).
- data/bets/placed.json: every bet, saved from the league office by fetch_bets.py (GitHub Actions, Tuesdays).
- data/bets/results{N}.json: graded slips, net points and with-bets scores for week N (built by settle()).
"""
import datetime, html, json, math, os, re
from collections import defaultdict

MAX_STAKE, MAX_LEGS, MAX_WIN = 5, 6, 150
VIG = 1.05
POS = ("QB", "RB", "WR", "TE")
TD_PRIOR = {"QB": 0.12, "RB": 0.45, "WR": 0.35, "TE": 0.25}
BDIR = os.path.join("data", "bets")
esc = html.escape


# ---------------------------------------------------------------- odds helpers
def dec(a):
    a = float(a)
    return 1 + a / 100 if a > 0 else 1 + 100 / abs(a)


def american(p):
    """Price a true chance p with the house edge, rounded the way books do."""
    q = min(0.97, max(0.03, p * VIG))
    a = -100 * q / (1 - q) if q >= 0.5 else 100 * (1 - q) / q
    step = 5 if abs(a) < 300 else 25
    a = int(round(a / step) * step)
    return a if abs(a) >= 100 else (-110 if q >= 0.5 else 100)


def half(x):
    """Line on a half point (no pushes)."""
    return math.floor(x) + 0.5


def phi(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _sel(eid, m, side, name, odds):
    return {"id": f"{eid}|{m}|{side}", "name": name, "odds": int(odds)}


# ---------------------------------------------------------------- lines
def lines(W, short):
    """Board for week W+1, built from the data available at the week-W edition."""
    import strength as S, teams as TM
    from facts import load as _load
    T = W + 1
    sch = json.load(open("data/players/nfl_schedule.json")) if os.path.exists("data/players/nfl_schedule.json") else {}
    games = [g for g in sch.get("games", []) if g["week"] == T]
    if not games:
        return None
    byes = sch.get("byes", {})
    ko = {}
    for g in games:
        ko[g["home"]] = ko[g["away"]] = g
    first = min(g["kickoff"] for g in games)
    out = {"week": T, "made": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "first_kickoff": first,
           "max_stake": MAX_STAKE, "max_legs": MAX_LEGS, "max_win": MAX_WIN, "nfl": [], "league": [], "props": []}

    # --- NFL games
    for g in sorted(games, key=lambda g: (g["kickoff"], g["id"])):
        eid, mk = "N:" + g["id"], []
        if g.get("aml") and g.get("hml"):
            mk.append({"m": "ml", "label": "Moneyline", "sel": [_sel(eid, "ml", "a", g["away"], g["aml"]), _sel(eid, "ml", "h", g["home"], g["hml"])]})
        if g.get("spread") is not None:
            hl = -g["spread"]
            f = lambda v: f"{v:+g}" if v else "PK"
            mk.append({"m": "sp", "label": "Spread", "line": hl, "sel": [_sel(eid, "sp", "a", f'{g["away"]} {f(-hl)}', g.get("aso") or -110),
                                                                        _sel(eid, "sp", "h", f'{g["home"]} {f(hl)}', g.get("hso") or -110)]})
        if g.get("total") is not None:
            mk.append({"m": "tot", "label": "Total", "line": g["total"], "sel": [_sel(eid, "tot", "o", f'Over {g["total"]:g}', g.get("oo") or -110),
                                                                                _sel(eid, "tot", "u", f'Under {g["total"]:g}', g.get("uo") or -110)]})
        if mk:
            out["nfl"].append({"id": eid, "title": f'{g["away"]} @ {g["home"]}', "away": g["away"], "home": g["home"], "lock": g["kickoff"], "markets": mk})

    # --- player props (and the projections the league lines use)
    X = S.compute(short, W); d = X["d"]
    rawp = S.raw_proj(W)

    def pj(p):
        if p.get("inj") in ("OUT", "INJURY_RESERVE", "SUSPENSION") or T in byes.get(p["team"], []) or p["team"] not in ko:
            return 0.0
        return S.proj_for(d, p, T, rawp) or 0.0

    for p in d.P:
        g = ko.get(p["team"])
        if not g or p["pos"] not in POS:
            continue
        pr = pj(p)
        if pr <= 0 or (not p.get("owner") and pr < 6) or p["g"] < 1:
            continue
        gw = [w for w in d.games(p) if w <= W]
        if not gw:
            continue
        l3 = gw[-3:]
        avg = lambda k, ws: sum(p["act"][w].get(k, 0) for w in ws) / len(ws)
        blend = lambda k: 0.6 * avg(k, gw) + 0.4 * avg(k, l3)
        eid, mk = f'P:{p["id"]}', []
        ln = half(pr)
        mk.append({"m": "fp", "label": "Fantasy points (PPR)", "line": ln, "sel": [_sel(eid, "fp", "o", f"Over {ln:g}", -110), _sel(eid, "fp", "u", f"Under {ln:g}", -110)]})
        if p["pos"] == "QB":
            if blend("pa_yds") >= 120:
                ln = half(blend("pa_yds"))
                mk.append({"m": "pyd", "label": "Passing yards", "line": ln, "sel": [_sel(eid, "pyd", "o", f"Over {ln:g}", -110), _sel(eid, "pyd", "u", f"Under {ln:g}", -110)]})
            lam = (sum(p["act"][w].get("pa_td", 0) for w in gw) + 2 * 1.5) / (len(gw) + 2)
            po = 1 - math.exp(-lam) * (1 + lam)
            mk.append({"m": "ptd", "label": "Passing TDs", "line": 1.5, "sel": [_sel(eid, "ptd", "o", "Over 1.5", american(po)), _sel(eid, "ptd", "u", "Under 1.5", american(1 - po))]})
            if blend("ru_yds") >= 15:
                ln = half(blend("ru_yds"))
                mk.append({"m": "ryd", "label": "Rushing yards", "line": ln, "sel": [_sel(eid, "ryd", "o", f"Over {ln:g}", -110), _sel(eid, "ryd", "u", f"Under {ln:g}", -110)]})
        else:
            if p["pos"] == "RB" and blend("ru_yds") >= 15:
                ln = half(blend("ru_yds"))
                mk.append({"m": "ryd", "label": "Rushing yards", "line": ln, "sel": [_sel(eid, "ryd", "o", f"Over {ln:g}", -110), _sel(eid, "ryd", "u", f"Under {ln:g}", -110)]})
            if blend("re_yds") >= 12:
                ln = half(blend("re_yds"))
                mk.append({"m": "cyd", "label": "Receiving yards", "line": ln, "sel": [_sel(eid, "cyd", "o", f"Over {ln:g}", -110), _sel(eid, "cyd", "u", f"Under {ln:g}", -110)]})
            if blend("rec") >= 1.5:
                ln = half(blend("rec"))
                mk.append({"m": "rec", "label": "Receptions", "line": ln, "sel": [_sel(eid, "rec", "o", f"Over {ln:g}", -110), _sel(eid, "rec", "u", f"Under {ln:g}", -110)]})
            tds = sum(p["act"][w].get("ru_td", 0) + p["act"][w].get("re_td", 0) for w in gw)
            lam = (tds + 2 * TD_PRIOR[p["pos"]]) / (len(gw) + 2)
            mk.append({"m": "td", "label": "Anytime touchdown", "sel": [_sel(eid, "td", "y", "Scores a TD", american(1 - math.exp(-lam)))]})
        opp = g["away"] if g["home"] == p["team"] else g["home"]
        out["props"].append({"id": eid, "name": p["name"], "pos": p["pos"], "team": p["team"], "owner": p.get("owner") or 0,
                             "opp": ("vs " if g["home"] == p["team"] else "@ ") + opp, "lock": g["kickoff"], "proj": round(pr, 1), "markets": mk})
    out["props"].sort(key=lambda e: -e["proj"])

    # --- our league's matchups
    LG = json.load(open("data/schedule.json")) if os.path.exists("data/schedule.json") else {"games": []}
    lg_games = [m for m in LG.get("games", []) if m.get("wk") == T]
    if lg_games:
        KD = json.load(open("data/players/espn_kdst.json")) if os.path.exists("data/players/espn_kdst.json") else []
        tot = {}
        for t in {m["home"] for m in lg_games} | {m["away"] for m in lg_games}:
            ps = [p for p in d.P if p.get("owner") == t]
            s = sum(pj(x) for _, x in TM._lineup(ps, pj) if x)
            for pos in ("D/ST", "K"):
                c = [x.get("proj", {}).get(str(T)) for x in KD if x.get("owner") == t and x["pos"] == pos and x.get("proj", {}).get(str(T)) is not None]
                s += max(c) if c else 0.0
            tot[t] = s
        # week-to-week swing: each team's weekly scores around its own average, pooled
        dev = []
        for t in tot:
            sc = []
            for k in range(1, W + 1):
                f = f"data/week{k}_raw.txt"
                if os.path.exists(f):
                    for m in _load(f)[3]:
                        if m["wk"] == k and t in (m["home"], m["away"]):
                            sc.append(m["hp"] if m["home"] == t else m["ap"])
            if len(sc) > 1:
                mu = sum(sc) / len(sc); dev += [(x - mu) ** 2 for x in sc]
        sig = math.sqrt(sum(dev) / len(dev)) if dev else 20.0
        sh = {int(k): v for k, v in short.items()}
        for m in lg_games:
            h, a = m["home"], m["away"]
            diff = tot[h] - tot[a]
            ph = phi(diff / (sig * math.sqrt(2)))
            eid = f"L:{T}:{h}-{a}"
            hl = -round(diff * 2) / 2
            f = lambda v: f"{v:+g}" if v else "PK"
            tl = half(tot[h] + tot[a])
            out["league"].append({"id": eid, "title": f"{sh.get(a, a)} @ {sh.get(h, h)}", "home": h, "away": a, "lock": first,
                                  "proj": [round(tot[a], 1), round(tot[h], 1)],
                                  "markets": [{"m": "ml", "label": "Moneyline", "sel": [_sel(eid, "ml", "a", sh.get(a, str(a)), american(1 - ph)), _sel(eid, "ml", "h", sh.get(h, str(h)), american(ph))]},
                                              {"m": "sp", "label": "Spread", "line": hl, "sel": [_sel(eid, "sp", "a", f"{sh.get(a, a)} {f(-hl)}", -110), _sel(eid, "sp", "h", f"{sh.get(h, h)} {f(hl)}", -110)]},
                                              {"m": "tot", "label": "Total", "line": tl, "sel": [_sel(eid, "tot", "o", f"Over {tl:g}", -110), _sel(eid, "tot", "u", f"Under {tl:g}", -110)]}]})
        out["sigma"] = round(sig, 1)
    return out


def save_lines(W, short):
    b = lines(W, short)
    if not b:
        return None
    os.makedirs(BDIR, exist_ok=True)
    with open(os.path.join(BDIR, f"lines{b['week']}.json"), "w") as f:
        json.dump(b, f, separators=(",", ":"))
    return b


# ---------------------------------------------------------------- settlement
def _grade_leg(lid, ln, N, P, games, sched):
    """'w', 'l', 'p' (push) or 'v' (void: player didn't play, game not final). ln = the market's line on the board."""
    ev, m, side = lid.split("|")
    kind, rest = ev.split(":", 1)
    if kind == "N":
        g = games.get(rest)
        if not g or g.get("hs") is None or g.get("as") is None:
            return "v"
        return _game(m, side, g["hs"], g["as"], ln if m == "sp" else 0, ln if m == "tot" else None)
    if kind == "L":
        wk, pair = rest.split(":")
        h, a = map(int, pair.split("-"))
        mt = next((x for x in sched if x["wk"] == int(wk) and x["home"] == h and x["away"] == a), None)
        if not mt:
            return "v"
        return _game(m, side, mt["hp"], mt["ap"], ln if m == "sp" else 0, ln if m == "tot" else None)
    if kind == "P":
        p = P.get(int(rest))
        st = p and (p["act"].get(str(N)) or p["act"].get(N))
        if not st:
            return "v"
        val = {"fp": st.get("pts", 0), "pyd": st.get("pa_yds", 0), "ptd": st.get("pa_td", 0), "ryd": st.get("ru_yds", 0),
               "cyd": st.get("re_yds", 0), "rec": st.get("rec", 0), "td": st.get("ru_td", 0) + st.get("re_td", 0)}.get(m)
        if val is None:
            return "v"
        if m == "td":
            return "w" if val >= 1 else "l"
        return "p" if val == ln else "w" if (val > ln) == (side == "o") else "l"
    return "v"


def _game(m, side, hs, as_, hl, total):
    """Home score, away score, the home side's spread (e.g. -3.5) and the total."""
    if m == "ml":
        if hs == as_:
            return "p"
        return "w" if (hs > as_) == (side == "h") else "l"
    if m == "sp":
        x = (hs - as_ + hl) * (1 if side == "h" else -1)
        return "p" if x == 0 else "w" if x > 0 else "l"
    if m == "tot":
        x = hs + as_ - total
        return "p" if x == 0 else "w" if (x > 0) == (side == "o") else "l"
    return "v"


def settle(N, short):
    """Grade every bet for week N. Needs data/bets/lines{N}.json (lines, for line values), data/bets/placed.json and week
    N's results (data/weekN_raw.txt, player stats, NFL scores). Writes data/bets/results{N}.json; returns it or None."""
    from facts import load as _load
    lf, pf = os.path.join(BDIR, f"lines{N}.json"), os.path.join(BDIR, "placed.json")
    raw = f"data/week{N}_raw.txt"
    if not (os.path.exists(lf) and os.path.exists(raw)):
        return None
    B = json.load(open(lf))
    placed = json.load(open(pf)) if os.path.exists(pf) else []
    line = {}
    for grp in ("nfl", "league", "props"):
        for e in B.get(grp, []):
            for mk in e["markets"]:
                for s in mk["sel"]:
                    line[s["id"]] = (mk.get("line"), s["name"], e)
    sch = json.load(open("data/players/nfl_schedule.json"))
    games = {g["id"]: g for g in sch.get("games", [])}
    P = {p["id"]: p for p in json.load(open("data/players/espn_players.json"))}
    sched = _load(raw)[3]
    score = {}
    for mt in sched:
        if mt["wk"] == N:
            score[mt["home"]] = mt["hp"]; score[mt["away"]] = mt["ap"]
    slips = []
    for b in placed:
        if int(b.get("week", 0)) != N or b.get("status") == "cancelled":
            continue
        legs, d_, res = [], 1.0, []
        for lg in b["legs"]:
            g = _grade_leg(lg["id"], line.get(lg["id"], (None,))[0], N, P, games, sched)
            legs.append({**lg, "r": g})
            res.append(g)
            if g == "w":
                d_ *= dec(lg["odds"])
        stake = float(b["stake"])
        if "l" in res:
            net, r = -stake, "lost"
        elif any(x == "w" for x in res):
            net, r = round(min(MAX_WIN, stake * (d_ - 1)), 2), "won"
        else:
            net, r = 0.0, "push"
        slips.append({"id": b["id"], "team": int(b["team"]), "stake": stake, "net": net, "result": r, "legs": legs})
    net = defaultdict(float)
    for s in slips:
        net[s["team"]] += s["net"]
    adj = {t: round(score[t] + net[t], 2) for t in score}
    games_out = []
    for mt in sched:
        if mt["wk"] != N:
            continue
        h, a = mt["home"], mt["away"]
        real = "h" if mt["hp"] > mt["ap"] else "a" if mt["ap"] > mt["hp"] else "t"
        wb = "h" if adj[h] > adj[a] else "a" if adj[a] > adj[h] else "t"
        games_out.append({"home": h, "away": a, "hp": mt["hp"], "ap": mt["ap"], "hb": adj[h], "ab": adj[a], "real": real, "with_bets": wb})
    out = {"week": N, "slips": slips, "net": {str(t): round(v, 2) for t, v in net.items()}, "games": games_out}
    with open(os.path.join(BDIR, f"results{N}.json"), "w") as f:
        json.dump(out, f, separators=(",", ":"))
    return out


def standings(upto):
    """Season with-bets records from every results file through week upto."""
    from facts import load as _load
    rec = defaultdict(lambda: {"w": 0, "l": 0, "t": 0, "bw": 0, "bl": 0, "bt": 0, "net": 0.0, "slips": 0, "won": 0})
    weeks = []
    for k in range(1, upto + 1):
        f = f"data/week{k}_raw.txt"
        if not os.path.exists(f):
            continue
        rf = os.path.join(BDIR, f"results{k}.json")
        R = json.load(open(rf)) if os.path.exists(rf) else None
        if R:
            weeks.append(k)
        net = {int(t): v for t, v in (R or {}).get("net", {}).items()}
        for mt in _load(f)[3]:
            if mt["wk"] != k:
                continue
            h, a, hp, ap = mt["home"], mt["away"], mt["hp"], mt["ap"]
            for t, x, y in ((h, hp, ap), (a, ap, hp)):
                rec[t]["w" if x > y else "l" if x < y else "t"] += 1
                xb, yb = x + net.get(t, 0), y + net.get(a if t == h else h, 0)
                rec[t]["b" + ("w" if xb > yb else "l" if xb < yb else "t")] += 1
                rec[t]["net"] += net.get(t, 0)
        for s in (R or {}).get("slips", []):
            rec[s["team"]]["slips"] += 1; rec[s["team"]]["won"] += s["result"] == "won"
    return rec, weeks


# ---------------------------------------------------------------- page
def build(W, short, api):
    """Called by render.py for the week-W edition: grade week W, post the week W+1 board, return the pane."""
    try:
        settle(W, short)
    except Exception as e:  # never lose the paper over the side game
        print("bets: settling week", W, "failed:", e)
    try:
        save_lines(W, short)
    except Exception as e:
        print("bets: week", W + 1, "board failed:", e)
    return section(W, short, api)


def section(W, short, api):
    """The Betting pane for the week-W edition: the week W+1 board, live bets from the league office, last week's results."""
    lf = os.path.join(BDIR, f"lines{W + 1}.json")
    b = json.load(open(lf)) if os.path.exists(lf) else lines(W, short)
    sh = {str(int(k)): v for k, v in short.items()}
    res = None
    rf = os.path.join(BDIR, f"results{W}.json")
    if os.path.exists(rf):
        res = json.load(open(rf))
    rec, weeks = standings(W)
    stand = [{"team": t, **v} for t, v in rec.items()] if weeks else []
    data = {"board": b, "teams": sh, "api": api, "results": res, "stand": stand, "weeks": weeks,
            "rules": {"stake": MAX_STAKE, "legs": MAX_LEGS, "win": MAX_WIN}}
    T = W + 1
    return ("<style>" + CSS + "</style>" + f'<section class="bk-hero" aria-label="Betting"><span class="kicker">The sportsbook · week {T}</span><h2>Bet<span>ting</span></h2>'
            f'<p>Points, not money. Stake up to <b>{MAX_STAKE}</b> of your week {T} points on props, our league\'s matchups or real NFL games. '
            f'Win and the payout is added to your week {T} score; lose and the stake comes off it. A side game: ESPN scores never change.</p>'
            f'<div class="bk-me" id="bk-me"></div></section>'
            f'<div class="bk-layout"><div class="bk-main">'
            f'<div class="bk-mk" role="tablist" aria-label="Markets"><button type="button" class="bk-mt" data-g="props" aria-selected="true">Player props</button>'
            f'<button type="button" class="bk-mt" data-g="league" aria-selected="false">Our league</button><button type="button" class="bk-mt" data-g="nfl" aria-selected="false">NFL games</button></div>'
            f'<div class="bk-filters" id="bk-filters"></div><div class="bk-board" id="bk-board"></div></div>'
            f'<aside class="bk-slip" id="bk-slip" aria-label="Bet slip"></aside></div>'
            f'<section class="sec" id="bk-mine"><div class="sec-head"><h2>Bets on the Board</h2><span class="kicker">Week {T} · every team\'s slips</span></div><div id="bk-live"></div></section>'
            f'<section class="sec" id="bk-results"><div class="sec-head"><h2>Week {W} Payouts</h2><span class="kicker">Graded slips · real vs. with-bets scores</span></div><div id="bk-res"></div></section>'
            f'<section class="sec" id="bk-stand"><div class="sec-head"><h2>With-Bets Standings</h2><span class="kicker">The side game · real record vs. record with bets</span></div><div id="bk-st"></div></section>'
            f'<p class="note-s">Lines: NFL games use posted sportsbook lines; our league\'s lines come from each team\'s best projected lineup; '
            f'player props are set at his projection or recent per-game average, so each side is close to a coin flip, and touchdown odds come from his scoring rate. '
            f'Up to {MAX_LEGS} legs per slip, winnings capped at {MAX_WIN} points per slip. Each leg locks at its game\'s kickoff; league matchups lock at the week\'s first kickoff. '
            f'A pushed or voided leg (player inactive) drops out of the parlay. Bets are recorded by the league office with the same team sign-in as Rule Changes.</p>'
            f'<script type="application/json" id="bk-data">{json.dumps(data, separators=(",", ":")).replace("</", "<\\/")}</script>'
            + SCRIPT)


CSS = r"""
/* Betting tab (bets.py) */
.bk-hero{display:grid;gap:10px;padding:24px 22px 18px;background:radial-gradient(var(--dot) 1.4px,transparent 1.6px) 0 0/9px 9px,var(--paper);border:3px solid var(--rule);border-top:10px solid var(--honolulu)}
.bk-hero h2{font-size:clamp(2.8rem,9vw,5.6rem);font-weight:900;text-transform:uppercase}.bk-hero h2 span{color:var(--blue)}
.bk-hero p{max-width:760px}
.bk-me{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;font-family:var(--mono);font-size:.78rem}
.bk-me .lg{width:26px;height:26px}
.bk-me b{font-family:var(--display);font-size:1.1rem}
.bk-me a{color:var(--blue)}
.bk-bank{display:inline-flex;gap:6px;align-items:center;background:var(--ink);color:var(--sheet);padding:4px 10px;border-radius:3px}
.bk-layout{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:22px;align-items:start}
.bk-main{display:grid;gap:12px;min-width:0}
.bk-mk{display:flex;gap:4px;border-bottom:3px solid var(--rule)}
.bk-mt{appearance:none;font-family:var(--display);font-weight:800;font-size:1.05rem;text-transform:uppercase;letter-spacing:.03em;padding:9px 16px;border:2px solid var(--rule);border-bottom:0;background:var(--paper);color:var(--muted);cursor:pointer;border-radius:5px 5px 0 0}
.bk-mt[aria-selected="true"]{background:var(--ink);color:var(--sheet)}
.bk-filters{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.bk-filters input,.bk-filters select{font:inherit;font-size:.92rem;padding:7px 10px;border:2px solid var(--rule);background:var(--sheet);color:var(--ink)}
.bk-filters input{flex:1 1 220px;max-width:320px}
.bk-filters .pt{padding:5px 10px}
.bk-board{display:grid;gap:10px}
.bk-ev{border:2px solid var(--rule);background:var(--sheet);display:grid}
.bk-ev-h{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:9px 12px;border-bottom:1px solid var(--line);background:var(--paper)}
.bk-ev-h b{font-family:var(--display);font-weight:800;font-size:1.15rem;text-transform:uppercase;display:flex;align-items:center;gap:7px}
.bk-ev-h b .lg{width:22px;height:22px}
.bk-ev-h small{font-family:var(--mono);font-size:.66rem;color:var(--muted);letter-spacing:.04em;text-align:right}
.bk-ev-h .bk-sub{font-family:var(--mono);font-size:.66rem;color:var(--muted);font-weight:400;text-transform:none}
.bk-lock{color:var(--red)!important;font-weight:600}
.bk-row{display:grid;grid-template-columns:minmax(0,150px) minmax(0,1fr);gap:8px;align-items:center;padding:7px 12px;border-bottom:1px solid var(--line)}
.bk-row:last-child{border-bottom:0}
.bk-row>span{font-family:var(--mono);font-size:.68rem;letter-spacing:.04em;text-transform:uppercase;color:var(--muted)}
.bk-sels{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:6px}
.bk-o{appearance:none;display:flex;justify-content:space-between;align-items:center;gap:8px;padding:8px 10px;border:1.5px solid var(--rule);background:var(--sheet);color:var(--ink);font:inherit;font-size:.86rem;cursor:pointer;border-radius:4px;text-align:left;min-width:0}
.bk-o span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bk-o b{font-family:var(--mono);font-size:.86rem;color:var(--blue);flex:none}
.bk-o:hover{background:var(--paper)}
.bk-o.on{background:var(--blue);border-color:var(--blue);color:#fff}.bk-o.on b{color:#fff}
.bk-o:disabled{opacity:.4;cursor:not-allowed}
.bk-more{appearance:none;justify-self:center;font-family:var(--mono);font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;padding:9px 18px;border:2px solid var(--rule);background:var(--sheet);color:var(--ink);cursor:pointer}
/* slip */
.bk-slip{position:sticky;top:12px;border:3px solid var(--rule);background:var(--sheet);display:grid;align-content:start}
.bk-sh{display:flex;justify-content:space-between;align-items:center;padding:10px 12px;background:var(--ink);color:var(--sheet)}
.bk-sh b{font-family:var(--display);font-size:1.25rem;text-transform:uppercase;letter-spacing:.03em}
.bk-sh em{font-style:normal;font-family:var(--mono);font-size:.74rem}
.bk-sb{display:grid;gap:10px;padding:12px}
.bk-empty{font-size:.88rem;color:var(--muted)}
.bk-leg{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:8px;align-items:start;padding-bottom:8px;border-bottom:1px dashed var(--line)}
.bk-leg b{display:block;font-size:.9rem}
.bk-leg small{display:block;font-family:var(--mono);font-size:.64rem;color:var(--muted)}
.bk-leg .num{font-family:var(--mono);font-weight:600;color:var(--blue)}
.bk-x{appearance:none;border:0;background:none;font-size:1.1rem;line-height:1;color:var(--muted);cursor:pointer;padding:0 2px}
.bk-tot{display:flex;justify-content:space-between;font-family:var(--mono);font-size:.8rem}
.bk-stake{display:grid;gap:6px}
.bk-stake label{font-family:var(--mono);font-size:.64rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.bk-stake input{font:inherit;font-size:1.2rem;font-family:var(--mono);padding:8px 10px;border:2px solid var(--rule);background:var(--sheet);color:var(--ink);width:100%}
.bk-chips{display:flex;gap:4px}.bk-chips button{flex:1;appearance:none;font-family:var(--mono);font-size:.72rem;padding:6px 0;border:1.5px solid var(--rule);background:var(--paper);color:var(--ink);cursor:pointer}
.bk-win{display:flex;justify-content:space-between;align-items:baseline;padding:10px;background:var(--paper)}
.bk-win span{font-family:var(--mono);font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.bk-win b{font-family:var(--display);font-size:1.8rem;color:var(--blue);line-height:1}
.bk-place{appearance:none;font-family:var(--display);font-weight:900;font-size:1.25rem;text-transform:uppercase;letter-spacing:.04em;padding:12px;border:0;background:var(--blue);color:#fff;cursor:pointer;border-radius:4px}
.bk-place:disabled{background:var(--silver);color:var(--muted);cursor:not-allowed}
.bk-msg{font-size:.84rem}.bk-msg.err{color:var(--red)}.bk-msg.ok{color:var(--blue);font-weight:600}
/* lists */
.bk-ticket{border:2px solid var(--rule);background:var(--sheet);display:grid}
.bk-ticket+.bk-ticket{margin-top:10px}
.bk-th{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:8px 12px;border-bottom:1px solid var(--line);background:var(--paper)}
.bk-th>span{display:flex;align-items:center;gap:7px;font-weight:600}
.bk-th .lg{width:22px;height:22px}
.bk-th em{font-style:normal;font-family:var(--mono);font-size:.72rem}
.bk-tl{display:grid;gap:4px;padding:8px 12px;font-size:.86rem}
.bk-tl div{display:flex;justify-content:space-between;gap:10px}
.bk-tl i{font-style:normal;font-family:var(--mono);font-size:.78rem;color:var(--muted)}
.bk-tag{font-family:var(--mono);font-size:.64rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;padding:2px 7px;border-radius:2px}
.bk-tag.won{background:var(--blue);color:#fff}.bk-tag.lost{background:var(--red);color:#fff}.bk-tag.push,.bk-tag.open{background:var(--silver);color:var(--ink)}.bk-tag.locked{background:var(--ink);color:var(--sheet)}
.bk-r-w{color:var(--blue)}.bk-r-l{color:var(--red)}
.bk-cancel{appearance:none;font-family:var(--mono);font-size:.66rem;text-transform:uppercase;padding:3px 8px;border:1.5px solid var(--rule);background:var(--sheet);cursor:pointer}
.bk-note{font-size:.9rem;color:var(--muted)}
table.bk-tbl{width:100%;border-collapse:collapse;font-size:.88rem}
table.bk-tbl th{font-family:var(--mono);font-size:.62rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);text-align:left;padding:6px 8px;border-bottom:2px solid var(--rule)}
table.bk-tbl td{padding:7px 8px;border-bottom:1px solid var(--line)}
table.bk-tbl td.n,table.bk-tbl th.n{text-align:right;font-family:var(--mono)}
.bk-tm{display:flex;align-items:center;gap:7px;font-weight:600}.bk-tm .lg{width:22px;height:22px}
.bk-flip{font-family:var(--mono);font-size:.64rem;font-weight:600;background:var(--hi);color:var(--hi-ink);padding:2px 6px;margin-left:6px}
.bk-bar{display:none}
@media (max-width:900px){
  .bk-layout{grid-template-columns:minmax(0,1fr)}
  .bk-slip{position:fixed;left:0;right:0;bottom:0;top:auto;z-index:45;border-width:3px 0 0;max-height:78vh;overflow:auto;box-shadow:0 -6px 20px rgba(0,0,0,.25);transform:translateY(calc(100% - 52px));transition:transform .2s}
  .bk-slip.open{transform:none}
  .bk-slip.empty{display:none}
  .bk-sh{cursor:pointer;min-height:52px}
  .bk-row{grid-template-columns:minmax(0,1fr)}
  .bk-mt{flex:1;font-size:.84rem;padding:8px 4px}
  body.bk-has-slip .m-top{bottom:70px!important}
}
"""

SCRIPT = r"""<script>
(function(){
  var src=document.getElementById('bk-data');if(!src)return;
  var D=JSON.parse(src.textContent),B=D.board,T=D.teams,API=D.api,R=D.rules;
  var $=function(id){return document.getElementById(id)};
  function e(s){return String(s==null?'':s).replace(/[&<>"]/g,function(m){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]})}
  function load(k){try{return JSON.parse(localStorage.getItem(k)||'null')}catch(x){return null}}
  function me(){var m=load('fz-team');return m&&m.team&&m.key?m:null}
  function od(a){return a>0?'+'+a:String(a)}
  function dec(a){return a>0?1+a/100:1+100/Math.abs(a)}
  function crest(t){return t?'<i class="lg lg-'+t+'" aria-hidden="true"></i>':''}
  function nm(t){return T[t]||('Team '+t)}
  function when(iso){var d=new Date(iso);return d.toLocaleString(undefined,{weekday:'short',hour:'numeric',minute:'2-digit'})}
  function locked(iso){return Date.now()>=Date.parse(iso)}
  var S=null,slip=[],grp='props',q='',pos='',own='',shown=30,stake='',msg='',busy=false;
  if(!B){$('bk-board').innerHTML='<p class="bk-note">The board for next week posts with Tuesday\'s paper.</p>'}
  // index every selection
  var IX={};
  if(B)['nfl','league','props'].forEach(function(g){(B[g]||[]).forEach(function(ev){ev.markets.forEach(function(mk){mk.sel.forEach(function(s){
    IX[s.id]={s:s,mk:mk,ev:ev,g:g}})})})});
  function mkey(id){return id.split('|').slice(0,2).join('|')}
  function evname(x){return x.g==='props'?x.ev.name:x.ev.title}
  // ---- server ----
  function refresh(){
    if(!API)return;
    fetch(API).then(function(r){return r.json()}).then(function(r){if(r.ok){S=r;drawMe();drawLive()}}).catch(function(){});
  }
  function call(body){return fetch(API,{method:'POST',headers:{'Content-Type':'text/plain;charset=utf-8'},body:JSON.stringify(body)}).then(function(r){return r.json()}).then(function(r){if(r.state){S=r.state;drawMe();drawLive()}return r})}
  function myBets(t){return ((S&&S.bets)||[]).filter(function(b){return b.team===t&&+b.week===B.week&&b.status!=='cancelled'})}
  function left(){var m=me();if(!m)return R.stake;return Math.max(0,R.stake-myBets(m.team).reduce(function(s,b){return s+(+b.stake)},0))}
  function betsOn(){return !!(S&&S.rules&&S.rules.betting)}
  // ---- header: who's betting ----
  function drawMe(){
    var m=me(),h='';
    if(!API)h='<span>Betting opens soon: the league office is being set up.</span>';
    else if(S&&!betsOn())h='<span>Betting opens when the commissioner updates the league office. You can browse the board now.</span>';
    else if(!m)h='<span>Sign this phone in to your team on the <a href="#proposals" data-tab="proposals">Rule Changes</a> tab to place bets. Browse freely.</span>';
    else h='<span>'+crest(m.team)+' Betting as <b>'+e(nm(m.team))+'</b></span><span class="bk-bank">'+left()+' of '+R.stake+' pts left to stake · week '+B.week+'</span>';
    $('bk-me').innerHTML=h;
    var a=$('bk-me').querySelector('a[data-tab]');if(a)a.addEventListener('click',function(ev){ev.preventDefault();var b=document.getElementById('tab-props');if(b)b.click()});
    drawSlip();
  }
  // ---- board ----
  function selBtn(s){var on=slip.indexOf(s.id)>=0,x=IX[s.id],lk=locked(x.ev.lock);
    return '<button type="button" class="bk-o'+(on?' on':'')+'" data-s="'+e(s.id)+'"'+(lk?' disabled':'')+' aria-pressed="'+on+'"><span>'+e(s.name)+'</span><b>'+od(s.odds)+'</b></button>'}
  function evCard(ev,g){
    var lk=locked(ev.lock),head;
    if(g==='props')head='<b>'+crest(ev.owner)+e(ev.name)+' <span class="bk-sub">'+e(ev.pos)+' · '+e(ev.team)+' '+e(ev.opp)+' · proj '+ev.proj+'</span></b>';
    else if(g==='league')head='<b>'+crest(ev.away)+e(nm(ev.away))+' <span class="bk-sub">@</span> '+crest(ev.home)+e(nm(ev.home))+'</b>';
    else head='<b>'+e(ev.away)+' <span class="bk-sub">@</span> '+e(ev.home)+'</b>';
    var sub=g==='league'?'proj '+ev.proj[0]+'–'+ev.proj[1]+' · ':'';
    return '<div class="bk-ev"><div class="bk-ev-h">'+head+'<small class="'+(lk?'bk-lock':'')+'">'+(lk?'Locked':sub+'locks '+e(when(ev.lock)))+'</small></div>'+
      ev.markets.map(function(mk){return '<div class="bk-row"><span>'+e(mk.label)+'</span><div class="bk-sels">'+mk.sel.map(selBtn).join('')+'</div></div>'}).join('')+'</div>';
  }
  function drawFilters(){
    var f=$('bk-filters');
    if(grp!=='props'){f.innerHTML='';f.hidden=true;return}
    f.hidden=false;
    var teams=Object.keys(T).map(Number).sort(function(a,b){return a-b});
    f.innerHTML='<input type="search" id="bk-q" placeholder="Find a player…" autocomplete="off" value="'+e(q)+'">'+
      ['','QB','RB','WR','TE'].map(function(p){return '<button type="button" class="pt" data-p="'+p+'" aria-pressed="'+(pos===p)+'">'+(p||'All')+'</button>'}).join('')+
      '<select id="bk-own"><option value="">Every player</option><option value="me"'+(own==='me'?' selected':'')+'>My team</option><option value="fa"'+(own==='fa'?' selected':'')+'>Free agents</option>'+
      teams.map(function(t){return '<option value="'+t+'"'+(own===String(t)?' selected':'')+'>'+e(nm(t))+'</option>'}).join('')+'</select>';
    $('bk-q').addEventListener('input',function(){q=this.value;shown=30;drawBoard(true)});
    f.querySelectorAll('.pt').forEach(function(b){b.addEventListener('click',function(){pos=b.dataset.p;shown=30;drawFilters();drawBoard()})});
    $('bk-own').addEventListener('change',function(){own=this.value;shown=30;drawBoard()});
  }
  function drawBoard(keepFocus){
    if(!B)return;
    var list=B[grp]||[],h='';
    if(grp==='props'){
      var t=q.trim().toLowerCase(),m=me();
      list=list.filter(function(ev){return (!pos||ev.pos===pos)&&(!t||ev.name.toLowerCase().indexOf(t)>=0)&&
        (!own||(own==='fa'?!ev.owner:own==='me'?(m&&ev.owner===m.team):String(ev.owner)===own))});
      var n=list.length;list=list.slice(0,shown);
      h=list.map(function(ev){return evCard(ev,'props')}).join('')+(n>shown?'<button type="button" class="bk-more" id="bk-more">Show more ('+(n-shown)+')</button>':'')+(n?'':'<p class="bk-note">No players match.</p>');
    } else h=list.length?list.map(function(ev){return evCard(ev,grp)}).join(''):'<p class="bk-note">No games on the board.</p>';
    $('bk-board').innerHTML=h;
    var mb=$('bk-more');if(mb)mb.addEventListener('click',function(){shown+=30;drawBoard()});
  }
  document.addEventListener('click',function(ev){
    var b=ev.target.closest&&ev.target.closest('.bk-o');if(!b)return;
    var id=b.dataset.s,i=slip.indexOf(id);
    if(i>=0)slip.splice(i,1);
    else{
      var k=mkey(id);slip=slip.filter(function(x){return mkey(x)!==k});       // other side of the same market: swap
      if(slip.length>=R.legs){msg='Up to '+R.legs+' legs per slip.';drawSlip();return}
      slip.push(id);msg='';
    }
    drawBoard();drawSlip();
  });
  document.querySelectorAll('.bk-mt').forEach(function(b){b.addEventListener('click',function(){grp=b.dataset.g;
    document.querySelectorAll('.bk-mt').forEach(function(x){x.setAttribute('aria-selected',x===b?'true':'false')});drawFilters();drawBoard()})});
  // ---- slip ----
  function odds(){return slip.reduce(function(d,id){return d*dec(IX[id].s.odds)},1)}
  function amer(d){return d>=2?'+'+Math.round((d-1)*100):'-'+Math.round(100/(d-1))}
  function drawSlip(){
    var el=$('bk-slip'),m=me(),n=slip.length;
    el.classList.toggle('empty',!n);document.body.classList.toggle('bk-has-slip',!!n);
    var d=odds(),st=+stake||0,win=Math.min(R.win,st*(d-1));
    var h='<div class="bk-sh" id="bk-sh"><b>Bet slip'+(n?' ('+n+')':'')+'</b><em>'+(n?(n>1?n+'-leg parlay · ':'')+amer(d):'')+'</em></div><div class="bk-sb">';
    if(!n)h+='<p class="bk-empty">Tap any odds to add a leg. Add more legs to build a parlay.</p>';
    else{
      h+=slip.map(function(id){var x=IX[id];return '<div class="bk-leg"><div><b>'+e(x.s.name)+'</b><small>'+e(x.mk.label)+' · '+e(evname(x))+'</small></div><span class="num">'+od(x.s.odds)+'</span><button type="button" class="bk-x" data-x="'+e(id)+'" aria-label="Remove">×</button></div>'}).join('');
      var lf=left();
      h+='<div class="bk-stake"><label for="bk-st">Stake (points) · '+lf+' left this week</label><input id="bk-st" type="number" inputmode="decimal" min="1" max="'+lf+'" step="1" placeholder="0" value="'+e(stake)+'">'+
        '<div class="bk-chips">'+[1,2,3].map(function(v){return '<button type="button" data-c="'+v+'">'+v+'</button>'}).join('')+'<button type="button" data-c="'+lf+'">Max</button></div></div>'+
        '<div class="bk-win"><span>To win</span><b class="num">+'+(Math.round(win*10)/10)+'</b></div>';
      var can=API&&betsOn()&&m&&st>=1&&st<=lf&&!busy;
      h+='<button type="button" class="bk-place" id="bk-place"'+(can?'':' disabled')+'>'+(busy?'Placing…':!m?'Sign in to bet':!betsOn()?'Betting not open yet':st>lf?'Over your '+R.stake+' pts':'Place bet')+'</button>';
      if(win>=R.win)h+='<p class="bk-empty">Payout capped at '+R.win+' points.</p>';
    }
    if(msg)h+='<p class="bk-msg'+(/placed/i.test(msg)?' ok':' err')+'">'+e(msg)+'</p>';
    el.innerHTML=h+'</div>';
    var sh=$('bk-sh');if(sh)sh.addEventListener('click',function(){el.classList.toggle('open')});
    el.querySelectorAll('.bk-x').forEach(function(b){b.addEventListener('click',function(){slip.splice(slip.indexOf(b.dataset.x),1);drawBoard();drawSlip()})});
    el.querySelectorAll('[data-c]').forEach(function(b){b.addEventListener('click',function(){stake=b.dataset.c;drawSlip()})});
    var si=$('bk-st');if(si)si.addEventListener('input',function(){stake=si.value;var d=odds(),st=+stake||0;
      el.querySelector('.bk-win b').textContent='+'+Math.round(Math.min(R.win,st*(d-1))*10)/10;
      var pb=$('bk-place'),lf=left(),m=me();pb.disabled=!(API&&betsOn()&&m&&st>=1&&st<=lf);pb.textContent=!m?'Sign in to bet':st>lf?'Over your '+R.stake+' pts':'Place bet'});
    var pb=$('bk-place');if(pb)pb.addEventListener('click',function(){
      var m=me();if(!m)return;busy=true;drawSlip();
      call({action:'bet',team:m.team,key:m.key,week:B.week,stake:+stake,legs:slip.slice()}).then(function(r){busy=false;
        if(r.ok){slip=[];stake='';msg='Bet placed. Good luck.';drawBoard()}else msg=r.error||'Could not place the bet.';drawSlip()})
      .catch(function(){busy=false;msg='The league office isn’t answering. Try again in a minute.';drawSlip()});
    });
  }
  // ---- everyone's slips this week ----
  function ticket(b,showCancel){
    var lk=b.legs.some(function(l){return locked(l.lock)}),st=lk?'locked':'open';
    return '<div class="bk-ticket"><div class="bk-th"><span>'+crest(b.team)+e(nm(b.team))+'</span><em>'+b.stake+' pts · '+(b.legs.length>1?b.legs.length+'-leg · '+amer(+b.dec):od(b.legs[0].odds))+' · to win +'+(Math.round(b.win*10)/10)+'</em>'+
      (showCancel&&!lk?'<button type="button" class="bk-cancel" data-cancel="'+e(b.id)+'">Cancel</button>':'<span class="bk-tag '+st+'">'+st+'</span>')+'</div>'+
      '<div class="bk-tl">'+b.legs.map(function(l){return '<div><span>'+e(l.desc)+'</span><i>'+od(l.odds)+'</i></div>'}).join('')+'</div></div>';
  }
  function drawLive(){
    var el=$('bk-live');if(!B){el.innerHTML='';return}
    if(!S||!S.bets){el.innerHTML='<p class="bk-note">'+(API?'Loading the league office…':'No bets yet.')+'</p>';return}
    var m=me(),bs=S.bets.filter(function(b){return +b.week===B.week&&b.status!=='cancelled'});
    if(!bs.length){el.innerHTML='<p class="bk-note">No bets on the board yet for week '+B.week+'.</p>';return}
    bs.sort(function(a,b){return (m&&b.team===m.team)-(m&&a.team===m.team)||a.team-b.team});
    el.innerHTML=bs.map(function(b){return ticket(b,m&&b.team===m.team)}).join('');
    el.querySelectorAll('[data-cancel]').forEach(function(x){x.addEventListener('click',function(){var m=me();if(!m)return;
      call({action:'cancelbet',team:m.team,key:m.key,bet:x.dataset.cancel}).then(function(r){if(!r.ok)alert(r.error)})})});
  }
  // ---- results and standings (graded in the pipeline) ----
  function drawResults(){
    var r=D.results,el=$('bk-res');
    if(!r){el.innerHTML='<p class="bk-note">Payouts post with the paper the Tuesday after each betting week. The first board is week '+(B?B.week:'')+'.</p>';return}
    var h='';
    if(!r.slips.length)h+='<p class="bk-note">Nobody bet in week '+r.week+'.</p>';
    h+=r.slips.map(function(s){return '<div class="bk-ticket"><div class="bk-th"><span>'+crest(s.team)+e(nm(s.team))+'</span><em>'+s.stake+' pts staked</em><span class="bk-tag '+s.result+'">'+(s.result==='won'?'+'+s.net:s.result==='lost'?s.net:'push')+'</span></div>'+
      '<div class="bk-tl">'+s.legs.map(function(l){var c=l.r==='w'?'bk-r-w':l.r==='l'?'bk-r-l':'';return '<div><span class="'+c+'">'+(l.r==='w'?'✓ ':l.r==='l'?'✗ ':'– ')+e(l.desc)+'</span><i>'+od(l.odds)+'</i></div>'}).join('')+'</div></div>'}).join('');
    if(r.games.length)h+='<'+'table class="bk-tbl" style="margin-top:14px"><'+'thead><'+'tr><'+'th>Game</th><'+'th class="n">Real</th><'+'th class="n">With bets</th></tr></thead><'+'tbody>'+r.games.map(function(g){
      var flip=g.real!==g.with_bets;
      return '<'+'tr><'+'td><span class="bk-tm">'+crest(g.away)+e(nm(g.away))+' @ '+crest(g.home)+e(nm(g.home))+(flip?'<span class="bk-flip">FLIPPED</span>':'')+'</span></td><'+'td class="n">'+g.ap.toFixed(2)+' – '+g.hp.toFixed(2)+'</td><'+'td class="n">'+g.ab.toFixed(2)+' – '+g.hb.toFixed(2)+'</td></tr>'}).join('')+'</tbody></table>';
    el.innerHTML=h;
  }
  function drawStand(){
    var el=$('bk-st'),s=D.stand;
    if(!s||!s.length){el.innerHTML='<p class="bk-note">The side standings start once the first betting week is graded.</p>';return}
    s=s.slice().sort(function(a,b){return (b.bw-a.bw)||(b.net-a.net)});
    el.innerHTML='<'+'table class="bk-tbl"><'+'thead><'+'tr><'+'th>Team</th><'+'th class="n">Real</th><'+'th class="n">With bets</th><'+'th class="n">Net from bets</th><'+'th class="n">Slips won</th></tr></thead><'+'tbody>'+s.map(function(r){
      return '<'+'tr><'+'td><span class="bk-tm">'+crest(r.team)+e(nm(r.team))+'</span></td><'+'td class="n">'+r.w+'–'+r.l+(r.t?'–'+r.t:'')+'</td><'+'td class="n"><b>'+r.bw+'–'+r.bl+(r.bt?'–'+r.bt:'')+'</b></td><'+'td class="n '+(r.net>0?'bk-r-w':r.net<0?'bk-r-l':'')+'">'+(r.net>0?'+':'')+r.net.toFixed(1)+'</td><'+'td class="n">'+r.won+' / '+r.slips+'</td></tr>'}).join('')+'</tbody></table>';
  }
  drawMe();drawFilters();drawBoard();drawLive();drawResults();drawStand();
  refresh();setInterval(function(){if(!document.getElementById('betting').hidden)refresh()},45000);
  var tb=document.getElementById('tab-bets');if(tb)tb.addEventListener('click',refresh);
})();
</script>"""
