"""The Daily Fantasizer: trade-activity fetcher for the Trade Rumors block.
Reads every trade-related transaction ESPN shows to the signed-in account (ESPN_S2/ESPN_SWID)
across all scoring periods so far: proposals (any status), accepts, declines, vetoes, cancels.
Writes data/trades.json. Read-only; never proposes, accepts or changes anything."""
import json, os, sys, datetime
import requests

LEAGUE, SEASON = 1196354715, 2026
BASE = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{SEASON}/segments/0/leagues/{LEAGUE}"
HERE = os.path.dirname(os.path.abspath(__file__))
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (DailyFantasizer)"
if os.environ.get("ESPN_S2"):
    S.cookies.set("espn_s2", os.environ["ESPN_S2"].strip(), domain=".espn.com")
    S.cookies.set("SWID", os.environ["ESPN_SWID"].strip(), domain=".espn.com")


def get(params, headers=None):
    r = S.get(BASE, params=params, headers=headers or {}, timeout=30)
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("application/json"):
        sys.exit(f"ESPN returned {r.status_code} for {params}")
    return r.json()


def main():
    st = get([("view", "mStatus"), ("view", "mSettings")])
    latest = st["status"]["latestScoringPeriod"]
    seen, txs, kinds = set(), [], {}
    for sp in range(1, latest + 1):
        for view in ("mTransactions2", "mPendingTransactions"):
            try:
                X = get([("view", view), ("scoringPeriodId", sp)])
            except SystemExit as e:
                print("skip", view, sp, e); continue
            for t in X.get("transactions", []) or []:
                k = f'{t.get("type")}/{t.get("status")}'
                kinds[k] = kinds.get(k, 0) + 1
                if not str(t.get("type", "")).startswith("TRADE") or t.get("id") in seen: continue
                seen.add(t.get("id")); txs.append(t)
    ids = sorted({i["playerId"] for t in txs for i in t.get("items") or []})
    nm = {}
    if ids:
        r = S.get(f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{SEASON}/players",
                  params={"scoringPeriodId": latest, "view": "players_wl"},
                  headers={"x-fantasy-filter": json.dumps({"filterIds": {"value": ids}})}, timeout=30)
        if r.ok: nm = {p["id"]: p["fullName"] for p in r.json()}
    def ts(ms): return datetime.datetime.utcfromtimestamp(ms / 1000).isoformat() + "Z" if ms else None
    out = [{"id": t.get("id"), "type": t.get("type"), "status": t.get("status"), "team": t.get("teamId"),
            "period": t.get("scoringPeriodId"), "proposed": ts(t.get("proposedDate")), "processed": ts(t.get("processDate")),
            "related": t.get("relatedTransactionId"),
            "items": [{"player": nm.get(i["playerId"], i["playerId"]), "from": i.get("fromTeamId"), "to": i.get("toTeamId"), "type": i.get("type")}
                      for i in t.get("items") or []]} for t in txs]
    out.sort(key=lambda t: t["proposed"] or "")
    json.dump({"fetched_at": datetime.datetime.utcnow().isoformat() + "Z", "latest_period": latest,
               "kinds_seen": kinds, "trades": out}, open(os.path.join(HERE, "data", "trades.json"), "w"), indent=1)
    print(f"wrote data/trades.json: {len(out)} trade rows; kinds {kinds}")


if __name__ == "__main__":
    main()
