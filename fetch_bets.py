"""Save every bet from the league office (Betting tab) to data/bets/placed.json, for bets.settle() on Tuesdays.
GitHub Actions only (the workspace can't reach Google). The league office URL is league.json "proposals_api"."""
import json, os, sys
import requests

api = json.load(open("league.json")).get("proposals_api")
if not api:
    sys.exit("no proposals_api in league.json")
r = requests.get(api, timeout=60)
r.raise_for_status()
st = r.json()
if not st.get("ok"):
    sys.exit("league office error: %s" % st.get("error"))
os.makedirs("data/bets", exist_ok=True)
with open("data/bets/placed.json", "w") as f:
    json.dump(st.get("bets", []), f, separators=(",", ":"), sort_keys=True)
print("saved", len(st.get("bets", [])), "bets")
