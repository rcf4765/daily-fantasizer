"""The Daily Fantasizer: player data fetcher for the Player Stats tab (GitHub Actions, no browser).

Writes compact JSON into data/players/:
  espn_players.json   QB/RB/WR/TE: weekly PPR points + usage box stats, ESPN weekly projections,
                      ESPN analyst weekly PPR ranks, league owner (onTeamId), injury status
  usage.json          nflverse weekly snap %, target share, air-yards share, WOPR
  fp_week{K}.json     FantasyPros weekly consensus (ECR) by position for week K
                      (past weeks are fetched once; the upcoming week is refreshed every run)
  fp_ros.json         FantasyPros rest-of-season PPR consensus
  fp_lean.json        players one tracked analyst (Joel Smyth) ranks well above/below consensus
  meta.json           which weeks are complete, the upcoming week, fetch time

Env: ESPN_S2, ESPN_SWID (same secrets as fetch_espn.py).
Sources stay in the background on the page; this file is where they are listed."""
import csv, html, io, json, os, re, sys, time, datetime
import requests

SEASON, LEAGUE = 2026, 1196354715
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "players")
os.makedirs(OUT, exist_ok=True)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
S = requests.Session(); S.headers["User-Agent"] = UA
E = requests.Session(); E.headers["User-Agent"] = UA
if os.environ.get("ESPN_S2"):
    E.cookies.set("espn_s2", os.environ["ESPN_S2"].strip(), domain=".espn.com")
    E.cookies.set("SWID", os.environ["ESPN_SWID"].strip(), domain=".espn.com")
BASE = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{SEASON}/segments/0/leagues/{LEAGUE}"
POS = {1: "QB", 2: "RB", 3: "WR", 4: "TE"}
TEAM = {0: "FA", 1: "ATL", 2: "BUF", 3: "CHI", 4: "CIN", 5: "CLE", 6: "DAL", 7: "DEN", 8: "DET", 9: "GB", 10: "TEN",
        11: "IND", 12: "KC", 13: "LV", 14: "LAR", 15: "MIA", 16: "MIN", 17: "NE", 18: "NO", 19: "NYG", 20: "NYJ",
        21: "PHI", 22: "ARI", 23: "PIT", 24: "LAC", 25: "SF", 26: "SEA", 27: "TB", 28: "WSH", 29: "CAR", 30: "JAX",
        33: "BAL", 34: "HOU"}
# ESPN stat ids (verified against appliedTotal for every week-5 player, 2026-10-19)
ST = {"pa_att": 0, "pa_cmp": 1, "pa_yds": 3, "pa_td": 4, "pa_int": 20, "ru_att": 23, "ru_yds": 24, "ru_td": 25,
      "rec": 53, "re_yds": 42, "re_td": 43, "tgt": 58, "fum": 72}


def norm(n):
    """Name key shared with players.py: no suffixes, punctuation or spaces (D.K. Metcalf = DK Metcalf)."""
    n = n.lower().replace("’", "'")
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", n)
    return re.sub(r"[^a-z]", "", n)


def save(name, obj):
    with open(os.path.join(OUT, name), "w") as f:
        json.dump(obj, f, separators=(",", ":"), sort_keys=True)
    print("wrote", name)


