"""The Daily Fantasizer: in-house projections (user, 2026-11-02: "bring as much in-house as possible").

Replaces FantasyPros (weekly consensus, rest-of-season consensus, Joel Smyth list) and ESPN's projections
(QB/RB/WR/TE, kickers, D/STs) everywhere on the site. Nothing here is copied from another projection source.

Inputs (game facts only), downloaded into IH_CACHE (default .cache/nflverse, not committed):
  stats_player_week_YYYY.csv  weekly box scores          stats_team_week_YYYY.csv  team box scores (D/ST)
  roster_weekly_YYYY.csv      game-day status, team      injuries_YYYY.csv         official NFL injury reports
  games.csv                   schedule, scores, market spread/total
for the current season and the two before it. For a paid product, point download() at a licensed feed with the
same columns; nothing else changes. Upcoming weeks with no game-day status yet use the injury tag in
espn_players.json (league data).

Model (QB/RB/WR/TE): recency-weighted PPR (half-life 5 games, last season's games x0.55) and opportunity
(targets, carries, pass attempts x league points per opportunity), last 3 games, the team's implied points from
the market spread/total, the opponent's points allowed to the position, and opportunity vacated by teammates who
are out that week. One ridge fit per position on last season (so this season is never used to fit itself).
Kickers: team implied points + the kicker's recent scoring. D/STs: opponent implied points + recent D/ST scoring.
Rookies with no NFL games: a baseline by position and draft slot. Out / IR / inactive / bye = 0, doubtful 30%.

Validated 2026-11-02 with lineup.team_backtest (all 12 teams, weeks 1-7, 84 lineups): in-house 116.21 pts/week,
FantasyPros + ESPN blend 116.20, ESPN only 114.83, managers 112.88, hindsight 126.31. Error per player is equal or
lower at every position (QB 6.08 vs 6.25, RB 6.03 vs 6.07, WR 6.30 vs 6.41, TE 6.18 vs 6.21, K 3.91 vs 4.04,
D/ST 4.63 vs 4.73).

Writes data/players/:
  ih_week{K}.json   every week 1..17 (later weeks feed the rest-of-season views), same row shape the pages already read (pos rank, rank range from the
                    model's own uncertainty, start/sit grade from the rank, projected points, opponent)
  ih_ros.json       rest of season: per-game rate, games left, total, position and overall rank, weekly move
  ih_ros_hist.json  overall ROS rank per week, for the Move column
and puts the in-house numbers into the `proj` fields of espn_players.json and espn_kdst.json (no ESPN projection is
stored any more).

Usage: python3 inhouse.py            download + build + apply
       python3 inhouse.py --apply    only re-apply the saved ih_week files (no network)
"""
import csv, datetime, json, math, os, re, sys, urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "players")
CACHE = os.environ.get("IH_CACHE") or os.path.join(HERE, ".cache", "nflverse")
REL = "https://github.com/nflverse/nflverse-data/releases/download/"
GAMES = ["https://github.com/nflverse/nfldata/raw/master/data/games.csv",
         "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"]
SKILL = ("QB", "RB", "WR", "TE")
# one team code everywhere: nflverse LA/WAS/LV vs ESPN LAR/WSH
TEAMFIX = {"LA": "LAR", "WSH": "WAS", "JAC": "JAX", "OAK": "LV", "LVR": "LV", "SD": "LAC", "STL": "LAR"}
FANTASY_LAST_WEEK = 17
GRADES = [(.15, "A+"), (.3, "A"), (.45, "A-"), (.6, "B+"), (.75, "B"), (.9, "B-"), (1.05, "C+"), (1.25, "C"), (1.5, "C-"), (2.0, "D")]
STARTERS = {"QB": 12, "RB": 30, "WR": 32, "TE": 12, "K": 12, "D/ST": 12}   # 12 teams, FLEX shared by RB/WR
OUT_TAGS = {"OUT", "INJURY_RESERVE", "SUSPENSION"}
DST = {"Bills": "BUF", "Dolphins": "MIA", "Patriots": "NE", "Jets": "NYJ", "Ravens": "BAL", "Bengals": "CIN", "Browns": "CLE",
       "Steelers": "PIT", "Texans": "HOU", "Colts": "IND", "Jaguars": "JAX", "Titans": "TEN", "Broncos": "DEN", "Chiefs": "KC",
       "Raiders": "LV", "Chargers": "LAC", "Cowboys": "DAL", "Giants": "NYG", "Eagles": "PHI", "Commanders": "WAS",
       "Bears": "CHI", "Lions": "DET", "Packers": "GB", "Vikings": "MIN", "Falcons": "ATL", "Panthers": "CAR",
       "Saints": "NO", "Buccaneers": "TB", "Cardinals": "ARI", "Rams": "LAR", "49ers": "SF", "Seahawks": "SEA"}


