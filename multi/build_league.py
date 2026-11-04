"""The Daily Fantasizer, any league: build one league's paper end to end.

  python3 multi/build_league.py --config league.cfg.json --work WORKDIR --out OUTDIR [--shared SHARED] [--no-fetch]

config (written by the website for each build; secrets arrive here, never in the repo):
  {"slug": "k3x9q2", "platform": "espn" | "yahoo", "league_id": "1196354715" (ESPN) | "461.l.12345" (Yahoo league key),
   "season": 2026, "espn_s2": "...", "swid": "{...}"  (ESPN private leagues only), "yahoo_token": "..." (Yahoo only),
   "features": {"rules": false, "bets": false}, "accent": "#33658a", "short_names": {"3": "Doughboys"},
   "office_api": "https://<site>/api/office/<slug>"  (only when Rule Changes or Betting is on)}

WORKDIR keeps the league's data between weeks (the weekly job restores and saves it), so only new weeks are fetched.
The code itself is never copied: the league folder holds symlinks to the repo's pipeline, so the Men Fantasizing
pipeline and every other league's paper are built by exactly the same files.

SHARED is a folder of league-independent player data (nflverse, FantasyPros, NFL schedule, ESPN's player pool
under its default PPR scoring), fetched once per run by multi/shared_players.py; each league then overlays its own
owners (and, on ESPN, its own scoring, kickers/defenses and waiver order).
Exit codes: 0 built, 3 no completed week yet (nothing to publish), anything else = failure.
"""
import argparse, glob, json, os, re, shutil, subprocess, sys, datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MULTI = os.path.join(REPO, "multi")
FILLER = {"the", "big", "team", "#1", "fantasy", "football", "club", "fc", "ffc", "of"}


def run(args, cwd, env, check=True):
    print("$", " ".join(args), flush=True)
    r = subprocess.run(args, cwd=cwd, env=env)
    if check and r.returncode != 0:
        sys.exit(f"step failed ({r.returncode}): {' '.join(args)}")
    return r.returncode


def prepare(work):
    os.makedirs(os.path.join(work, "data", "players"), exist_ok=True)
    os.makedirs(os.path.join(work, "data", "bets"), exist_ok=True)
    links = glob.glob(os.path.join(REPO, "*.py")) + [os.path.join(REPO, "template.html"), os.path.join(REPO, "rules_presets.json"),
                                                     os.path.join(MULTI, "autocopy.py")]
    for src in links:
        dst = os.path.join(work, os.path.basename(src))
        if os.path.islink(dst) or os.path.exists(dst):
            os.remove(dst)
        os.symlink(src, dst)


def short_name(name):
    name = re.sub(r"\s+", " ", name).strip()
    if len(name) <= 18:   # keep whole names that fit the narrow columns ("Per My Last Email")
        return name
    words = [w for w in name.split(" ") if w.lower().strip("'’s") not in FILLER] or name.split(" ")
    two = " ".join(words[:2])
    if len(two) <= 16:
        return two
    return max(words, key=len)[:16]


def read_raw(path):
    meta, slots, teams = {}, {}, {}
    sec = None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("META|"):
            meta = dict(kv.split("=", 1) for kv in line.split("|")[1:])
        elif line.startswith("SLOTS|"):
            slots = {k: int(v) for k, v in (s.split(":") for s in line[6:].split(","))}
        elif line in ("TEAMS", "SCHED", "ROSTERS", "TX", "LOGOURLS"):
            sec = line
        elif sec == "TEAMS" and line.strip():
            p = line.split("|"); teams[int(p[0])] = p[1]
    return meta, slots, teams


def fetch_espn(work, env, cfg):
    env = dict(env)
    if cfg.get("espn_s2") and cfg.get("swid"):
        env["ESPN_S2"], env["ESPN_SWID"] = cfg["espn_s2"], cfg["swid"]
    else:
        env.pop("ESPN_S2", None); env.pop("ESPN_SWID", None)
    run([sys.executable, "fetch_espn.py"], work, env)
    lj = os.path.join(work, "data", "latest.json")
    if not os.path.exists(lj):
        return 0
    W = json.load(open(lj))["week"]
    for k in range(1, W):  # backfill: season sections re-score every week from 1
        if not os.path.exists(os.path.join(work, "data", f"week{k}_raw.txt")):
            run([sys.executable, "fetch_espn.py"], work, dict(env, WEEK=str(k)))
    json.dump({"week": W, "complete": True, "fetched_at": datetime.datetime.utcnow().isoformat() + "Z", "platform": "espn"}, open(lj, "w"), indent=1)
    run([sys.executable, "fetch_trades.py"], work, env, check=False)
    run([sys.executable, "-c", "import fetch_players as f\ncur, final = f.espn()\n"
         "for step in (f.espn_waivers, lambda: f.espn_kdst(cur)):\n    try: step()\n    except Exception as e: print('optional step failed:', e)"],
        work, env, check=False)
    apply_projections(work, env)
    return W


def apply_projections(work, env):
    """The league's own player pool was just rewritten (owners, scoring): put our projections back into it, as the
    weekly Men Fantasizing run does. Without this, Rankings, Projections, Start/Sit, Rankings vs. Actuals and the
    Trade Matchmaker come out empty."""
    run([sys.executable, "-c", "import inhouse\ninhouse.apply()"], work, dict(env, FZ_HOME=work), check=False)


