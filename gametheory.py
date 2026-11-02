"""Game theory for the owner team (league.json owner_team), trades excluded.

Usage: python3 gametheory.py [W]   (W = last finished week; default = newest data/weekK_raw.txt)
Writes data/gametheory_weekW.json and prints a summary.

Reads only league data already in the repo:
- data/espn_settings.json   waiver type/reset/process days, move limits, tie rules
- data/schedule.json        regular-season length, playoff teams, remaining matchups
- data/weekK_raw.txt        scores, rosters, transactions
- data/players/waivers.json waiver order snapshots

Three levers are measured:
1. Leverage: how much each remaining game moves the owner's playoff and first-round-bye chances
   (Monte Carlo, same team-strength model as the site's Playoff Odds; ties go to points for).
2. Waivers: what a claim costs under these settings and how every manager uses waivers / streams K and D/ST.
3. Denial: for each remaining opponent, how often they stream a K or D/ST, i.e. how much grabbing
   the best streamer first in free agency hurts them.
"""
import glob, json, random, re, statistics as st, sys
from collections import Counter, defaultdict

from facts import load

LG = json.load(open("league.json"))
ME = LG["owner_team"]
SET = json.load(open("data/espn_settings.json"))
SCH = json.load(open("data/schedule.json"))
REG, POT = SCH["regweeks"], SCH["playoff_teams"]
NBYE = 2 if POT == 6 else 0          # 6 teams in a 3-week bracket: seeds 1-2 skip round one


def weeks_available():
    return sorted(int(re.search(r"week(\d+)_raw", f).group(1)) for f in glob.glob("data/week*_raw.txt"))


def season(W):
    S = {}
    for k in range(1, W + 1):
        _m, _sl, teams, sched, ros, tx, _ = load(f"data/week{k}_raw.txt")
        sc, opp = {}, {}
        for g in sched:
            if g["wk"] == k and g["away"]:
                sc[g["home"]], sc[g["away"]] = g["hp"], g["ap"]
                opp[g["home"]], opp[g["away"]] = g["away"], g["home"]
        S[k] = dict(score=sc, opp=opp, ros=ros, tx=tx, teams=teams)
    return S


# ---------------------------------------------------------------- 1. leverage
def leverage(S, W, NS=20000, seed=7):
    teams = sorted(S[W]["score"])
    wk = range(1, W + 1)
    allw = [S[k]["score"][t] for k in wk for t in teams]
    lmean = st.mean(allw)
    mu = {t: (sum(S[k]["score"][t] for k in wk) + 3 * lmean) / (W + 3) for t in teams}
    sig = st.pstdev([S[k]["score"][t] - st.mean(S[j]["score"][t] for j in wk) for k in wk for t in teams])
    w0 = {t: sum(S[k]["score"][t] > S[k]["score"][S[k]["opp"][t]] for k in wk) for t in teams}
    pf0 = {t: sum(S[k]["score"][t] for k in wk) for t in teams}
    left = [(g["wk"], g["home"], g["away"]) for g in SCH["games"] if W < g["wk"] <= REG]
    mine = {w: (a if h == ME else h) for w, h, a in left if ME in (h, a)}
    rng = random.Random(seed)
    # per remaining owner week: [n, playoffs, bye] split by win / loss
    acc = {w: {True: [0, 0, 0], False: [0, 0, 0]} for w in mine}
    tot = [0, 0, 0]
    seeds = Counter()
    for _ in range(NS):
        wv, pv, res = dict(w0), dict(pf0), {}
        for w, h, a in left:
            sh, sa = rng.gauss(mu[h], sig), rng.gauss(mu[a], sig)
            pv[h] += sh; pv[a] += sa
            win = h if sh > sa else a
            wv[win] += 1
            if ME in (h, a):
                res[w] = win == ME
        order = sorted(teams, key=lambda t: (-wv[t], -pv[t]))
        s = order.index(ME) + 1
        seeds[s] += 1
        po, by = s <= POT, s <= NBYE
        tot[0] += 1; tot[1] += po; tot[2] += by
        for w, won in res.items():
            a = acc[w][won]; a[0] += 1; a[1] += po; a[2] += by
    rows = []
    for w in sorted(mine):
        o = mine[w]
        pw = acc[w][True][0] / NS
        f = lambda won, i: acc[w][won][i] / max(acc[w][won][0], 1)
        rows.append(dict(week=w, opp=o, p_win=round(pw, 3),
                         po_if_win=round(f(True, 1), 3), po_if_loss=round(f(False, 1), 3),
                         bye_if_win=round(f(True, 2), 3), bye_if_loss=round(f(False, 2), 3),
                         swing_po=round(f(True, 1) - f(False, 1), 3), swing_bye=round(f(True, 2) - f(False, 2), 3)))
    stand = sorted(teams, key=lambda t: (-w0[t], -pf0[t]))
    return dict(p_playoffs=round(tot[1] / NS, 3), p_bye=round(tot[2] / NS, 3),
                seed_dist={s: round(seeds[s] / NS, 3) for s in sorted(seeds)},
                record=f"{w0[ME]}-{W - w0[ME]}", pf=round(pf0[ME], 2), rank=stand.index(ME) + 1,
                standings=[dict(team=t, w=w0[t], pf=round(pf0[t], 1), mu=round(mu[t], 1)) for t in stand],
                sigma=round(sig, 1), weeks=rows)


