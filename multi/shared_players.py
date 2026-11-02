"""Fetch the league-independent player data once per weekly run (used by every league's Player Stats tab).

  python3 multi/shared_players.py SHARED_DIR

Runs the regular fetch_players.py into SHARED_DIR/data/players, reading ESPN's player pool from ESPN's public
default PPR league (no cookies needed) instead of a specific league. Each league's build then copies these
files and overlays its own owners (ESPN leagues: its own player pool and scoring; Yahoo leagues: yahoo.py --players).
"""
import os, subprocess, sys, datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
shared = os.path.abspath(sys.argv[1])
os.makedirs(os.path.join(shared, "data", "players"), exist_ok=True)
season = os.environ.get("FZ_SEASON") or str(datetime.date.today().year if datetime.date.today().month >= 8 else datetime.date.today().year - 1)
env = dict(os.environ, FZ_HOME=shared, FZ_PLATFORM="shared", FZ_SEASON=season,
           FZ_ESPN_BASE=f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/segments/0/leaguedefaults/3")
env.pop("ESPN_S2", None); env.pop("ESPN_SWID", None)
sys.exit(subprocess.run([sys.executable, os.path.join(REPO, "fetch_players.py")], cwd=shared, env=env).returncode)
