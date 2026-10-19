"""The Daily Fantasizer: story finder.
Usage: python3 facts.py data/week5_raw.txt
Reads the raw dump from extract.js and writes data/weekN_facts.json and data/weekN_facts.md.
Code does all the math; the writer only uses numbers from these files."""
import json, sys
from collections import defaultdict

FLEX_ELIG = {"FLEX": {"RB", "WR", "TE"}, "RB/WR": {"RB", "WR"}, "WR/TE": {"WR", "TE"}, "OP": {"QB", "RB", "WR", "TE"}}


def load(path):
    meta, slots, teams, sched, rosters, tx, logo_urls = {}, {}, {}, [], defaultdict(list), [], {}
    sec, cur = None, None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n").strip()
        if not line: continue
        if line.startswith("META|"):
            meta = dict(kv.split("=", 1) for kv in line.split("|")[1:]); continue
        if line.startswith("SLOTS|"):
            slots = {k: int(v) for k, v in (s.split(":") for s in line[6:].split(","))}; continue
        if line in ("TEAMS", "SCHED", "ROSTERS", "TX", "LOGOURLS"):
            sec = line; continue
        p = line.split("|")
        if sec == "TEAMS":
            teams[int(p[0])] = dict(id=int(p[0]), name=p[1], abbrev=p[2], owner=p[3])
        elif sec == "SCHED":
            sched.append(dict(wk=int(p[0]), home=int(p[1]), hp=float(p[2]), away=int(p[3]), ap=float(p[4]), winner=p[5]))
        elif sec == "ROSTERS":
            if line.startswith("#"): cur = int(line[1:]); continue
            rosters[cur].append(dict(name=p[0], pos=p[1], slot=p[2], pts=float(p[3]), proj=float(p[4])))
        elif sec == "TX":
            tx.append(dict(kind={"F": "free agent", "W": "waiver", "T": "trade"}[p[0]], team=int(p[1]), moves=p[2].split(",") if p[2] else []))
        elif sec == "LOGOURLS":
            logo_urls[int(p[0])] = p[1]
    meta["week"] = int(meta["week"])
    return meta, slots, teams, sched, rosters, tx, logo_urls


def optimal(roster, slots):
    pool = sorted([p for p in roster if p["slot"] != "IR"], key=lambda p: -p["pts"])
    used, lineup = set(), []
    for slot, n in slots.items():               # single-position slots first
        if slot in FLEX_ELIG: continue
        for p in [p for p in pool if p["pos"] == slot and p["name"] not in used][:n]:
            used.add(p["name"]); lineup.append(p)
    for slot in sorted((s for s in slots if s in FLEX_ELIG), key=lambda s: len(FLEX_ELIG[s])):
        for _ in range(slots[slot]):
            c = next((p for p in pool if p["pos"] in FLEX_ELIG[slot] and p["name"] not in used), None)
            if c: used.add(c["name"]); lineup.append(c)
    return round(sum(p["pts"] for p in lineup), 2), lineup


