"""The Daily Fantasizer, any league: automatic copy (no AI, no hand-writing).

Usage (from a league folder): python3 autocopy.py W   → data/weekW_copy.json
Reads data/weekW_facts.json (facts.py) and league.json. Writes the same schema the hand-written
editions use (data/week7_copy.json), so render.py doesn't know the difference.

Rules carried over from the runbook: every number comes from the facts; team names go in as {T7}/{S7}
tokens; roast lineup decisions and results, never people; upset headlines <= 6 words, texts <= 30 words;
the biggest-news section owns its games, so the hero and lead pick a different game.
Variety: each slot has several phrasings; the pick is a stable hash of week + teams, so a rebuild of the
same week gives the same words and different weeks read differently.
"""
import hashlib, json, sys

W = int(sys.argv[1])
F = json.load(open(f"data/week{W}_facts.json"))
LG = json.load(open("league.json"))
TF = {int(k): v for k, v in F["this_week"].items()}
SEA = {int(k): v for k, v in F["season"].items()}
TEAMS = {int(k): v for k, v in F["teams"].items()}
GAMES = F["games"]
L = F["league"]
UPS = F.get("upsets", [])
NT = len(TEAMS)


def pick(options, *salt):
    h = int(hashlib.sha256(("|".join(map(str, (W,) + salt))).encode()).hexdigest(), 16)
    return options[h % len(options)]


def g(x):
    return f"{x:g}"


def f2(x):
    return f"{x:.2f}"


def last(n):
    if "D/ST" in n:
        return n.replace(" D/ST", " D")
    for s in (" Jr.", " Sr.", " III", " II", " IV"):
        n = n.replace(s, "")
    return n.split(" ")[-1]


def rec(t):
    s = SEA[t]
    return f'{s["w"]}–{s["l"]}' + (f'–{s["t"]}' if s.get("t") else "")


def words(s, n):
    """Trim to n words without cutting a {T7} token."""
    w = s.split()
    return s if len(w) <= n else " ".join(w[:n]).rstrip(",;:") + "."


def allplay_week(t):
    me = TF[t]["week_pts"]
    return sum(me > TF[o]["week_pts"] for o in TF if o != t), sum(me < TF[o]["week_pts"] for o in TF if o != t)


def top_starters(t, n=3):
    return sorted(TF[t]["starters"], key=lambda s: -s[3])[:n]


def busts(t):
    """Starters who missed their projection by the most (name, pos, slot, pts, proj)."""
    return sorted([s for s in TF[t]["starters"] if s[4] > 0], key=lambda s: s[3] - s[4])


def game_of(t):
    return next(x for x in GAMES if t in (x["winner"], x["loser"]))


ups_pairs = [{u["winner"], u["loser"]} for u in UPS]

# ---------------- biggest news (upsets, heartbreakers, blowout) ----------------
upsets = {}
for u in UPS:
    w, l = u["winner"], u["loser"]
    # the cards already show bench points, the benched star and the losing streak as chips: the words tell
    # who won it and who didn't show up
    bits = []
    tw, bl = top_starters(w, 1), busts(l)
    if u["upset"]:
        head = pick([f"No. {u['w_rank_pre']} Shocks No. {u['l_rank_pre']}", "Nobody Saw This Coming",
                     "The Underdog Bites Back", f"Upset Special, Week {W}"], w, l)
        wp = u['w_pre']; wrec = f"{wp['w']}–{wp['l']}" + (f"–{wp['t']}" if wp.get('t') else "")
        bits.append(f"{{S{w}}} came in {wrec} and beat {{S{l}}} by {u['margin']:.2f}.")
    elif u["heartbreaker"]:
        head = pick(["Lost by a Hair", "So Close It Hurts", f"Short by {u['margin']:.2f}", "One Play Away"], w, l)
        bits.append(f"{{S{l}}} lost to {{S{w}}} by {u['margin']:.2f}.")
    else:
        head = pick(["Blowout of the Week", f"Buried by {u['margin']:.0f}", "Not Close. At All.", "A Total Wipeout"], w, l)
        bits.append(f"{{S{w}}} won by {u['margin']:.2f}, the biggest margin of week {W}.")
    if tw:
        bits.append(f"{tw[0][0]} led the way with {g(tw[0][3])}.")
    if bl and bl[0][3] - bl[0][4] <= -5:
        bits.append(f"{{S{l}}} got {g(bl[0][3])} from {bl[0][0]}, projected for {g(bl[0][4])}.")
    upsets[f"{w}-{l}"] = {"headline": head, "text": words(" ".join(bits), 30)}

# ---------------- hero + lead: the week's best game not already in the news ----------------
others = [x for x in GAMES if {x["winner"], x["loser"]} not in ups_pairs] or GAMES
hero_g = max(others, key=lambda x: TF[x["winner"]]["week_pts"])
hw, hl = hero_g["winner"], hero_g["loser"]
apw, apl = allplay_week(hw)
hero = {"winner": hw, "loser": hl,
        "big": f"{apw}–{apl}" if apw + apl else f2(TF[hw]["week_pts"]),
        "label": "all-play record, beat every team" if apl == 0 else "all-play record this week"}

