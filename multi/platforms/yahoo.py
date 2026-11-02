"""The Daily Fantasizer, any league: Yahoo Fantasy Football → the paper's raw data files.

Reads the Yahoo Fantasy Sports API (XML) with an OAuth access token the website hands the build
(Sign in with Yahoo, read-only scope fspt-r) and writes, into the league folder ($FZ_HOME):
  data/weekN_raw.txt     same format as fetch_espn.py (META, SLOTS, TEAMS, SCHED, ROSTERS, TX, LOGOURLS)
  data/schedule.json     full regular season (Playoff Odds)
  data/trades.json       completed trades only
  data/trade_block.json  empty: Yahoo has no trading block in its API (On the Block shows "not reported")
  data/logos.txt, data/logo_urls.txt, data/latest.json
  data/yahoo_rosters.json   current rosters (who owns whom), used by --players
  data/yahoo_scoring.json   the league's stat modifiers, used by --players

Usage:
  python3 yahoo.py                  fetch every completed week that isn't saved yet (+ schedule, trades, crests)
  python3 yahoo.py --players        after the shared player data is copied in: set each player's owner to the
                                    Yahoo team that rosters him and rescore weekly points with this league's scoring
Env: YAHOO_TOKEN (access token), FZ_LEAGUE_KEY (e.g. 461.l.123456), FZ_HOME (league folder).
Projections: Yahoo's API doesn't publish weekly projections, so QB/RB/WR/TE use FantasyPros' consensus
projection for that week (data/players/fp_weekN.json, r2p_pts); kickers and defenses, and anyone not found,
are given their own score as the projection, which keeps them out of the "beat/missed projection" stories.
Read-only: never changes anything on Yahoo.
"""
import datetime, json, os, re, sys, xml.etree.ElementTree as ET
import requests

