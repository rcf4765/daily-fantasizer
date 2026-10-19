"""The Daily Fantasizer: ESPN fetcher (no browser needed).
Python port of extract.js + extract_logos.js, run by GitHub Actions every Tuesday.

Env:
  ESPN_S2, ESPN_SWID   cookies from a signed-in ESPN session (GitHub secrets)
  WEEK                 optional; default = latest completed matchup period
  FORCE=1              optional; re-fetch even if data/weekN_raw.txt exists
  PREVIEW=1            optional; snapshot WEEK even if it isn't final, written to
                       preview/weekN_raw.txt (complete=0). Never touches data/ (no
                       crests, no latest.json), so the real weekly edition is unaffected.
Writes data/weekN_raw.txt (same format extract.js produces), refreshes
data/logos.txt + data/logo_urls.txt for any team whose crest URL changed,
and data/latest.json. Exit code 0 with "nothing to do" if the week is already saved
or not final yet."""
import base64, io, json, math, os, sys, datetime
import requests
from PIL import Image

LEAGUE, SEASON = 1196354715, 2026
BASE = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{SEASON}/segments/0/leagues/{LEAGUE}"
POS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "D/ST"}
SLOT = {0: "QB", 2: "RB", 4: "WR", 6: "TE", 16: "D/ST", 17: "K", 20: "BE", 21: "IR", 23: "FLEX", 3: "RB/WR", 5: "WR/TE", 7: "OP"}
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (DailyFantasizer)"
if os.environ.get("ESPN_S2"):
    S.cookies.set("espn_s2", os.environ["ESPN_S2"].strip(), domain=".espn.com")
    S.cookies.set("SWID", os.environ["ESPN_SWID"].strip(), domain=".espn.com")


def get(params, headers=None):
    r = S.get(BASE, params=params, headers=headers or {}, timeout=30)
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("application/json"):
        sys.exit(f"ESPN returned {r.status_code} {r.headers.get('content-type')} for {params}. "
                 "If 401/403 or HTML, the ESPN_S2/ESPN_SWID secrets are missing or expired.")
    return r.json()


def js_num(x, places=2):
    """Match JavaScript Math.round(x*10^p)/10^p and its string form (e.g. 82 not 82.0)."""
    f = 10 ** places
    v = math.floor((x or 0) * f + 0.5) / f
    s = repr(v)
    return s[:-2] if s.endswith(".0") else s