def main(path):
    meta, slots, teams, sched, rosters, tx, logo_urls = load(path)
    W = meta["week"]
    if meta.get("complete") != "1":
        print(f"WARNING: week {W} is not final on ESPN (complete=0). Wait until Monday/Tuesday games finish.")
    played = [g for g in sched if g["wk"] <= W and g["away"]]

    # ---- season records computed from the schedule (not ESPN's live record) ----
    rec = {t: dict(w=0, l=0, t=0, pf=0.0, pa=0.0, results=[], weekly={}) for t in teams}
    for g in sorted(played, key=lambda g: g["wk"]):
        for me, op, mp, opp in ((g["home"], g["away"], g["hp"], g["ap"]), (g["away"], g["home"], g["ap"], g["hp"])):
            r = rec[me]; r["pf"] += mp; r["pa"] += opp; r["weekly"][g["wk"]] = mp
            res = "W" if mp > opp else "L" if mp < opp else "T"
            r[{"W": "w", "L": "l", "T": "t"}[res]] += 1; r["results"].append(res)
    for r in rec.values():
        r["pf"], r["pa"] = round(r["pf"], 2), round(r["pa"], 2)
        last = r["results"][-1]; n = 0
        for x in reversed(r["results"]):
            if x != last: break
            n += 1
        r["streak"] = f"{last}{n}"

    weeks = sorted({g["wk"] for g in played})
    nteams = len(teams)
    allplay = defaultdict(int)
    for wk in weeks:
        s = {t: rec[t]["weekly"][wk] for t in teams if wk in rec[t]["weekly"]}
        for t in s: allplay[t] += sum(s[t] > s[o] for o in s if o != t)
    ap_games = len(weeks) * (nteams - 1)

    # ---- this week ----
    TF = {}
    for tid, roster in rosters.items():
        starters = [p for p in roster if p["slot"] not in ("BE", "IR")]
        actual = round(sum(p["pts"] for p in starters), 2)
        opt, opt_lineup = optimal(roster, slots)
        names = {p["name"] for p in opt_lineup}
        bench = [p for p in roster if p["slot"] == "BE"]
        prev = [v for k, v in rec[tid]["weekly"].items() if k < W]
        TF[tid] = dict(week_pts=actual, optimal=opt, left_on_bench=round(opt - actual, 2),
                       should_have_started=[(p["name"], p["pos"], p["pts"]) for p in opt_lineup if p["slot"] == "BE"],
                       should_have_sat=[(p["name"], p["pos"], p["pts"]) for p in starters if p["name"] not in names],
                       started_zero_projection=[p["name"] for p in starters if p["proj"] == 0],
                       starters=sorted([(p["name"], p["pos"], p["slot"], p["pts"], p["proj"]) for p in starters], key=lambda x: -x[3]),
                       best_bench=max(bench, key=lambda p: p["pts"])["name"] + f" ({max(p['pts'] for p in bench)})" if bench else None,
                       season_high=bool(prev) and actual > max(prev), season_low=bool(prev) and actual < min(prev),
                       prev_high=max(prev) if prev else None, prev_low=min(prev) if prev else None)
    games = []
    for g in [g for g in sched if g["wk"] == W and g["away"]]:
        h, a = TF[g["home"]], TF[g["away"]]
        if abs(h["week_pts"] - g["hp"]) > .05 or abs(a["week_pts"] - g["ap"]) > .05:
            print(f"WARNING: starter sum mismatch in game {g} -> {h['week_pts']} / {a['week_pts']}")
        w_, l_ = (g["home"], g["away"]) if g["hp"] >= g["ap"] else (g["away"], g["home"])
        ws, ls = max(g["hp"], g["ap"]), min(g["hp"], g["ap"])
        games.append(dict(winner=w_, loser=l_, ws=ws, ls=ls, margin=round(ws - ls, 2), tie=g["hp"] == g["ap"],
                          loser_optimal=TF[l_]["optimal"], loser_optimal_would_win=TF[l_]["optimal"] > ws))
    # ---- upsets & heartbreakers (top of the paper; user, 2026-10-19) ----
    # Upset: the winner had fewer wins going into the week AND the loser was a top-N team going in
    # (standings = wins, then points for) or had at least `upset_win_gap` more wins.
    # Heartbreaker: margin under `heartbreaker_margin` points. A game can be both.
    try: LGc = json.load(open("league.json"))
    except (OSError, ValueError): LGc = {}
    UP_TOP, UP_GAP, HB = LGc.get("upset_top_n", 4), LGc.get("upset_win_gap", 2), LGc.get("heartbreaker_margin", 2)
    pre = {t: dict(w=sum(1 for wk, r in zip(sorted(rec[t]["weekly"]), rec[t]["results"]) if wk < W and r == "W"),
                   l=sum(1 for wk, r in zip(sorted(rec[t]["weekly"]), rec[t]["results"]) if wk < W and r == "L"),
                   t=sum(1 for wk, r in zip(sorted(rec[t]["weekly"]), rec[t]["results"]) if wk < W and r == "T"),
                   pf=sum(v for wk, v in rec[t]["weekly"].items() if wk < W)) for t in teams}
    pre_rank = {t: i + 1 for i, t in enumerate(sorted(teams, key=lambda t: (-pre[t]["w"], -pre[t]["pf"])))}
    upsets = []
    bo_game = max((g for g in games if not g["tie"]), key=lambda g: g["margin"], default=None)  # biggest margin (user, 2026-10-19)
    for g in games:
        w_, l_ = g["winner"], g["loser"]
        if g["tie"]: continue
        gap = pre[l_]["w"] - pre[w_]["w"]
        is_up = W > 1 and gap > 0 and (pre_rank[l_] <= UP_TOP or gap >= UP_GAP)
        is_hb = g["margin"] < HB
        is_bo = g is bo_game
        if not (is_up or is_hb or is_bo): continue
        benched = sorted(TF[l_]["should_have_started"], key=lambda x: -x[2])
        upsets.append(dict(winner=w_, loser=l_, ws=g["ws"], ls=g["ls"], margin=g["margin"], upset=is_up, heartbreaker=is_hb, blowout=is_bo,
                           win_gap=gap, w_pre=pre[w_], l_pre=pre[l_], w_rank_pre=pre_rank[w_], l_rank_pre=pre_rank[l_],
                           l_left_on_bench=TF[l_]["left_on_bench"], l_optimal=TF[l_]["optimal"],
                           loser_optimal_would_win=g["loser_optimal_would_win"], l_benched_star=benched[0] if benched else None,
                           w_now=f"{rec[w_]['w']}-{rec[w_]['l']}", l_now=f"{rec[l_]['w']}-{rec[l_]['l']}", l_streak=rec[l_]["streak"]))
    # banner order: upset + heartbreaker, upsets (bigger win gap first), heartbreakers (closest first), then the blowout
    upsets.sort(key=lambda u: (not (u["upset"] and u["heartbreaker"]), not u["upset"], not u["heartbreaker"], -u["win_gap"], u["margin"]))

    starters = [(t, p) for t, r in rosters.items() for p in r if p["slot"] not in ("BE", "IR")]
    benchp = [(t, p) for t, r in rosters.items() for p in r if p["slot"] == "BE"]
    wk_scores = {t: TF[t]["week_pts"] for t in TF}
    allscores = sorted(((v, t, wk) for t in teams for wk, v in rec[t]["weekly"].items()), reverse=True)
    league = dict(
        avg=round(sum(wk_scores.values()) / len(wk_scores), 2),
        high=max(wk_scores, key=wk_scores.get), low=min(wk_scores, key=wk_scores.get),
        closest=min(games, key=lambda g: g["margin"]), blowout=max(games, key=lambda g: g["margin"]),
        top_player=max(starters, key=lambda x: x[1]["pts"]), best_benched=max(benchp, key=lambda x: x[1]["pts"]),
        worst_busts=[(t, p["name"], p["pos"], p["proj"], p["pts"], round(p["pts"] - p["proj"], 1)) for t, p in sorted([x for x in starters if x[1]["proj"] > 0], key=lambda x: x[1]["pts"] - x[1]["proj"])[:8]],
        booms=[(t, p["name"], p["pos"], p["proj"], p["pts"], round(p["pts"] - p["proj"], 1)) for t, p in sorted(starters, key=lambda x: -(x[1]["pts"] - x[1]["proj"]))[:5]],
        most_left=max(TF, key=lambda t: TF[t]["left_on_bench"]), least_left=min(TF, key=lambda t: TF[t]["left_on_bench"]),
        total_left=round(sum(TF[t]["left_on_bench"] for t in TF), 2),
        all_play_week={t: sum(wk_scores[t] > wk_scores[o] for o in wk_scores if o != t) for t in wk_scores},
        season_high=[x for x in allscores if x[0] == allscores[0][0]], season_low=[x for x in allscores if x[0] == allscores[-1][0]],
    )
    season = {t: dict(**{k: v for k, v in rec[t].items() if k != "results"}, results="".join(rec[t]["results"]),
                      allplay=f"{allplay[t]}-{ap_games - allplay[t]}", allplay_w=allplay[t],
                      expected_wins=round(allplay[t] / (nteams - 1), 2), luck=round(rec[t]["w"] - allplay[t] / (nteams - 1), 2),
                      avg=round(rec[t]["pf"] / len(rec[t]["weekly"]), 1)) for t in teams}
    ranking = sorted(teams, key=lambda t: (-allplay[t], -rec[t]["pf"]))
    nxt = []
    for g in [g for g in sched if g["wk"] == W + 1 and g["away"]]:
        h, a = g["home"], g["away"]
        ra = {x: rec[x]["pf"] / len(rec[x]["weekly"]) for x in (h, a)}   # unrounded season averages
        fav, dog = (h, a) if ra[h] >= ra[a] else (a, h)
        nxt.append(dict(home=h, away=a, fav=fav, dog=dog,
                        spread=round((ra[fav] - ra[dog]) * 2) / 2,
                        ou=round((ra[h] + ra[a]) * 2) / 2))
    for t_ in tx:  # flag adds that are not on that team's roster for the week (may be post-game adds)
        names = {p["name"] for p in rosters.get(t_["team"], [])}
        t_["verified"] = all(m.split(":")[1] in names for m in t_["moves"] if m.startswith("ADD:"))

    F = dict(meta=meta, slots=slots, week=W, teams={t: dict(**teams[t], logo_url=logo_urls.get(t)) for t in teams},
             this_week=TF, games=games, upsets=upsets, league=league, season=season, ranking=ranking, next_week=nxt, transactions=tx)
    base = path.replace("_raw.txt", "")
    json.dump(F, open(base + "_facts.json", "w"), indent=1, default=str)

    # ---- readable digest for writing the copy ----
    N = lambda t: f"{teams[t]['name']} [{t}]"
    md = [f"# Week {W} facts — {meta.get('name')}", f"League avg {league['avg']} · total left on benches {league['total_left']}",
          f"High {N(league['high'])} {wk_scores[league['high']]} · Low {N(league['low'])} {wk_scores[league['low']]}",
          f"Season high(s): {[(v, N(t), 'wk'+str(w)) for v, t, w in league['season_high']]} · Season low(s): {[(v, N(t), 'wk'+str(w)) for v, t, w in league['season_low']]}",
          f"Top player: {league['top_player'][1]['name']} {league['top_player'][1]['pts']} ({N(league['top_player'][0])})",
          f"Best benched: {league['best_benched'][1]['name']} {league['best_benched'][1]['pts']} ({N(league['best_benched'][0])})", "", "## Games"]
    for g in sorted(games, key=lambda g: g["margin"]):
        md.append(f"- {N(g['winner'])} {g['ws']} def. {N(g['loser'])} {g['ls']} (margin {g['margin']}); loser best lineup {g['loser_optimal']}{' WOULD HAVE WON' if g['loser_optimal_would_win'] else ''}")
    md.append(f"\n## Upsets, heartbreakers & the blowout (the week's biggest news, under the stat tiles; upset = fewer wins going in and beat a top-{UP_TOP} team or one with {UP_GAP}+ more wins; heartbreaker = margin < {HB}; blowout = the week's biggest margin, always listed)")
    for u in upsets:
        tags = " + ".join(x for x, on in (("UPSET", u["upset"]), ("HEARTBREAKER", u["heartbreaker"]), ("BLOWOUT", u["blowout"])) if on)
        star = f"; benched {u['l_benched_star'][0]} ({u['l_benched_star'][2]})" if u["l_benched_star"] else ""
        md.append(f"- {tags}: {N(u['winner'])} (#{u['w_rank_pre']}, {u['w_pre']['w']}-{u['w_pre']['l']} going in, now {u['w_now']}) {u['ws']} def. "
                  f"{N(u['loser'])} (#{u['l_rank_pre']}, {u['l_pre']['w']}-{u['l_pre']['l']} going in, now {u['l_now']}, streak {u['l_streak']}) {u['ls']}, margin {u['margin']}; "
                  f"loser left {u['l_left_on_bench']} on bench (best {u['l_optimal']}{', WOULD HAVE WON' if u['loser_optimal_would_win'] else ''}){star}")
    md.append("\n## Teams this week")
    for t in sorted(TF, key=lambda t: -TF[t]["week_pts"]):
        x, s = TF[t], season[t]
        md.append(f"### {N(t)} — {teams[t]['owner']}\n- {x['week_pts']} pts (best {x['optimal']}, left {x['left_on_bench']}); all-play this week {league['all_play_week'][t]}-{nteams-1-league['all_play_week'][t]}"
                  f"{'; SEASON HIGH (prev '+str(x['prev_high'])+')' if x['season_high'] else ''}{'; SEASON LOW (prev '+str(x['prev_low'])+')' if x['season_low'] else ''}\n"
                  f"- Record {s['w']}-{s['l']}{'-'+str(s['t']) if s['t'] else ''} ({s['results']}), streak {s['streak']}, PF {s['pf']}, PA {s['pa']}, avg {s['avg']}, weekly {s['weekly']}, all-play {s['allplay']}, luck {s['luck']:+}\n"
                  f"- Starters: " + ", ".join(f"{n} {sl} {pts} (proj {pr})" for n, pos, sl, pts, pr in x["starters"]) +
                  f"\n- Should have started: {x['should_have_started']} · should have sat: {x['should_have_sat']} · zero-projection starters: {x['started_zero_projection']} · best bench: {x['best_bench']}")
    md.append("\n## Biggest misses vs projection\n" + "\n".join(f"- {n} ({pos}, {N(t)}): proj {pr}, scored {pts} ({d:+})" for t, n, pos, pr, pts, d in league["worst_busts"]))
    md.append("\n## Biggest beats vs projection\n" + "\n".join(f"- {n} ({pos}, {N(t)}): proj {pr}, scored {pts} ({d:+})" for t, n, pos, pr, pts, d in league["booms"]))
    md.append("\n## Pecking order (all-play)\n" + "\n".join(f"{i}. {N(t)} {season[t]['w']}-{season[t]['l']} all-play {season[t]['allplay']} PF {season[t]['pf']} luck {season[t]['luck']:+}" for i, t in enumerate(ranking, 1)))
    md.append("\n## Transactions\n" + "\n".join(f"- {N(x['team'])} {x['kind']}: {', '.join(x['moves'])}{'' if x['verified'] else '  (UNVERIFIED: add not on week roster, skip or check)'}" for x in tx))
    md.append(f"\n## Week {W+1} lines (season averages)\n" + "\n".join(f"- {N(n['fav'])} -{n['spread']} vs {N(n['dog'])}, O/U {n['ou']}" for n in nxt))
    open(base + "_facts.md", "w").write("\n".join(md))
    print(f"wrote {base}_facts.json and {base}_facts.md")


if __name__ == "__main__":
    main(sys.argv[1])