def espn():
    st = E.get(BASE, params={"view": "mStatus"}, timeout=30)
    if st.status_code != 200 or "json" not in st.headers.get("content-type", ""):
        sys.exit(f"ESPN status {st.status_code}; check ESPN_S2/ESPN_SWID secrets")
    status = st.json()["status"]
    cur = st.json()["scoringPeriodId"]  # the week being played / about to be played
    sched = E.get(BASE, params={"view": "mMatchupScore"}, timeout=30).json()["schedule"]
    final = sorted({s["matchupPeriodId"] for s in sched} - {s["matchupPeriodId"] for s in sched if s.get("winner", "UNDECIDED") == "UNDECIDED"})
    flt = {"players": {"filterSlotIds": {"value": [0, 2, 4, 6]}, "limit": 600,
                       "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
                       "filterStatsForTopScoringPeriodIds": {"value": 40, "additionalValue":
                           [f"00{SEASON}", f"10{SEASON}"] + [f"11{SEASON}{w}" for w in range(1, 19)] + [f"11{SEASON}{w:02d}" for w in range(1, 19)]}}}
    r = E.get(BASE, params={"view": "kona_player_info", "scoringPeriodId": cur},
              headers={"X-Fantasy-Filter": json.dumps(flt)}, timeout=90)
    r.raise_for_status()
    players = []
    for p in r.json()["players"]:
        pl = p["player"]
        if pl.get("defaultPositionId") not in POS:
            continue
        act, proj = {}, {}
        for s in pl.get("stats", []):
            if s.get("seasonId") != SEASON or s.get("statSplitTypeId") != 1:
                continue
            wk = s["scoringPeriodId"]
            if s["statSourceId"] == 0:
                v = {int(k): x for k, x in s.get("stats", {}).items()}
                act[wk] = {"pts": round(s.get("appliedTotal", 0), 2), **{k: round(v.get(i, 0), 1) for k, i in ST.items()}}
            elif s["statSourceId"] == 1:
                proj[wk] = round(s.get("appliedTotal", 0), 2)
        ranks = {}
        for wk, lst in (pl.get("rankings") or {}).items():
            pp = {str(x["rankSourceId"]): x["rank"] for x in lst if x.get("rankType") == "PPR"}
            if pp:
                ranks[wk] = pp
        players.append({"id": pl["id"], "name": pl["fullName"], "pos": POS[pl["defaultPositionId"]],
                        "team": TEAM.get(pl.get("proTeamId"), "FA"), "owner": p.get("onTeamId", 0),
                        "inj": pl.get("injuryStatus", "ACTIVE"), "own_pct": round((pl.get("ownership") or {}).get("percentOwned", 0), 1),
                        "act": act, "proj": proj, "ranks": ranks})
    # ESPN only returns weekly projections for the scoring period asked for: add next week's
    nxt = cur + 1
    r2 = E.get(BASE, params={"view": "kona_player_info", "scoringPeriodId": nxt},
               headers={"X-Fantasy-Filter": json.dumps(flt)}, timeout=90)
    if r2.ok:
        byid = {p["id"]: p for p in players}
        for p in r2.json().get("players", []):
            pl = p["player"]
            if pl["id"] not in byid:
                continue
            for s in pl.get("stats", []):
                if s.get("seasonId") == SEASON and s.get("statSourceId") == 1 and s.get("scoringPeriodId") == nxt:
                    byid[pl["id"]]["proj"][nxt] = round(s.get("appliedTotal", 0), 2)
    save("espn_players.json", players)
    return cur, final


def nflverse():
    base = "https://github.com/nflverse/nflverse-data/releases/download/"
    out = {}
    try:
        st = list(csv.DictReader(io.StringIO(S.get(base + f"stats_player/stats_player_week_{SEASON}.csv", timeout=90).text)))
        for x in st:
            if x.get("season_type") != "REG" or x.get("position") not in ("QB", "RB", "WR", "TE"):
                continue
            k = f'{x["player_display_name"]}|{x["position"]}|{x["team"]}'
            d = out.setdefault(k, {"name": x["player_display_name"], "pos": x["position"], "team": x["team"], "wk": {}})
            f = lambda c: round(float(x[c]), 4) if x.get(c) not in (None, "", "NA") else None
            d["wk"][x["week"]] = {"ts": f("target_share"), "ays": f("air_yards_share"), "wopr": f("wopr"),
                                  "ay": f("receiving_air_yards"), "opp": x.get("opponent_team")}
        sn = list(csv.DictReader(io.StringIO(S.get(base + f"snap_counts/snap_counts_{SEASON}.csv", timeout=90).text)))
        snaps = {}
        for x in sn:
            if x.get("game_type") != "REG" or x.get("position") not in ("QB", "RB", "WR", "TE"):
                continue
            snaps[f'{norm(x["player"])}|{x["position"]}|{x["week"]}'] = round(float(x["offense_pct"] or 0), 3)
        for k, d in out.items():
            for wk, v in d["wk"].items():
                v["snap"] = snaps.get(f'{norm(d["name"])}|{d["pos"]}|{wk}')
        # snap-only players (no box score yet) are skipped: no usage to show
    except Exception as e:  # nflverse is a nice-to-have; the page degrades without it
        print("nflverse failed:", e)
        if os.path.exists(os.path.join(OUT, "usage.json")):
            return
    save("usage.json", list(out.values()))