HOME = os.environ.get("FZ_HOME") or os.getcwd()
DATA = os.path.join(HOME, "data")
API = "https://fantasysports.yahooapis.com/fantasy/v2"
NS = {"y": "http://fantasysports.yahooapis.com/fantasy/v2/base.rng"}
POS = {"QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "K": "K", "DEF": "D/ST"}
SLOT = {"QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "K": "K", "DEF": "D/ST", "W/R/T": "FLEX", "W/R": "RB/WR",
        "W/T": "WR/TE", "Q/W/R/T": "OP", "BN": "BE", "IR": "IR"}
# Yahoo NFL stat ids → the box-score keys in espn_players.json (for rescoring with this league's modifiers)
YSTAT = {4: "pa_yds", 5: "pa_td", 6: "pa_int", 9: "ru_yds", 10: "ru_td", 11: "rec", 12: "re_yds", 13: "re_td", 18: "fum"}

S = requests.Session()
S.headers["User-Agent"] = "DailyFantasizer/1.0"


def get(path):
    tok = os.environ.get("YAHOO_TOKEN", "").strip()
    if not tok:
        sys.exit("YAHOO_TOKEN is missing (the website passes a fresh one to every build)")
    r = S.get(f"{API}/{path}", headers={"Authorization": f"Bearer {tok}"}, timeout=40)
    if r.status_code == 401:
        sys.exit("Yahoo said 401: the access token expired or was revoked. The commissioner should sign in with Yahoo again.")
    if r.status_code != 200:
        sys.exit(f"Yahoo returned {r.status_code} for {path}: {r.text[:300]}")
    return ET.fromstring(r.content)


def t(el, path, default=""):
    x = el.find(path, NS)
    return x.text.strip() if x is not None and x.text else default


def all_(el, path):
    return el.findall(path, NS)


def js_num(x, places=2):
    import math
    f = 10 ** places
    v = math.floor((x or 0) * f + 0.5) / f
    s = repr(v)
    return s[:-2] if s.endswith(".0") else s


def norm(n):
    n = n.lower().replace("’", "'")
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", n)
    return re.sub(r"[^a-z]", "", n)


def player_name(p):
    pos = POS.get(t(p, "y:primary_position") or t(p, "y:display_position").split(",")[0], t(p, "y:display_position"))
    if pos == "D/ST":  # "Pittsburgh Steelers" → "Steelers D/ST", ESPN's naming, so every module matches
        full = t(p, "y:editorial_team_full_name") or t(p, "y:name/y:full")
        return f"{full.split(' ')[-1]} D/ST", pos
    return t(p, "y:name/y:full"), pos


def league():
    lk = os.environ["FZ_LEAGUE_KEY"]
    L = get(f"league/{lk}/settings").find("y:league", NS)
    T = get(f"league/{lk}/teams").find("y:league", NS)
    return lk, L, T


def fp_proj(week):
    """FantasyPros consensus projection for that week, by normalized name."""
    f = os.path.join(DATA, "players", f"fp_week{week}.json")
    if not os.path.exists(f):
        return {}
    j = json.load(open(f))
    out = {}
    for rows in (j.get("pos") or {}).values():
        for r in rows:
            try:
                out[norm(r["player_name"])] = float(r.get("r2p_pts") or 0)
            except (TypeError, ValueError):
                pass
    return out


def scoreboard(lk, w):
    sb = get(f"league/{lk}/scoreboard;week={w}")
    out = []
    for m in sb.iter(f"{{{NS['y']}}}matchup"):
        tm = all_(m, "y:teams/y:team")
        if len(tm) != 2:
            continue
        a, b = tm
        ia, ib = int(t(a, "y:team_id")), int(t(b, "y:team_id"))
        pa, pb = float(t(a, "y:team_points/y:total", "0") or 0), float(t(b, "y:team_points/y:total", "0") or 0)
        status = t(m, "y:status")
        if status != "postevent":
            win = "UNDECIDED"
        elif t(m, "y:is_tied") == "1":
            win = "TIE"
        else:
            wk = t(m, "y:winner_team_key")
            win = "HOME" if wk == t(a, "y:team_key") else "AWAY"
        out.append(dict(wk=int(t(m, "y:week") or w), home=ia, hp=pa, away=ib, ap=pb, winner=win, status=status))
    return out


def roster(tk, w=None):
    path = f"team/{tk}/roster;week={w}/players/stats;type=week;week={w}" if w else f"team/{tk}/roster/players"
    R = get(path)
    out = []
    for p in R.iter(f"{{{NS['y']}}}player"):
        name, pos = player_name(p)
        slot = SLOT.get(t(p, "y:selected_position/y:position"), t(p, "y:selected_position/y:position"))
        pts = float(t(p, "y:player_points/y:total", "0") or 0)
        out.append(dict(name=name, pos=pos, slot=slot, pts=pts, team=t(p, "y:editorial_team_abbr").upper()))
    return out


def game_weeks(lk):
    gk = lk.split(".l.")[0]
    G = get(f"game/{gk}/game_weeks")
    wk = {}
    for x in G.iter(f"{{{NS['y']}}}game_week"):
        wk[int(t(x, "y:week"))] = (t(x, "y:start"), t(x, "y:end"))
    return wk


def week_of(ts, weeks):
    d = datetime.datetime.utcfromtimestamp(int(ts)).date().isoformat()
    for w in sorted(weeks):
        start = weeks[w][0]
        nxt = weeks.get(w + 1, ("9999-12-31",))[0]
        if start <= d < nxt:
            return w
    return 0


def transactions(lk, ids_by_key):
    X = get(f"league/{lk}/transactions;types=add,drop,trade")
    out = []
    for tx in X.iter(f"{{{NS['y']}}}transaction"):
        if t(tx, "y:status") != "successful":
            continue  # pending / declined trades are private: never stored
        kind = t(tx, "y:type")
        items = []
        for p in all_(tx, "y:players/y:player"):
            name, _ = player_name(p)
            td = p.find("y:transaction_data", NS)
            if td is None:
                continue
            items.append(dict(name=name, type=t(td, "y:type"), src=t(td, "y:source_type"),
                              frm=ids_by_key.get(t(td, "y:source_team_key")), to=ids_by_key.get(t(td, "y:destination_team_key"))))
        out.append(dict(key=t(tx, "y:transaction_key"), kind=kind, ts=t(tx, "y:timestamp"), items=items))
    return out


def crests(teams_xml):
    """Team logos as 72px webp data URIs (same as fetch_espn.crest), refreshed only when a URL changes."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    import fetch_espn as FE
    lu_path, lg_path = os.path.join(DATA, "logo_urls.txt"), os.path.join(DATA, "logos.txt")
    old = dict(l.strip().split("|", 1) for l in open(lu_path) if "|" in l) if os.path.exists(lu_path) else {}
    logos = dict(l.strip().split(" ", 1) for l in open(lg_path) if l.strip()) if os.path.exists(lg_path) else {}
    urls = {}
    for tm in teams_xml:
        tid = t(tm, "y:team_id")
        logo = next((t(x, "y:url") for x in all_(tm, "y:team_logos/y:team_logo") if t(x, "y:size") == "large"), "") or t(tm, "y:team_logos/y:team_logo/y:url")
        urls[tid] = logo
    for tid, u in urls.items():
        if old.get(tid) == u and f"@{tid}" in logos:
            continue
        try:
            logos[f"@{tid}"] = FE.crest(u); old[tid] = u
        except Exception as ex:  # a blank crest is better than no paper
            print(f"WARNING: crest for team {tid} failed: {ex}")
            logos[f"@{tid}"] = "data:image/gif;base64,R0lGODlhAQABAAAAACw="; old[tid] = u
    open(lg_path, "w").write("\n".join(f"{k} {logos[k]}" for k in sorted(logos, key=lambda k: int(k[1:]))) + "\n")
    open(lu_path, "w").write("\n".join(f"{k}|{old[k]}" for k in sorted(old, key=int)) + "\n")
    return urls


def main():
    os.makedirs(DATA, exist_ok=True)
    lk, L, T = league()
    teams_xml = all_(T, "y:teams/y:team")
    ids_by_key = {t(x, "y:team_key"): int(t(x, "y:team_id")) for x in teams_xml}
    st = L.find("y:settings", NS)
    start_w, cur_w = int(t(L, "y:start_week", "1")), int(t(L, "y:current_week", "1"))
    po_start = int(t(st, "y:playoff_start_week", "15") or 15) if t(st, "y:uses_playoff", "1") == "1" else int(t(L, "y:end_week", "17")) + 1
    regweeks = po_start - start_w
    po_teams = int(t(st, "y:num_playoff_teams", "4") or 4)
    slots = {}
    for rp in all_(st, "y:roster_positions/y:roster_position"):
        p = SLOT.get(t(rp, "y:position"), t(rp, "y:position"))
        if p in ("BE", "IR"):
            continue
        slots[p] = slots.get(p, 0) + int(t(rp, "y:count", "0") or 0)
    mods = {int(t(s, "y:stat_id")): float(t(s, "y:value", "0") or 0) for s in all_(st, "y:stat_modifiers/y:stats/y:stat")}
    json.dump({"modifiers": mods}, open(os.path.join(DATA, "yahoo_scoring.json"), "w"), indent=1)

    # every regular-season week's matchups (played and not), with final scores where finished
    sched = {}
    for w in range(start_w, start_w + regweeks):
        sched[w] = scoreboard(lk, w)
    final = [w for w in sched if sched[w] and all(g["status"] == "postevent" for g in sched[w])]
    games = [{"wk": g["wk"] - start_w + 1, "home": g["home"], "away": g["away"], "winner": g["winner"]} for w in sched for g in sched[w]]
    now = datetime.datetime.utcnow().isoformat() + "Z"
    json.dump({"fetched_at": now, "regweeks": regweeks, "playoff_teams": po_teams, "games": sorted(games, key=lambda g: (g["wk"], g["home"]))},
              open(os.path.join(DATA, "schedule.json"), "w"), indent=1)
    json.dump({"fetched_at": now, "teams_total": len(teams_xml), "teams_reporting": [], "block": {}},
              open(os.path.join(DATA, "trade_block.json"), "w"), indent=1)

    urls = crests(teams_xml)
    weeks = game_weeks(lk)
    txs = transactions(lk, ids_by_key)
    trades = []
    for x in txs:
        if x["kind"] != "trade":
            continue
        tm = sorted({i["frm"] for i in x["items"] if i["frm"]} | {i["to"] for i in x["items"] if i["to"]})
        trades.append({"id": x["key"], "period": week_of(x["ts"], weeks) - start_w + 1,
                       "processed": datetime.datetime.utcfromtimestamp(int(x["ts"])).isoformat() + "Z", "teams": tm,
                       "items": [{"player": i["name"], "from": i["frm"], "to": i["to"]} for i in x["items"]]})
    json.dump({"fetched_at": now, "latest_period": cur_w, "trades": sorted(trades, key=lambda z: z["processed"])},
              open(os.path.join(DATA, "trades.json"), "w"), indent=1)

    team_lines = []
    for x in teams_xml:
        mgrs = " & ".join(t(m, "y:nickname") for m in all_(x, "y:managers/y:manager") if t(m, "y:nickname") not in ("", "--hidden--"))
        name = t(x, "y:name")
        abbrev = "".join(w[0] for w in name.split()[:3]).upper() or "T"
        team_lines.append("|".join([t(x, "y:team_id"), name.replace("|", "/"), abbrev, mgrs.replace("|", "/")]))

    wrote = []
    for W in sorted(final):
        pw = W - start_w + 1  # the paper counts weeks from 1
        path = os.path.join(DATA, f"week{pw}_raw.txt")
        if os.path.exists(path) and os.environ.get("FORCE") != "1":
            continue
        proj = fp_proj(pw)
        out = [f'META|league={lk.split(".l.")[-1]}|season={t(L, "y:season")}|week={pw}|name={t(L, "y:name")}|latest={pw + 1}|complete=1'
               f'|regweeks={regweeks}|playoffteams={po_teams}',
               "SLOTS|" + ",".join(f"{k}:{v}" for k, v in slots.items()), "TEAMS", *team_lines, "SCHED"]
        for w in sorted(sched):
            if w - start_w + 1 > pw + 1:
                continue
            for g in sched[w]:
                out.append("|".join([str(w - start_w + 1), str(g["home"]), js_num(g["hp"]), str(g["away"]), js_num(g["ap"]),
                                     g["winner"] if w <= W else "UNDECIDED"]))
        out.append("ROSTERS")
        for x in teams_xml:
            out.append(f'#{t(x, "y:team_id")}')
            for p in roster(t(x, "y:team_key"), W):
                pj = proj.get(norm(p["name"])) if p["pos"] in ("QB", "RB", "WR", "TE") else None
                out.append("|".join([p["name"], p["pos"], p["slot"], js_num(p["pts"]), js_num(pj if pj is not None else p["pts"], 1)]))
        out.append("TX")
        for x in txs:
            if week_of(x["ts"], weeks) != W:
                continue
            if x["kind"] == "trade":
                tm = next((i["frm"] for i in x["items"] if i["frm"]), 0)
                out.append("|".join(["T", str(tm), ",".join(f'TRADE:{i["name"]}:{i["frm"]}>{i["to"]}' for i in x["items"])]))
            else:
                tm = next((i["to"] for i in x["items"] if i["type"] == "add"), None) or next((i["frm"] for i in x["items"]), 0)
                kind = "W" if any(i["src"] == "waivers" for i in x["items"]) else "F"
                out.append("|".join([kind, str(tm), ",".join(f'{"ADD" if i["type"] == "add" else "DROP"}:{i["name"]}' for i in x["items"])]))
        out.append("LOGOURLS")
        out += [f"{k}|{v}" for k, v in urls.items()]
        open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")
        wrote.append(pw)
        print(f"wrote {path} ({len(out)} lines)")

    rosters = {}
    for x in teams_xml:
        for p in roster(t(x, "y:team_key")):
            rosters[f'{norm(p["name"])}|{p["pos"]}'] = int(t(x, "y:team_id"))
    json.dump(rosters, open(os.path.join(DATA, "yahoo_rosters.json"), "w"))
    latest = max(final) - start_w + 1 if final else 0
    json.dump({"week": latest, "complete": bool(final), "fetched_at": now, "wrote": wrote, "platform": "yahoo"},
              open(os.path.join(DATA, "latest.json"), "w"), indent=1)
    print(f"Yahoo league {lk}: latest completed week {latest}; wrote weeks {wrote or 'none (all saved)'}")


def players():
    """Owners + this league's scoring on the shared ESPN player pool."""
    P = os.path.join(DATA, "players")
    ros = json.load(open(os.path.join(DATA, "yahoo_rosters.json")))
    mods = {int(k): v for k, v in json.load(open(os.path.join(DATA, "yahoo_scoring.json")))["modifiers"].items()}
    rescore = all(k in mods for k in (4, 9, 12))  # only when the main categories are known
    for fn in ("espn_players.json", "espn_kdst.json"):
        f = os.path.join(P, fn)
        if not os.path.exists(f):
            continue
        rows = json.load(open(f))
        for r in rows:
            r["owner"] = ros.get(f'{norm(r["name"])}|{r["pos"]}', 0)
            if rescore and fn == "espn_players.json":
                for wk, a in r.get("act", {}).items():
                    a["pts"] = round(sum(mods.get(i, 0) * float(a.get(k, 0) or 0) for i, k in YSTAT.items()), 2)
        json.dump(rows, open(f, "w"), separators=(",", ":"), sort_keys=True)
    print(f"players: owners set from Yahoo rosters ({len(ros)} rostered); "
          f"{'rescored with the league' if rescore else 'kept ESPN PPR'} scoring")


if __name__ == "__main__":
    players() if sys.argv[1:] == ["--players"] else main()