def norm(n):
    """Same key as players.norm: no suffixes, punctuation or spaces."""
    n = n.lower().replace("’", "'")
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", n)
    return re.sub(r"[^a-z]", "", n)


def tm(t):
    return TEAMFIX.get(t, t)


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _load(name, default=None):
    p = os.path.join(OUT, name)
    if not os.path.exists(p):
        return default
    with open(p) as f:
        return json.load(f)


def _save(name, obj):
    with open(os.path.join(OUT, name), "w") as f:
        json.dump(obj, f, separators=(",", ":"), sort_keys=True)
    print("wrote", name)


# ------------------------------------------------------------------ inputs
def files(s):
    return [f"stats_player/stats_player_week_{s}.csv", f"stats_team/stats_team_week_{s}.csv",
            f"weekly_rosters/roster_weekly_{s}.csv", f"injuries/injuries_{s}.csv"]


def download(season):
    os.makedirs(CACHE, exist_ok=True)
    def get(url, dest):
        req = urllib.request.Request(url, headers={"User-Agent": "daily-fantasizer"})
        with urllib.request.urlopen(req, timeout=120) as r, open(dest + ".part", "wb") as f:
            f.write(r.read())
        os.replace(dest + ".part", dest)
    for s in (season - 2, season - 1, season):
        for rel in files(s):
            dest = os.path.join(CACHE, os.path.basename(rel))
            if s < season and os.path.exists(dest):
                continue                                             # finished seasons don't change
            try:
                get(REL + rel, dest)
            except Exception as e:
                print("download failed:", rel, e)
    for u in GAMES:
        try:
            get(u, os.path.join(CACHE, "games.csv")); break
        except Exception as e:
            print("download failed:", u, e)


def _rd(name):
    p = os.path.join(CACHE, name)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