def fp_page(path):
    r = S.get("https://www.fantasypros.com/nfl/" + path, timeout=60)
    time.sleep(1.5)
    if r.status_code != 200:
        print("FantasyPros", r.status_code, path); return None
    m = re.search(r"var ecrData\s*=\s*(\{.*?\});\s*\n", r.text, re.S)
    return (json.loads(m.group(1)), r.text) if m else (None, r.text)


KEEP = ("player_name", "player_team_id", "player_position_id", "player_opponent", "rank_ecr", "rank_min", "rank_max",
        "rank_ave", "rank_std", "pos_rank", "tier", "r2p_pts", "start_sit_grade", "player_ecr_delta", "player_owned_avg")


def fantasypros(cur, final):
    """Weekly ECR for every completed week (fetched once) and the upcoming week (always refreshed)."""
    # the week on the field (cur) and the one after it: FantasyPros posts the next week's
    # rankings early in the week, so cur + 1 is saved as soon as it shows up
    upcoming = cur + 1
    for wk in range(1, upcoming + 1):
        fn = os.path.join(OUT, f"fp_week{wk}.json")
        if wk < cur and os.path.exists(fn):
            continue
        res = {"week": wk, "pos": {}}
        for pos, slug in (("QB", "qb"), ("RB", "ppr-rb"), ("WR", "ppr-wr"), ("TE", "ppr-te")):
            got = fp_page(f"rankings/{slug}.php?week={wk}")
            j = got and got[0]
            if not j or str(j.get("week")) != str(wk):
                print(f"FantasyPros week {wk} {pos}: not posted yet (page shows week {j and j.get('week')})"); continue
            res["pos"][pos] = [{k: p.get(k) for k in KEEP} for p in j["players"]]
            res["experts"] = j.get("total_experts"); res["updated"] = j.get("last_updated")
        if res["pos"]:
            save(f"fp_week{wk}.json", res)
    got = fp_page("rankings/ros-ppr-overall.php")
    if got and got[0]:
        j = got[0]
        save("fp_ros.json", {"updated": j.get("last_updated"), "players": [{k: p.get(k) for k in KEEP} for p in j["players"]]})
    lean = {"week": None, "pos": {}}
    for pos in ("QB", "RB", "WR", "TE"):
        got = fp_page(f"rankings/joel-smyth-consensus-rankings.php?position={pos}")
        if not got:
            continue
        html_ = got[1]
        t = re.search(r"Rankings Week (\d+)", html_)
        lean["week"] = int(t.group(1)) if t else None
        rows = []
        for tbl in re.findall(r"<table.*?</table>", html_, re.S):
            hdr = html.unescape(re.sub(r"<[^>]+>", " ", tbl[:600]))
            higher = "Joel Smyth's Rank" in hdr.split("Player")[0]
            for tr in re.findall(r"<tr.*?</tr>", tbl, re.S)[1:]:
                c = [html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x))).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
                if len(c) >= 3 and c[0].isdigit():
                    m = re.match(r"(.+?) ([A-Z]{2,3}) - ([A-Z]{1,3})$", c[1])
                    if not m:
                        continue
                    a, b = int(c[0]), int(re.sub(r"\D", "", c[2]) or 0)
                    rows.append({"name": m.group(1), "team": m.group(2), "analyst": a if higher else b,
                                 "ecr": b if higher else a})
        lean["pos"][pos] = rows
    save("fp_lean.json", lean)
    return upcoming


def main():
    cur, final = espn()
    nflverse()
    upcoming = fantasypros(cur, final)
    save("meta.json", {"season": SEASON, "espn_week": cur, "final_weeks": final, "upcoming": upcoming,
                       "fetched": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ")})


if __name__ == "__main__":
    main()