# ---------------------------------------------------------------- 2/3. waivers, streaming, denial
def moves(S, W):
    per = defaultdict(lambda: Counter())
    pos_of = {}
    for k in range(1, W + 1):
        for t, pl in S[k]["ros"].items():
            for p in pl:
                pos_of[p["name"]] = p["pos"]
    for k in range(1, W + 1):
        for x in S[k]["tx"]:
            if x["kind"] == "trade":
                continue                      # trades excluded by request
            c = per[x["team"]]
            for m in x["moves"]:
                if not m.startswith("ADD:"):
                    continue
                name = m[4:]
                pos = "D/ST" if name.endswith("D/ST") else pos_of.get(name, "?")
                c["adds"] += 1
                c["waiver" if x["kind"] == "waiver" else "fa"] += 1
                if pos in ("K", "D/ST"):
                    c["stream_" + pos] += 1
                c["wk%d" % k] += 1
    out = {}
    for t in sorted(S[W]["score"]):
        c = per[t]
        out[t] = dict(adds=c["adds"], waiver=c["waiver"], fa=c["fa"],
                      kdst=c["stream_K"] + c["stream_D/ST"], dst=c["stream_D/ST"], k=c["stream_K"],
                      active_weeks=sum(1 for k in range(1, W + 1) if c["wk%d" % k]),
                      kdst_per_week=round((c["stream_K"] + c["stream_D/ST"]) / W, 2))
    return out


def waiver_rules():
    a = SET["acquisitionSettings"]
    hist = json.load(open("data/players/waivers.json"))
    mypri = [(h["scoringPeriod"], h["order"].get(str(ME))) for h in hist.get("history", [])]
    return dict(type=a["acquisitionType"], reset_weekly=a["waiverOrderReset"], hours=a["waiverHours"],
                process_days=a["waiverProcessDays"], season_add_limit=a["acquisitionLimit"],
                weekly_add_limit=a["matchupAcquisitionLimit"], faab=a["isUsingAcquisitionBudget"],
                tie_rule=SET["scoringSettings"]["matchupTieRule"],
                my_priority_now=hist["current"]["order"].get(str(ME)), my_priority_history=mypri)


def main():
    have = weeks_available()
    W = int(sys.argv[1]) if len(sys.argv) > 1 else have[-1]
    S = season(W)
    lev = leverage(S, W)
    mv = moves(S, W)
    wr = waiver_rules()
    deny = [dict(week=r["week"], opp=r["opp"], opp_kdst_per_week=mv[r["opp"]]["kdst_per_week"]) for r in lev["weeks"]]
    out = dict(week=W, me=ME, short=LG["short_names"], rules=wr, leverage=lev, moves=mv, denial=deny)
    json.dump(out, open(f"data/gametheory_week{W}.json", "w"), indent=1)
    sn = LG["short_names"]
    print(f"Through week {W}: {sn[str(ME)]} {lev['record']} (rank {lev['rank']}), PF {lev['pf']}")
    print(f"Playoffs {lev['p_playoffs']:.1%}  bye {lev['p_bye']:.1%}  sigma {lev['sigma']}")
    for r in lev["weeks"]:
        print(f" wk{r['week']:>2} vs {sn[str(r['opp'])]:<16} win {r['p_win']:.0%}  playoffs {r['po_if_win']:.0%}/{r['po_if_loss']:.0%}"
              f" (swing {r['swing_po']:+.0%})  bye {r['bye_if_win']:.0%}/{r['bye_if_loss']:.0%} (swing {r['swing_bye']:+.0%})"
              f"  opp K/DST adds/wk {mv[r['opp']]['kdst_per_week']}")
    print("rules", json.dumps(wr))
    for t, m in mv.items():
        print(f" {sn[str(t)]:<16} {m}")


if __name__ == "__main__":
    main()