class Store:
    def __init__(self, season):
        seasons = (season - 2, season - 1, season)
        self.season = season
        self.games = defaultdict(list)          # gsis -> [game dicts]
        self.name = {}                          # norm|pos -> gsis
        self.anyname = defaultdict(set)         # norm -> {gsis}
        self.pos = {}
        for s in seasons:
            for x in _rd(f"stats_player_week_{s}.csv"):
                if x["season_type"] != "REG":
                    continue
                p = x["position"]
                g = {"s": s, "w": int(x["week"]), "team": tm(x["team"]), "ppr": _f(x["fantasy_points_ppr"]),
                     "tgt": _f(x["targets"]), "car": _f(x["carries"]), "att": _f(x["attempts"]),
                     "k": self._kpts(x) if p == "K" else 0.0}
                self.games[x["player_id"]].append(g)
                self.pos[x["player_id"]] = p
                k = norm(x["player_display_name"])
                self.name[k + "|" + p] = x["player_id"]; self.anyname[k].add(x["player_id"])
        self.by_team = defaultdict(set)
        for pid, v in self.games.items():
            v.sort(key=lambda g: (g["s"], g["w"]))
            if self.pos.get(pid) in ("RB", "WR", "TE"):
                for g in v:
                    self.by_team[(g["s"], g["team"])].add(pid)
        self.status, self.team_of, self.draft, self.last = {}, {}, {}, {}
        for s in seasons:
            for x in _rd(f"roster_weekly_{s}.csv"):
                if x["game_type"] != "REG" or not x["gsis_id"]:
                    continue
                k = (x["gsis_id"], s, int(x["week"]))
                self.status[k] = x["status"]; self.team_of[k] = tm(x["team"])
                p = x["position"]
                n = norm(x["full_name"])
                self.last[x["gsis_id"]] = norm(x["last_name"])
                self.name.setdefault(n + "|" + p, x["gsis_id"]); self.anyname[n].add(x["gsis_id"])
                self.pos.setdefault(x["gsis_id"], p)
                if x.get("draft_number") not in (None, "", "NA"):
                    self.draft[x["gsis_id"]] = int(_f(x["draft_number"]))
        self.inj = {}
        for s in seasons:
            for x in _rd(f"injuries_{s}.csv"):
                if (x.get("season_type") or x.get("game_type")) == "REG" and x.get("report_status") and x.get("week"):
                    self.inj[(x["gsis_id"], s, int(x["week"]))] = x["report_status"]
        self.sched = {}                         # (season, week, team) -> game
        for x in _rd("games.csv"):
            s = int(x["season"])
            if s not in seasons or x["game_type"] != "REG":
                continue
            w = int(x["week"]); h, a = tm(x["home_team"]), tm(x["away_team"])
            ih = ia = None
            if x["total_line"] not in ("", "NA") and x["spread_line"] not in ("", "NA"):   # spread_line > 0 = home favored
                ih, ia = (_f(x["total_line"]) + _f(x["spread_line"])) / 2, (_f(x["total_line"]) - _f(x["spread_line"])) / 2
            hs = None if x["home_score"] in ("", "NA") else _f(x["home_score"])
            as_ = None if x["away_score"] in ("", "NA") else _f(x["away_score"])
            self.sched[(s, w, h)] = {"opp": a, "home": True, "imp": ih, "oimp": ia, "pa": as_}
            self.sched[(s, w, a)] = {"opp": h, "home": False, "imp": ia, "oimp": ih, "pa": hs}
        self.espn_tag = {}                      # gsis -> ESPN injury tag, for weeks with no game-day status yet
        self._dst(seasons)
        self._allowed()

    def find(self, name, pos, team=None):
        k = norm(name)
        if pos in ("QB", "RB", "WR", "TE", "K") and self.name.get(k + "|" + pos):
            return self.name[k + "|" + pos]
        ids = self.anyname.get(k) or set()
        if len(ids) == 1:
            return next(iter(ids))
        if team:                                                     # nicknames: same last name, team and position
            last = norm(name.replace(" Jr.", "").replace(" Sr.", "").replace(" III", "").replace(" II", "").split(" ")[-1])
            c = {pid for (pid, s, w), t in self.team_of.items() if s == self.season and t == tm(team)
                 and self.pos.get(pid) == pos and self.last.get(pid) == last}
            if len(c) == 1:
                return next(iter(c))
        return None

    @staticmethod
    def _kpts(x):
        short = sum(_f(x[c]) for c in ("fg_made_0_19", "fg_made_20_29", "fg_made_30_39"))
        return (3 * short + 4 * _f(x["fg_made_40_49"]) + 5 * (_f(x["fg_made_50_59"]) + _f(x["fg_made_60_"]))
                - _f(x["fg_missed"]) + _f(x["pat_made"]) - _f(x["pat_missed"]))

    def _dst(self, seasons):
        """D/ST points per team-game with the league's (ESPN default) D/ST scoring."""
        T = {}
        for s in seasons:
            for x in _rd(f"stats_team_week_{s}.csv"):
                if x["season_type"] == "REG":
                    T[(s, int(x["week"]), tm(x["team"]))] = x
        self.dst = defaultdict(list)
        for (s, w, t), x in T.items():
            g = self.sched.get((s, w, t))
            if not g or g["pa"] is None:
                continue
            o = T.get((s, w, g["opp"]))
            ya = (_f(o["passing_yards"]) + _f(o["rushing_yards"])) if o else 330
            pa = g["pa"]
            pts = (_f(x["def_sacks"]) + 2 * _f(x["def_interceptions"]) + 2 * _f(x["fumble_recovery_opp"])
                   + 6 * (_f(x["def_tds"]) + _f(x["special_teams_tds"]) + _f(x["fumble_recovery_tds"]))
                   + 2 * _f(x["def_safeties"]) + 2 * (_f(x["def_punt_blocks"]) + _f(x["def_fg_blocks"])))
            pts += 5 if pa == 0 else 4 if pa <= 6 else 3 if pa <= 13 else 1 if pa <= 17 else 0 if pa <= 27 else -1 if pa <= 34 else -3 if pa <= 45 else -5
            pts += 5 if ya < 100 else 3 if ya < 200 else 2 if ya < 300 else 0 if ya < 350 else -1 if ya < 400 else -3 if ya < 450 else -5 if ya < 500 else -6 if ya < 550 else -7
            self.dst[t].append((s, w, pts))
        for v in self.dst.values():
            v.sort()

    def _allowed(self):
        a = defaultdict(float)
        for pid, gs in self.games.items():
            p = self.pos.get(pid)
            if p not in SKILL:
                continue
            for g in gs:
                sc = self.sched.get((g["s"], g["w"], g["team"]))
                if sc:
                    a[(g["s"], g["w"], sc["opp"], p)] += g["ppr"]
        self.allow = a
        self._mc = {}

    def before(self, pid, s, w):
        return [g for g in self.games.get(pid, []) if (g["s"], g["w"]) < (s, w)]

    def matchup(self, opp, pos, s, w, half=6.0):
        """Opponent's PPR allowed to the position vs league, recency-weighted, shrunk toward 1."""
        key = (pos, s, w)
        if key not in self._mc:
            tot, cnt = defaultdict(float), defaultdict(float)
            for (ss, ww, d, p), v in self.allow.items():
                if p != pos or (ss, ww) >= (s, w) or ss < s - 1:
                    continue
                age = (w - ww) if ss == s else (w + 18 - ww)
                wt = 0.5 ** (age / half) * (1.0 if ss == s else 0.6)
                tot[d] += wt * v; cnt[d] += wt
            lg = sum(tot.values()) / sum(cnt.values()) if cnt else 0
            self._mc[key] = {d: (tot[d] + 3 * lg) / (cnt[d] + 3) / lg for d in cnt} if lg > 0 else {}
        return self._mc[key].get(opp, 1.0)

    def team(self, pid, s, w, espn_team=None):
        t = self.team_of.get((pid, s, w))
        if t:
            return t
        if espn_team and espn_team != "FA":
            return tm(espn_team)
        prior = [k for k in self.team_of if k[0] == pid and (k[1], k[2]) < (s, w)]
        if prior:
            return self.team_of[max(prior, key=lambda k: (k[1], k[2]))]
        gs = self.games.get(pid)
        return gs[-1]["team"] if gs else None