def crest(url):
    """Draw the crest into a 72x72 transparent canvas and return a webp data URI."""
    r = S.get(url, timeout=30); r.raise_for_status()
    if url.lower().endswith(".svg") or "svg" in r.headers.get("content-type", ""):
        import cairosvg
        im = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=r.content, output_width=288))).convert("RGBA")
    else:
        im = Image.open(io.BytesIO(r.content)).convert("RGBA")
    s = min(72 / im.width, 72 / im.height)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    canvas = Image.new("RGBA", (72, 72), (0, 0, 0, 0))
    canvas.paste(im, ((72 - im.width) // 2, (72 - im.height) // 2), im)
    buf = io.BytesIO(); canvas.save(buf, "WEBP", quality=82)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


def main():
    L = get([("view", "mTeam"), ("view", "mSettings"), ("view", "mStatus"), ("view", "mMatchupScore")])
    sched = L["schedule"]
    final = sorted({s["matchupPeriodId"] for s in sched} - {s["matchupPeriodId"] for s in sched if s.get("winner", "UNDECIDED") == "UNDECIDED"})
    W = int(os.environ.get("WEEK") or 0) or (final[-1] if final else 0)
    if not W:
        print("No completed week yet; nothing to do."); return
    PREVIEW = os.environ.get("PREVIEW") == "1"
    out_path = os.path.join(HERE, "preview", f"week{W}_raw.txt") if PREVIEW else os.path.join(DATA, f"week{W}_raw.txt")
    complete = W in final
    if not complete and not PREVIEW:
        print(f"Week {W} is not final on ESPN yet; nothing to do."); return
    if not PREVIEW and os.path.exists(out_path) and os.environ.get("FORCE") != "1":
        print(f"{out_path} already exists; nothing to do (set FORCE=1 to refetch)."); return

    mem = {m["id"]: f'{m.get("firstName", "")} {m.get("lastName", "")}'.strip() for m in L.get("members", [])}
    st, se = L["settings"], L["settings"]["scheduleSettings"]
    out = [f'META|league={LEAGUE}|season={SEASON}|week={W}|name={st["name"]}|latest={L["status"]["latestScoringPeriod"]}|complete={1 if complete else 0}'
           f'|regweeks={se["matchupPeriodCount"]}|playoffteams={se["playoffTeamCount"]}']
    out.append("SLOTS|" + ",".join(f'{SLOT.get(int(k), "SLOT" + k)}:{v}' for k, v in st["rosterSettings"]["lineupSlotCounts"].items() if v > 0 and k not in ("20", "21")))
    out.append("TEAMS")
    for t in L["teams"]:
        name = (t.get("name") or f'{t.get("location", "")} {t.get("nickname", "")}').strip()
        out.append("|".join([str(t["id"]), name, t.get("abbrev", ""), " & ".join(mem.get(o, "") for o in t.get("owners", []))]))
    out.append("SCHED")
    for s in sched:
        if s["matchupPeriodId"] <= W + 1:
            h, a = s.get("home", {}), s.get("away") or {}
            out.append("|".join([str(s["matchupPeriodId"]), str(h.get("teamId")), js_num(h.get("totalPoints")), str(a.get("teamId", 0)), js_num(a.get("totalPoints")), s.get("winner", "")]))

    B = get([("view", "mMatchupScore"), ("view", "mBoxscore"), ("scoringPeriodId", W)])
    out.append("ROSTERS")
    for s in B["schedule"]:
        if s["matchupPeriodId"] != W: continue
        for side in (s.get("home"), s.get("away")):
            if not side: continue
            out.append(f'#{side["teamId"]}')
            for e in (side.get("rosterForCurrentScoringPeriod") or {}).get("entries", []):
                p = e["playerPoolEntry"]["player"]; stats = p.get("stats", [])
                act = next((x for x in stats if x.get("statSourceId") == 0 and x.get("scoringPeriodId") == W), None)
                proj = next((x for x in stats if x.get("statSourceId") == 1 and x.get("scoringPeriodId") == W), None)
                pts = act["appliedTotal"] if act and "appliedTotal" in act else e["playerPoolEntry"].get("appliedStatTotal", 0)
                out.append("|".join([p["fullName"], POS.get(p["defaultPositionId"], str(p["defaultPositionId"])),
                                     SLOT.get(e["lineupSlotId"], str(e["lineupSlotId"])), js_num(pts), js_num((proj or {}).get("appliedTotal", 0), 1)]))

    X = get([("view", "mTransactions2"), ("scoringPeriodId", W)])
    txs = [t for t in X.get("transactions", []) if t.get("type") in ("FREEAGENT", "WAIVER", "TRADE_PROPOSAL") and t.get("status") == "EXECUTED" and t.get("items")]
    ids = sorted({i["playerId"] for t in txs for i in t["items"]})
    nm = {}
    if ids:
        r = S.get(f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{SEASON}/players",
                  params={"scoringPeriodId": W, "view": "players_wl"},
                  headers={"x-fantasy-filter": json.dumps({"filterIds": {"value": ids}})}, timeout=30)
        if r.ok: nm = {p["id"]: p["fullName"] for p in r.json()}
    out.append("TX")
    for t in txs:
        moves = ",".join(f'{i["type"]}:{nm.get(i["playerId"], i["playerId"])}' + (f':{i.get("fromTeamId")}>{i.get("toTeamId")}' if i["type"] == "TRADE" else "") for i in t["items"])
        out.append("|".join([{"FREEAGENT": "F", "WAIVER": "W", "TRADE_PROPOSAL": "T"}[t["type"]], str(t.get("teamId")), moves]))
    out.append("LOGOURLS")
    urls = {t["id"]: t.get("logo", "") for t in L["teams"]}
    out += [f"{k}|{v}" for k, v in urls.items()]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    open(out_path, "w", encoding="utf-8").write("\n".join(out) + "\n")
    print(f"wrote {out_path} ({len(out)} lines)")
    if PREVIEW: return  # preview snapshots never update crests or latest.json

    # crests: refresh only teams whose logo URL changed
    lu_path, lg_path = os.path.join(DATA, "logo_urls.txt"), os.path.join(DATA, "logos.txt")
    old_urls = dict(l.strip().split("|", 1) for l in open(lu_path) if "|" in l) if os.path.exists(lu_path) else {}
    logos = dict(l.strip().split(" ", 1) for l in open(lg_path) if l.strip()) if os.path.exists(lg_path) else {}
    changed = [t for t, u in urls.items() if old_urls.get(str(t)) != u or f"@{t}" not in logos]
    for t in changed:
        try:
            logos[f"@{t}"] = crest(urls[t]); old_urls[str(t)] = urls[t]; print(f"crest updated for team {t}")
        except Exception as ex:
            print(f"WARNING: crest for team {t} failed: {ex}")
    if changed:
        open(lg_path, "w").write("\n".join(f"{k} {logos[k]}" for k in sorted(logos, key=lambda k: int(k[1:]))) + "\n")
        open(lu_path, "w").write("\n".join(f"{k}|{old_urls[k]}" for k in sorted(old_urls, key=int)) + "\n")
    json.dump({"week": W, "complete": True, "fetched_at": datetime.datetime.utcnow().isoformat() + "Z", "crests_updated": changed},
              open(os.path.join(DATA, "latest.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