leader = F["ranking"][0]
ts = top_starters(hw, 3)
lead_head = pick([f"{{S{hw}}} Runs It Up", f"{{S{hw}}} Hangs {TF[hw]['week_pts']:.0f}", f"Big Day for {{S{hw}}}"], hw)
# headlines are escaped text, not filled: use the short name itself
SHORT = {int(k): v for k, v in (LG.get("short_names") or {}).items()}
for t in TEAMS:
    SHORT.setdefault(t, TEAMS[t]["name"])
lead_head = lead_head.replace(f"{{S{hw}}}", SHORT[hw])
para1 = (f"{{T{hw}}} scored {f2(TF[hw]['week_pts'])} and beat {{S{hl}}} by {hero_g['margin']:.2f}. "
         + ", ".join(f"{s[0]} {g(s[3])}" for s in ts) + " led the way.")
p2 = []
lb = busts(hl)
if lb and lb[0][3] - lb[0][4] <= -5:
    p2.append(f"{{S{hl}}} got {g(lb[0][3])} from {lb[0][0]} on a {g(lb[0][4])} projection.")
lsea = SEA[leader]
p2.append(f"At the top, {{S{leader}}} is {rec(leader)} with {f2(lsea['pf'])} points for.")
if SEA[hw]["streak"].startswith("W") and int(SEA[hw]["streak"][1:]) >= 3:
    p2.append(f"{{S{hw}}} has won {SEA[hw]['streak'][1:]} straight.")
lead = {"kicker": "Page one", "headline": lead_head,
        "deck": f"Week {W}'s top score, {apw} of {NT - 1} teams beaten in all-play.",
        "paragraphs": [para1, " ".join(p2)]}

# ---------------- sidebar: "Strange but true" = biggest beat vs projection ----------------
beats = sorted(((t, s) for t in TF for s in TF[t]["starters"] if s[4] >= 0), key=lambda x: -(x[1][3] - x[1][4]))
side = []
if beats:
    bt, bs = beats[0]
    rows = [{"label": last(s[0]), "value": round(s[3], 2), **({"alt": True} if s[0] == bs[0] else {})} for s in top_starters(bt, 4)]
    if not any(r.get("alt") for r in rows):
        rows[-1] = {"label": last(bs[0]), "value": round(bs[3], 2), "alt": True}
    side.append({"style": "hi", "kicker": "Strange but true",
                 "title": pick([f"{last(bs[0])} Out of Nowhere", "Nobody Projected This", f"{g(bs[4])} Projected, {g(bs[3])} Scored"], bt),
                 "viz": {"type": "bars", "rows": rows},
                 "text": f"{bs[0]} was projected for {g(bs[4])} and scored {g(bs[3])} for {{S{bt}}}, "
                         f"{bs[3] - bs[4]:+.1f} over the number."})
else:
    side.append({"style": "hi", "kicker": "Strange but true", "title": "Quiet Week", "text": "Every starter landed near the projection."})

# ---------------- game recaps ----------------
recaps = {}
for x in GAMES:
    w, l = x["winner"], x["loser"]
    if {w, l} in ups_pairs:
        recaps[f"{w}-{l}"] = {"headline": "See the top of the page", "text": f"{{S{w}}} {f2(x['ws'])}, {{S{l}}} {f2(x['ls'])}."}
        continue
    if (w, l) == (hw, hl):
        recaps[f"{w}-{l}"] = {"headline": "See Page One", "text": f"{{S{l}}} scored {f2(x['ls'])}. Not nearly enough."}
        continue
    tw = top_starters(w, 2)
    head = pick([f"{last(tw[0][0])} Carries It", f"{last(tw[0][0])} Goes Off", f"{SHORT[w]} Gets There"], w, l)
    if x["margin"] < 5:
        head = pick(["Survived by a Nose", "Down to the Wire", "Photo Finish"], w, l)
    txt = f"{tw[0][0]} {g(tw[0][3])}" + (f", {tw[1][0]} {g(tw[1][3])}." if len(tw) > 1 else ".")
    bl = busts(l)
    if bl and bl[0][3] - bl[0][4] <= -6:
        txt += f" {SHORT[l]}'s {last(bl[0][0])}: {g(bl[0][3])} on a {g(bl[0][4])} projection."
    if x["loser_optimal_would_win"]:
        txt += " The loser's best lineup would have won."
    recaps[f"{w}-{l}"] = {"headline": words(head, 6), "text": txt}

# ---------------- manager of the week ----------------
perfect = [t for t in TF if TF[t]["left_on_bench"] == 0]
if perfect:
    mt = max(perfect, key=lambda t: TF[t]["week_pts"])
    big, big_label = "0.00", "pts left on bench"
    why = f"A perfect lineup: every starter was the right call, worth {f2(TF[mt]['week_pts'])}."