def wmean(gs, s, key, half, kprev):
    num = den = 0.0
    for i, g in enumerate(reversed(gs)):
        wt = 0.5 ** (i / half) * (1.0 if g["s"] == s else kprev ** (s - g["s"]))
        num += wt * g[key]; den += wt
    return (num / den if den else 0.0), den


def ridge(X, y, lam):
    if not X:
        return []
    k = len(X[0])
    A = [[sum(x[i] * x[j] for x in X) + (lam if i == j and i else 0) for j in range(k)] for i in range(k)]
    b = [sum(x[i] * t for x, t in zip(X, y)) for i in range(k)]
    for c in range(k):
        piv = max(range(c, k), key=lambda r: abs(A[r][c])); A[c], A[piv] = A[piv], A[c]; b[c], b[piv] = b[piv], b[c]
        for r in range(k):
            if r != c and A[c][c]:
                f = A[r][c] / A[c][c]; A[r] = [a - f * x for a, x in zip(A[r], A[c])]; b[r] -= f * b[c]
    return [b[i] / A[i][i] if A[i][i] else 0 for i in range(k)]


def dot(b, x):
    return sum(c * v for c, v in zip(b, x))


class Model:
    HALF, KPREV = 5.0, 0.55
    ROOKIE = {"QB": 12.0, "RB": 7.0, "WR": 6.0, "TE": 4.0}

    def __init__(self, st, half=5.0, kprev=0.55):
        self.HALF, self.KPREV = half, kprev
        self.st = st
        self._vc = {}
        self.live_from = 99                                          # set by build(): weeks not yet final
        train = st.season - 1
        self.x = self._rates(train)
        self.beta, self.sd = {}, {}
        for pos in SKILL:
            X, y = [], []
            for pid, gs in st.games.items():
                if st.pos.get(pid) != pos:
                    continue
                for g in gs:
                    if g["s"] != train or g["w"] < 2 or (g["tgt"] + g["car"] + g["att"]) == 0:
                        continue
                    f = self.feats(pid, pos, g["s"], g["w"], g["team"])
                    if f:
                        X.append(f); y.append(g["ppr"])
            self.beta[pos] = ridge(X, y, 1.0)
            # miss size grows with the projection: |error| ~ a + b * projection (sd = that x sqrt(pi/2))
            pr = [max(0.0, dot(self.beta[pos], f)) for f in X]
            self.sd[pos] = [c * math.sqrt(math.pi / 2) for c in ridge([[1.0, p] for p in pr], [abs(t - p) for t, p in zip(y, pr)], 0.0)] or [5.0, 0.3]
        X, y = [], []
        for pid, gs in st.games.items():
            if st.pos.get(pid) == "K":
                for g in gs:
                    if g["s"] == train and g["w"] >= 2:
                        X.append(self.kfeats(pid, train, g["w"], g["team"])); y.append(g["k"])
        self.kb = ridge(X, y, 1.0) or [0.0, 0.3, 0.0]
        X, y = [], []
        for t, rows in st.dst.items():
            for (s, w, pts) in rows:
                if s == train and w >= 2:
                    X.append(self.dfeats(t, s, w)); y.append(pts)
        self.db = ridge(X, y, 1.0) or [6.0, 0.0, 0.0]
        self.sd["K"], self.sd["D/ST"] = [4.5, 0.1], [5.5, 0.1]
        self._vc = {}                                                # fit-time cache used other statuses

    def _rates(self, s):
        tot = defaultdict(lambda: [0.0, 0.0])
        for pid, gs in self.st.games.items():
            p = self.st.pos.get(pid)
            if p in SKILL:
                for g in gs:
                    if g["s"] == s:
                        tot[p][0] += g["ppr"]; tot[p][1] += g["tgt"] + g["car"] + g["att"]
        return {p: (a / b if b else 1.0) for p, (a, b) in tot.items()}

    def feats(self, pid, pos, s, w, team, neutral=False):
        gs = self.st.before(pid, s, w)
        if not gs:
            return None
        ppr, n = wmean(gs, s, "ppr", self.HALF, self.KPREV)
        opp = sum(wmean(gs, s, k, self.HALF, self.KPREV)[0] for k in ("tgt", "car", "att")) * self.x.get(pos, 1)
        l3 = sum(g["ppr"] for g in gs[-3:]) / len(gs[-3:])
        cur = [g for g in gs if g["s"] == s]
        sc = self.st.sched.get((s, w, team)) or {}
        it = 1.0 if neutral else (sc.get("imp") or 22.5) / 22.5
        mr = 1.0 if neutral else self.st.matchup(sc.get("opp"), pos, s, w)
        shrink = n / (n + 1.5)
        vac = 0.0 if neutral else self.vacated(pid, pos, s, w, team)
        return [1.0, ppr * shrink, opp * shrink, l3, ppr * (it - 1), ppr * (mr - 1), min(len(cur), 8) / 8.0, vac]

    def vacated(self, pid, pos, s, w, team):
        """Targets and carries left by teammates who are out this week, handed out by each active player's share."""
        if pos == "QB":
            return 0.0
        key = (s, w, team)
        if key not in self._vc:
            mates = {}
            for q in self.st.by_team.get((s, team), ()):
                gs = [g for g in self.st.games[q] if g["s"] == s and g["w"] < w and g["team"] == team][-4:]
                if gs:
                    mates[q] = (sum(g["tgt"] for g in gs) / len(gs), sum(g["car"] for g in gs) / len(gs),
                                self.available(q, s, w, team) > 0)
            vt = sum(t for t, c, a in mates.values() if not a); vc = sum(c for t, c, a in mates.values() if not a)
            at = sum(t for t, c, a in mates.values() if a) or 1; ac = sum(c for t, c, a in mates.values() if a) or 1
            self._vc[key] = (mates, vt, vc, at, ac)
        mates, vt, vc, at, ac = self._vc[key]
        if pid not in mates:
            return 0.0
        t, c, _ = mates[pid]
        return (vt * t / at + vc * c / ac) * self.x.get(pos, 1)

    def kfeats(self, pid, s, w, team):
        gs = self.st.before(pid, s, w)
        sc = self.st.sched.get((s, w, team)) or {}
        return [1.0, sc.get("imp") or 22.5, wmean(gs, s, "k", 6.0, 0.6)[0] if gs else 7.5]

    def dfeats(self, t, s, w):
        sc = self.st.sched.get((s, w, t)) or {}
        hist = [p for (ss, ww, p) in self.st.dst.get(t, []) if (ss, ww) < (s, w)][-10:]
        return [1.0, sc.get("oimp") or 22.5, sum(hist) / len(hist) if hist else 6.0]

    def available(self, pid, s, w, team):
        if (s, w, team) not in self.st.sched:
            return 0.0                                               # bye
        stt = self.st.status.get((pid, s, w))
        if stt is not None and stt != "ACT":
            return 0.0                                               # inactive, reserve, cut
        rep = self.st.inj.get((pid, s, w))
        if w >= self.live_from and stt is None:
            # not played yet: only a ruling-out counts here (Player Stats and the lineup apply their own odds for
            # doubtful / questionable tags, so they aren't cut twice)
            tag = self.st.espn_tag.get(pid)
            return 0.0 if rep == "Out" or tag in OUT_TAGS else 1.0
        return 0.0 if rep == "Out" else 0.3 if rep == "Doubtful" else 1.0

    def rookie(self, pid, pos):
        dn = self.st.draft.get(pid) or 999
        return self.ROOKIE.get(pos, 4.0) * (1.6 if dn <= 32 else 1.25 if dn <= 64 else 1.0 if dn <= 100 else 0.6)

    def skill(self, pid, pos, s, w, team, neutral=False):
        if not team:
            return 0.0
        a = 1.0 if neutral else self.available(pid, s, w, team)
        if a == 0:
            return 0.0
        f = self.feats(pid, pos, s, w, team, neutral)
        if f is None:
            # no NFL games yet: a draft-slot baseline in the first two weeks; after that he's a backup until he plays
            return a * self.rookie(pid, pos) * (1.0 if w <= 2 else 0.1)
        return a * max(0.0, dot(self.beta[pos], f))

    def kicker(self, pid, s, w, team):
        if not team or self.available(pid, s, w, team) == 0:
            return 0.0
        return max(0.0, dot(self.kb, self.kfeats(pid, s, w, team)))

    def defense(self, t, s, w):
        return dot(self.db, self.dfeats(t, s, w)) if (s, w, t) in self.st.sched else 0.0

    def sdev(self, pos, mu):
        a, b = self.sd.get(pos, [5.0, 0.3])
        return max(1.5, a + b * mu)


