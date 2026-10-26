"""The Daily Fantasizer: apply passed Rule Changes to the ESPN league (GitHub Actions; ESPN_S2/ESPN_SWID secrets).

Usage:
  python rules_espn.py inspect        read-only: print the settings the presets touch, and whether the
                                      saved ESPN login is a league manager (needed to change settings)
  python rules_espn.py apply          apply every passed, not-yet-applied proposal whose preset is in
                                      rules_presets.json, then re-read ESPN to verify; record results in
                                      docs/rulebook.json (the Rule Changes tab shows it)
  python rules_espn.py apply --dry    same, but never writes to ESPN

Safety:
  - Only presets listed in rules_presets.json can change ESPN. Each preset names exact fields and values;
    nothing a manager types is ever sent to ESPN. Free-text proposals that pass go in the rulebook as
    "Commissioner to apply".
  - Before writing, the current value is read and recorded, so every change can be undone by hand.
  - After writing, ESPN is read again; the change counts only if ESPN now shows the new value.
"""
import copy
import datetime
import json
import os
import sys

import requests

LEAGUE, SEASON = 1196354715, 2026
READ = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{SEASON}/segments/0/leagues/{LEAGUE}"
WRITE = f"https://lm-api-writes.fantasy.espn.com/apis/v3/games/ffl/seasons/{SEASON}/segments/0/leagues/{LEAGUE}"
HERE = os.path.dirname(os.path.abspath(__file__))
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (DailyFantasizer)"
if os.environ.get("ESPN_S2"):
    S.cookies.set("espn_s2", os.environ["ESPN_S2"].strip(), domain=".espn.com")
    S.cookies.set("SWID", os.environ["ESPN_SWID"].strip(), domain=".espn.com")


def now(): return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def read(views):
    r = S.get(READ, params=[("view", v) for v in views], timeout=30)
    if r.status_code != 200 or "json" not in r.headers.get("content-type", ""):
        sys.exit(f"ESPN read failed: {r.status_code}")
    return r.json()


def get_path(obj, path):
    for k in path:
        if isinstance(k, dict):  # list element selected by matching keys, e.g. {"statId": 53}
            obj = next((x for x in obj if all(x.get(a) == b for a, b in k.items())), None)
        else:
            obj = obj.get(k) if isinstance(obj, dict) else None
        if obj is None:
            return None
    return obj


def set_path(obj, path, value):
    for k in path[:-1]:
        obj = next(x for x in obj if all(x.get(a) == b for a, b in k.items())) if isinstance(k, dict) else obj[k]
    obj[path[-1]] = value


def manager_check(L):
    swid = os.environ.get("ESPN_SWID", "").strip().upper()
    for m in L.get("members", []):
        if str(m.get("id", "")).upper() == swid:
            return bool(m.get("isLeagueManager")), m.get("displayName", "")
    return None, ""


def inspect():
    L = read(["mSettings", "mTeam"])
    st = L["settings"]
    lm, who = manager_check(L)
    print("saved ESPN login is league manager:", lm, f"({who})" if who else "")
    print("status:", {k: L.get("status", {}).get(k) for k in ("currentMatchupPeriod", "isActive", "latestScoringPeriod")})
    print("acquisitionSettings:", json.dumps(st.get("acquisitionSettings"), sort_keys=True))
    print("tradeSettings:", json.dumps(st.get("tradeSettings"), sort_keys=True))
    print("rosterSettings keys:", sorted((st.get("rosterSettings") or {}).keys()))
    sc = st.get("scoringSettings") or {}
    print("scoringSettings keys:", sorted(sc.keys()))
    for it in sc.get("scoringItems", []):
        print("  scoringItem", json.dumps(it, sort_keys=True))
    P = json.load(open(os.path.join(HERE, "rules_presets.json")))
    for pid, p in P.items():
        for ch in p.get("espn", []):
            print(f"preset {pid}: {ch['path']} now = {json.dumps(get_path(st, ch['path']))} -> {json.dumps(ch['value'])}")


def apply(dry):
    P = json.load(open(os.path.join(HERE, "rules_presets.json")))
    LG = json.load(open(os.path.join(HERE, "league.json")))
    api = LG.get("proposals_api")
    if not api:
        sys.exit("league.json has no proposals_api")
    state = requests.get(api, timeout=60).json()
    book_path = os.path.join(HERE, "docs", "rulebook.json")
    book = json.load(open(book_path)) if os.path.exists(book_path) else {"entries": {}}
    todo = [p for p in state.get("proposals", []) if p.get("status") == "passed"
            and book["entries"].get(p["id"], {}).get("result") not in ("applied", "manual")]
    if not todo:
        print("nothing to apply"); return
    L = read(["mSettings", "mTeam"])
    lm, _ = manager_check(L)
    for p in todo:
        e = {"id": p["id"], "title": p["title"], "category": p.get("category"), "preset": p.get("preset") or None,
             "passed_at": p.get("closedAt"), "checked_at": now()}
        pre = P.get(p.get("preset") or "")
        if not pre or not pre.get("espn"):
            e.update(result="manual", note="Free-text change: the commissioner sets it in ESPN.")
            book["entries"][p["id"]] = e; print(p["id"], "manual"); continue
        settings = copy.deepcopy(L["settings"])
        before, missing = [], []
        for ch in pre["espn"]:
            cur = get_path(settings, ch["path"])
            if cur is None and not ch.get("create"):
                missing.append(ch["path"])
            before.append({"path": ch["path"], "was": cur, "now": ch["value"]})
        e["changes"] = before
        if missing:
            e.update(result="needs_commissioner", note=f"ESPN doesn't have the setting {missing}; set it by hand.")
        elif all(b["was"] == b["now"] for b in before):
            e.update(result="applied", note="ESPN already had this setting.", applied_at=now())
        elif lm is False:
            e.update(result="needs_commissioner", note="The saved ESPN login isn't the league manager, so it can't change settings.")
        elif dry:
            e.update(result="dry_run", note="Would change ESPN (dry run).")
        else:
            for ch in pre["espn"]:
                set_path(settings, ch["path"], ch["value"])
            r = S.put(WRITE + "/settings", json=settings, timeout=30,
                      headers={"Content-Type": "application/json", "x-fantasy-source": "kona", "x-fantasy-platform": "kona-PROD"})
            after = read(["mSettings"])["settings"]
            ok = all(get_path(after, ch["path"]) == ch["value"] for ch in pre["espn"])
            if ok:
                e.update(result="applied", applied_at=now(), note=f"Live on ESPN since {now()[:10]}.")
            else:
                e.update(result="needs_commissioner", note=f"ESPN didn't take the change (HTTP {r.status_code}); set it by hand.",
                         http=r.status_code, espn_said=r.text[:300])
            L = read(["mSettings", "mTeam"])  # fresh copy for the next proposal
        book["entries"][p["id"]] = e
        print(p["id"], e["result"], e.get("note", ""))
    book["updated_at"] = now()
    os.makedirs(os.path.dirname(book_path), exist_ok=True)
    json.dump(book, open(book_path, "w"), indent=1)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "inspect"
    if cmd == "inspect":
        inspect()
    elif cmd == "apply":
        apply("--dry" in sys.argv)
    else:
        sys.exit(__doc__)
