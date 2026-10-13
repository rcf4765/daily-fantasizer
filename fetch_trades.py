"""The Daily Fantasizer: trades + trading block fetcher (runs in the weekly GitHub Action).
- data/trades.json: COMPLETED trades only (TRADE_PROPOSAL rows with status EXECUTED), season to date.
  Pending, declined or expired offers are private to the managers involved and are never stored.
- data/trade_block.json: each team's ESPN trading block (players marked on the block / untouchable),
  which ESPN shows to the whole league. `teams_reporting` records which teams returned the field.
Read-only; never proposes, accepts or changes anything."""
import json, os, sys, datetime
import requests

LEAGUE, SEASON = 1196354715, 2026
BASE = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{SEASON}/segments/0/leagues/{LEAGUE}"
HERE = os.path.dirname(os.path.abspath(__file__))
POS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "D/ST"}
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (DailyFantasizer)"
if os.environ.get("ESPN_S2"):
    S.cookies.set("espn_s2", os.environ["ESPN_S2"].strip(), domain=".espn.com")
    S.cookies.set("SWID", os.environ["ESPN_SWID"].strip(), domain=".espn.com")


def get(params):
    r = S.get(BASE, params=params, timeout=30)
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("application/json"):
        sys.exit(f"ESPN returned {r.status_code} for {params}")
    return r.json()


def now(): return datetime.datetime.utcnow().isoformat() + "Z"
def ts(ms): return datetime.datetime.utcfromtimestamp(ms / 1000).isoformat() + "Z" if ms else None


def main():
    L = get([("view", "mStatus"), ("view", "mTeam"), ("view", "mRoster")])
    latest = L["status"]["latestScoringPeriod"]
    names, pos = {}, {}
    for t in L["teams"]:
        for e in (t.get("roster") or {}).get("entries", []):
            p = e["playerPoolEntry"]["player"]; names[p["id"]] = p["fullName"]; pos[p["id"]] = POS.get(p["defaultPositionId"], "")

    # ---- trading block ----
    block, reporting = {}, []
    for t in L["teams"]:
        tb = t.get("tradeBlock")
        if tb is None: continue
        reporting.append(t["id"])
        players = (tb or {}).get("players") or {}
        block[str(t["id"])] = [{"player": names.get(int(pid), pid), "pos": pos.get(int(pid), ""), "status": st} for pid, st in players.items()]
    json.dump({"fetched_at": now(), "teams_total": len(L["teams"]), "teams_reporting": sorted(reporting), "block": block},
              open(os.path.join(HERE, "data", "trade_block.json"), "w"), indent=1)
    print(f"trade block: {len(reporting)}/{len(L['teams'])} teams report; {sum(len(v) for v in block.values())} players listed")

    # ---- completed trades ----
    seen, done = set(), []
    for sp in range(1, latest + 1):
        X = get([("view", "mTransactions2"), ("scoringPeriodId", sp)])
        for t in X.get("transactions", []) or []:
            if t.get("type") == "TRADE_PROPOSAL" and t.get("status") == "EXECUTED" and t.get("items") and t["id"] not in seen:
                seen.add(t["id"]); done.append(t)
    ids = {i["playerId"] for t in done for i in t["items"]} - set(names)
    if ids:
        r = S.get(f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{SEASON}/players",
                  params={"scoringPeriodId": latest, "view": "players_wl"},
                  headers={"x-fantasy-filter": json.dumps({"filterIds": {"value": sorted(ids)}})}, timeout=30)
        if r.ok: names.update({p["id"]: p["fullName"] for p in r.json()})
    out = [{"id": t["id"], "period": t.get("scoringPeriodId"), "processed": ts(t.get("processDate") or t.get("proposedDate")),
            "teams": sorted({i["fromTeamId"] for i in t["items"]} | {i["toTeamId"] for i in t["items"]}),
            "items": [{"player": names.get(i["playerId"], i["playerId"]), "from": i["fromTeamId"], "to": i["toTeamId"]} for i in t["items"]]}
           for t in done]
    out.sort(key=lambda t: t["processed"] or "")
    json.dump({"fetched_at": now(), "latest_period": latest, "trades": out}, open(os.path.join(HERE, "data", "trades.json"), "w"), indent=1)
    print(f"completed trades: {len(out)}")


if __name__ == "__main__":
    main()