# ------------------------------------------------------------------ build
def _grade(r, pos):
    q = r / STARTERS.get(pos, 12)
    return next((g for lim, g in GRADES if q <= lim), "F")


def build(season=None):
    meta = _load("meta.json", {})
    season = season or meta.get("season") or datetime.date.today().year
    cur = int(meta.get("espn_week") or 1)
    upcoming = min(18, max(cur + 1, (max(meta.get("final_weeks") or [0]) + 1)))
    P = _load("espn_players.json", []); KD = _load("espn_kdst.json", [])
    st = Store(season)
    if not st.games or not any(k[0] == season for k in st.sched):
        print("in-house: input data missing (box scores or schedule); keeping the saved projections"); return False
    M = Model(st)
    # the panel: the same model with other memory settings (half-life 4-6 games, last season x0.45-0.65), all of
    # which scored within noise of the main one in the backtest. Their spread is the "range across projections".
    panel = [M] + [Model(st, h, k) for h in (4.0, 6.0) for k in (0.45, 0.65)]
    for m in panel:
        m.live_from = cur
    ids = {}
    miss = []
    for p in P:
        pid = st.find(p["name"], p["pos"], p.get("team"))
        ids[p["name"] + "|" + p["pos"]] = pid
        if pid:
            st.espn_tag[pid] = p.get("inj", "ACTIVE")
        else:
            miss.append(p["name"])
    for p in KD:
        if p["pos"] == "K":
            pid = st.find(p["name"], "K", p.get("team")); ids[p["name"] + "|K"] = pid
            if pid:
                st.espn_tag[pid] = p.get("inj", "ACTIVE")
    stamp = datetime.datetime.now(datetime.timezone.utc)
    for w in range(1, FANTASY_LAST_WEEK + 1):
        rows = defaultdict(list)
        for p in P:
            pid = ids.get(p["name"] + "|" + p["pos"])
            team = st.team(pid, season, w, p.get("team") if w >= cur else None) if pid else tm(p.get("team", "FA"))
            mus = [m.skill(pid, p["pos"], season, w, team) for m in panel] if pid else [0.0] * len(panel)
            rows[p["pos"]].append((p, team, mus))
        for p in KD:
            if p["pos"] == "K":
                pid = ids.get(p["name"] + "|K")
                team = st.team(pid, season, w, p.get("team")) if pid else tm(p.get("team", "FA"))
                mus = [m.kicker(pid, season, w, team) for m in panel] if pid else [0.0] * len(panel)
            else:
                team = DST.get(p["name"].replace("D/ST", "").strip()) or tm(p.get("team", "FA"))
                mus = [m.defense(team, season, w) for m in panel]
            rows[p["pos"]].append((p, team, mus))
        out = {}
        for pos, lst in rows.items():
            lst.sort(key=lambda x: -x[2][0])
            # each panel member's own ranking -> the rank range
            rk = []
            for j in range(len(panel)):
                order = sorted(range(len(lst)), key=lambda i: -lst[i][2][j])
                rk.append({i: n for n, i in enumerate(order, 1)})
            res = []
            for i, (p, team, mus) in enumerate(lst):
                mu = mus[0]
                sc = st.sched.get((season, w, team)) or {}
                r = {"player_name": p["name"], "player_position_id": pos, "player_team_id": p.get("team"),
                     "r2p_pts": f"{mu:.1f}", "rank_ecr": i + 1, "pos_rank": f"{pos}{i + 1}",
                     "player_opponent": (("vs. " if sc["home"] else "@ ") + sc["opp"]) if sc else None}
                if mu > 0:
                    r["lo"], r["hi"] = round(min(mus), 1), round(max(mus), 1)
                    r["rank_min"] = str(min(x[i] for x in rk)); r["rank_max"] = str(max(x[i] for x in rk))
                    r["start_sit_grade"] = _grade(i + 1, pos)
                res.append(r)
            out[pos] = res
        _save(f"ih_week{w}.json", {"week": w, "season": season, "source": "in-house", "updated": stamp.strftime("%m/%d"),
                                   "built": stamp.strftime("%Y-%m-%dT%H:%MZ"), "pos": out})
    _ros(st, M, P, ids, season, upcoming, stamp)
    if miss:
        print(f"in-house: {len(miss)} players not matched (no projection):", ", ".join(miss[:20]))
    return True