else:
    winners = [x["winner"] for x in GAMES if not x["tie"]]
    mt = min(winners or list(TF), key=lambda t: TF[t]["left_on_bench"])
    big, big_label = f2(TF[mt]["left_on_bench"]), "pts left on bench"
    why = f"Fewest points left on the bench of any winner, and {f2(TF[mt]['week_pts'])} on the board."
smart = sorted(TF[mt]["starters"], key=lambda s: -(s[3] - s[4]))
if smart and smart[0][3] - smart[0][4] > 5:
    why += f" Started {smart[0][0]} on a {g(smart[0][4])} projection; he scored {g(smart[0][3])}."
honor = {"team": mt, "big": big, "big_label": big_label, "kicker": "Manager of the week", "title": TEAMS[mt]["name"], "text": why}

# ---------------- police blotter: worst bench decisions ----------------
blotter = []
for t in sorted(TF, key=lambda t: -TF[t]["left_on_bench"]):
    if len(blotter) >= 4 or TF[t]["left_on_bench"] <= 0:
        break
    sh, ss = TF[t]["should_have_started"], TF[t]["should_have_sat"]
    zero = TF[t]["started_zero_projection"]
    if zero:
        title, text = "Started a zero", f"{zero[0]} was projected for zero and started anyway."
    elif sh and ss:
        a, b = sh[0], ss[0]
        title = pick(["Benched the wrong guy", "Wrong call at " + a[1], "Lineup malpractice"], t)
        text = f"{a[0]} {g(a[2])} sat. {b[0]} {g(b[2])} started."
    else:
        title, text = "Points left behind", f"{TF[t]['left_on_bench']:.1f} points stayed on the bench."
    blotter.append({"team": t, "title": title, "text": text})
if not blotter:
    blotter.append({"team": L["high"], "title": "No crimes reported", "text": "Every team started its best lineup. Suspicious."})

# ---------------- missing persons: biggest misses vs projection (starters only) ----------------
missing, seen = [], set()
for t, name, pos, proj, pts, diff in L.get("worst_busts", []):
    if len(missing) >= 4 or diff > -5 or t in seen:
        continue
    if not any(s[0] == name for s in TF[t]["starters"]):
        continue
    seen.add(t)
    missing.append({"team": t, "player": name,
                    "text": pick([f"Projected {g(proj)}. Found {g(pts)}.", "Last seen near the end zone. Never arrived.",
                                  f"{pos}, presumed missing.", "Reward offered for any information."], t, name)})
if not missing:  # render.py needs at least one starter
    t = L["low"]; s = busts(t)[0] if busts(t) else TF[t]["starters"][0]
    missing.append({"team": t, "player": s[0], "text": f"Projected {g(s[4])}. Found {g(s[3])}."})

# ---------------- pecking order notes ----------------
pecking = {}
for t in TEAMS:
    s, tw = SEA[t], TF[t]
    if tw["season_high"]:
        n = f"Season high, {f2(tw['week_pts'])}."
    elif tw["season_low"]:
        n = f"Season low, {f2(tw['week_pts'])}."
    elif s["streak"][0] in "WL" and int(s["streak"][1:]) >= 3:
        n = f"{s['streak'][1:]} straight {'wins' if s['streak'][0] == 'W' else 'losses'}."
    elif s["luck"] <= -1:
        n = f"Unlucky: {s['expected_wins']:.1f} wins earned in all-play, {s['w']} on the board."
    elif s["luck"] >= 1:
        n = f"Lucky: {s['w']} wins on {s['expected_wins']:.1f} earned."
    else:
        n = f"All-play {s['allplay']}."
    pecking[str(t)] = n

# ---------------- next week's lines ----------------
forecast = {}
for n in F.get("next_week", []):
    fav, dog = n["fav"], n["dog"]
    if n["spread"] <= 3:
        b = f"{g(n['spread'])} points. Closest line of the week."
    elif n["spread"] == max(x["spread"] for x in F["next_week"]):
        b = f"{{S{fav}}} by {g(n['spread'])}, the biggest spread of the week."
    else:
        b = f"{{S{fav}}} favored by {g(n['spread'])}. O/U {g(n['ou'])}."
    forecast[f"{n['home']}-{n['away']}"] = b

copy = {"week": W, "hero": hero, "lead": lead, "sidebar": side, "recaps": recaps, "honor": honor,
        "blotter": blotter, "missing": missing, "pecking_notes": pecking, "forecast_blurbs": forecast, "upsets": upsets}
ann = [a for a in LG.get("announcements", []) if a.get("week") == W]
if ann:
    copy["announcement"] = ann[0]
json.dump(copy, open(f"data/week{W}_copy.json", "w"), indent=1, ensure_ascii=False)
print(f"wrote data/week{W}_copy.json (automatic copy)")