def fetch_yahoo(work, env, cfg):
    env = dict(env, YAHOO_TOKEN=cfg.get("yahoo_token", ""), FZ_LEAGUE_KEY=str(cfg["league_id"]))
    run([sys.executable, os.path.join(MULTI, "platforms", "yahoo.py")], work, env)
    run([sys.executable, os.path.join(MULTI, "platforms", "yahoo.py"), "--players"], work, env)
    apply_projections(work, env)
    lj = os.path.join(work, "data", "latest.json")
    return json.load(open(lj))["week"] if os.path.exists(lj) else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--shared")
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args()
    cfg = json.load(open(a.config))
    work, out = os.path.abspath(a.work), os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    prepare(work)
    platform = cfg.get("platform", "espn")
    env = dict(os.environ, FZ_HOME=work, FZ_PLATFORM=platform, FZ_SEASON=str(cfg.get("season") or datetime.date.today().year))
    if platform == "espn":
        env["FZ_LEAGUE_ID"] = str(cfg["league_id"])

    # shared player data first (the Yahoo adapter reads FantasyPros projections from it)
    if a.shared:
        dst = os.path.join(work, "data", "players")
        for f in glob.glob(os.path.join(a.shared, "data", "players", "*")):
            shutil.copy2(f, dst)

    # league.json (office API before fetching, so fetch_bets can read it)
    feats = cfg.get("features") or {}
    office = cfg.get("office_api", "") if (feats.get("rules") or feats.get("bets")) else ""
    lpath = os.path.join(work, "league.json")
    LG = json.load(open(lpath)) if os.path.exists(lpath) else {}
    LG.update({"proposals_api": office})
    json.dump(LG, open(lpath, "w"), indent=1, ensure_ascii=False)

    if not a.no_fetch:
        W = fetch_espn(work, env, cfg) if platform == "espn" else fetch_yahoo(work, env, cfg)
        if office and feats.get("bets"):
            run([sys.executable, "fetch_bets.py"], work, env, check=False)
    else:
        lj = os.path.join(work, "data", "latest.json")
        W = json.load(open(lj))["week"] if os.path.exists(lj) else 0
    if not W:
        print("No completed week yet: nothing to publish.")
        json.dump({"week": 0, "built_at": datetime.datetime.utcnow().isoformat() + "Z", "status": "waiting"}, open(os.path.join(out, "meta.json"), "w"))
        sys.exit(3)

    meta, slots, teams = read_raw(os.path.join(work, "data", f"week{W}_raw.txt"))
    shorts = {str(t): (cfg.get("short_names") or {}).get(str(t)) or short_name(n) for t, n in teams.items()}
    lineup = [s for s, n in slots.items() for _ in range(n)]
    host_url = (f"https://fantasy.espn.com/football/league?leagueId={cfg['league_id']}&seasonId={meta.get('season')}" if platform == "espn"
                else f"https://football.fantasysports.yahoo.com/f1/{str(cfg['league_id']).split('.l.')[-1]}")
    LG.update({"league_id": meta.get("league"), "season": int(meta.get("season") or env["FZ_SEASON"]), "league_name": meta.get("name") or "Our League",
               "league_format": f"{len(teams)} teams · head-to-head points", "price": "Price: one bad bench decision",
               "volume": 1, "espn_url": host_url, "short_names": shorts,
               "lore": LG.get("lore", []), "announcements": LG.get("announcements", []), "repo": "", "owner_team": 1,
               "trade_block_min_teams": max(1, round(len(teams) * 0.8)), "upset_top_n": LG.get("upset_top_n", 4),
               "upset_win_gap": LG.get("upset_win_gap", 2), "heartbreaker_margin": LG.get("heartbreaker_margin", 2),
               "proposals_api": office, "lineup": lineup, "platform": platform})
    json.dump(LG, open(lpath, "w"), indent=1, ensure_ascii=False)

    run([sys.executable, "facts.py", f"data/week{W}_raw.txt"], work, env)
    run([sys.executable, "autocopy.py", str(W)], work, env)
    run([sys.executable, "render.py", str(W)], work, env)
    page = os.path.join(work, f"daily-fantasizer-week{W}.html")
    pcfg = os.path.join(work, "post.json")
    json.dump({"platform": platform, "features": feats, "accent": cfg.get("accent"), "teams": len(teams)}, open(pcfg, "w"))
    run([sys.executable, os.path.join(MULTI, "postprocess.py"), page, os.path.join(out, f"week{W}.html"), pcfg], work, env)
    shutil.copy2(os.path.join(out, f"week{W}.html"), os.path.join(out, "index.html"))
    lines = os.path.join(work, "data", "bets", f"lines{W + 1}.json")
    if feats.get("bets") and os.path.exists(lines):
        os.makedirs(os.path.join(out, "bets"), exist_ok=True)
        shutil.copy2(lines, os.path.join(out, "bets", f"lines{W + 1}.json"))
    json.dump({"week": W, "built_at": datetime.datetime.utcnow().isoformat() + "Z", "status": "ok", "league_name": LG["league_name"],
               "teams": [{"id": t, "name": n, "short": shorts[str(t)]} for t, n in sorted(teams.items())]},
              open(os.path.join(out, "meta.json"), "w"), indent=1)
    print(f"built week {W} for {LG['league_name']} → {out}")


if __name__ == "__main__":
    main()