def _ros(st, M, P, ids, season, upcoming, stamp):
    rows = []
    for p in P:
        pid = ids.get(p["name"] + "|" + p["pos"])
        team = None if p.get("team") in (None, "FA") else (st.team(pid, season, upcoming, p.get("team")) if pid else tm(p["team"]))
        rate = M.skill(pid, p["pos"], season, upcoming, team, neutral=True) if pid else 0.0
        left = sum(1 for w in range(upcoming, FANTASY_LAST_WEEK + 1) if (season, w, team) in st.sched)
        tag = p.get("inj", "ACTIVE")
        g = left * 0.25 if tag == "INJURY_RESERVE" else max(0.0, left - 1) if tag in ("OUT", "SUSPENSION") else \
            left - 0.7 if tag == "DOUBTFUL" else left - 0.07 if tag == "QUESTIONABLE" else left
        rows.append({"p": p, "rate": rate, "g": max(0.0, g), "tot": rate * max(0.0, g)})
    repl = {}
    for pos in SKILL:
        rs = sorted((r["rate"] for r in rows if r["p"]["pos"] == pos), reverse=True)
        repl[pos] = rs[STARTERS[pos]] if len(rs) > STARTERS[pos] else 0.0
    for r in rows:
        d = r["rate"] - repl[r["p"]["pos"]]
        # value over a replacement starter for the games he'll play; below replacement, by how far below;
        # no games left (free agent with no team, season over) last
        r["vor"] = d * r["g"] if d > 0 else d
        r["key"] = (r["g"] > 0, r["vor"], r["tot"])
    rows.sort(key=lambda r: r["key"], reverse=True)
    hist = _load("ih_ros_hist.json", {})
    prev_w = max((int(k) for k in hist if int(k) < upcoming), default=None)
    prev = hist.get(str(prev_w), {}) if prev_w else {}
    posn = defaultdict(int)
    by_pos_tot = {pos: sorted((r for r in rows if r["p"]["pos"] == pos), key=lambda r: -r["tot"]) for pos in SKILL}
    prank = {id(r): i for pos in SKILL for i, r in enumerate(by_pos_tot[pos], 1)}
    out, now = [], {}
    for i, r in enumerate(rows, 1):
        p = r["p"]; key = norm(p["name"]) + "|" + p["pos"]
        now[key] = i
        out.append({"player_name": p["name"], "player_position_id": p["pos"], "player_team_id": p.get("team"),
                    "rank_ecr": i, "pos_rank": f'{p["pos"]}{prank[id(r)]}',
                    "player_ecr_delta": (prev[key] - i) if key in prev else None,
                    "ros_ppg": round(r["rate"], 2), "ros_games": round(r["g"], 1), "ros_pts": round(r["tot"], 1), "r2p_pts": None})
    hist[str(upcoming)] = now
    _save("ih_ros.json", {"updated": stamp.strftime("%m/%d"), "week": upcoming, "source": "in-house", "players": out})
    _save("ih_ros_hist.json", hist)


def apply():
    """Put the in-house numbers into the proj fields the pages read (espn_players.json, espn_kdst.json)."""
    weeks = {}
    for fn in os.listdir(OUT):
        m = re.match(r"ih_week(\d+)\.json$", fn)
        if m:
            weeks[int(m.group(1))] = _load(fn)
    if not weeks:
        print("in-house: no ih_week files to apply"); return
    val = defaultdict(dict)
    for w, f in weeks.items():
        for pos, rows in f["pos"].items():
            for r in rows:
                val[norm(r["player_name"]) + "|" + pos][str(w)] = float(r["r2p_pts"])
    for fn in ("espn_players.json", "espn_kdst.json"):
        L = _load(fn)
        if not L:
            continue
        for p in L:
            p["proj"] = val.get(norm(p["name"]) + "|" + p["pos"], {})
        _save(fn, L)


def lookup(week):
    """norm(name)|pos -> in-house projection for one week (facts.py uses it for the weekly dumps)."""
    f = _load(f"ih_week{week}.json")
    if not f:
        return {}
    return {norm(r["player_name"]) + "|" + pos: float(r["r2p_pts"]) for pos, rows in f["pos"].items() for r in rows}


if __name__ == "__main__":
    if "--apply" not in sys.argv:
        meta = _load("meta.json", {})
        download(meta.get("season") or datetime.date.today().year)
        build()
    apply()
