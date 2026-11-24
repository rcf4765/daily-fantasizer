"""Breaking News: clinched and eliminated (user, 2026-11-24: "on top of the paper section put a 'breaking news' area and
put a write up for when a team gets eliminated or gets into the playoffs"; "keep it simple").

A small box at the very top of This Week's Paper, above the stat tiles. It appears only in a week when a team
clinches a playoff spot, clinches a first-round bye, or is eliminated, one item per team: crest, a CLINCHED / BYE /
ELIMINATED stamp, a headline and a short write-up. After the last regular-season week it announces the final field.
Write-ups come from `data/weekN_copy.json` "breaking": {"<teamId>": {"headline": ..., "text": ...}} ({T7}/{S7}
tokens work); a team without copy gets a plain automatic line and render.py prints a NOTE.

The math is exact, not simulated, and conservative about ties: standings go by wins (a tie counts half), and because
the tiebreaker (points for) can still swing, a team only counts as clinched if it finishes above the line in EVERY way
the remaining games can go, even when every tie on wins goes against it; eliminated only if it misses in every way,
even when every tie goes its way. `python3 playoffs.py W` prints every team's status after week W.
"""
import itertools, math, re


def _flow_ok(games, cap, need_total):
    """games: list of (a, b) teams, each game gives one win to a or b. cap: team -> wins it may still take.
    Returns the number of games that can be placed (max flow), by augmenting paths."""
    owner = {}  # game index -> team
    load = {t: 0 for t in cap}

    def place(gi, seen):
        for t in games[gi]:
            if t not in cap or t in seen:
                continue
            seen.add(t)
            if load[t] < cap[t]:
                owner[gi] = t; load[t] += 1
                return True
            for gj, o in list(owner.items()):
                if o == t and place(gj, seen):
                    owner[gi] = t
                    return True
        return False

    n = 0
    for gi in range(len(games)):
        if place(gi, set()):
            n += 1
            if need_total is not None and n >= need_total:
                return n
    return n


def _split(t, left, t_result):
    """t's remaining games are decided by t_result(game) -> True if t wins. Returns (t_extra_wins, bonus, others)
    where bonus are wins handed to t's opponents and others the games not involving t."""
    tw, bonus, others = 0, {}, []
    for g in left:
        _, h, a = g
        if t in (h, a):
            if t_result(g):
                tw += 1
            else:
                o = a if h == t else h
                bonus[o] = bonus.get(o, 0) + 1
        else:
            others.append((h, a))
    return tw, bonus, others


def _can_push_out(t, w0, left, k, t_result):
    """True if the remaining games can leave k or more rivals with at least t's wins (t's games decided by t_result)."""
    tw, bonus, others = _split(t, left, t_result)
    target = w0[t] + tw
    rivals = [u for u in w0 if u != t]
    for S in itertools.combinations(rivals, k):
        need = {u: max(0, math.ceil(target - w0[u] - bonus.get(u, 0))) for u in S}
        if any(need[u] > sum(1 for g in others if u in g) for u in S):
            continue
        tot = sum(need.values())
        if tot == 0 or _flow_ok([g for g in others if g[0] in need or g[1] in need], need, tot) >= tot:
            return True
    return False


def _can_squeeze_in(t, w0, left, k, t_result):
    """True if the remaining games can leave at most k-1 rivals with MORE wins than t (ties going t's way)."""
    tw, bonus, others = _split(t, left, t_result)
    best = w0[t] + tw
    rivals = [u for u in w0 if u != t]
    for S in itertools.combinations(rivals, max(0, k - 1)):
        cap = {}
        ok = True
        for u in rivals:
            if u in S:
                cap[u] = 10 ** 6
            else:
                c = math.floor(best - w0[u] - bonus.get(u, 0) + 1e-9)
                if c < 0:
                    ok = False; break
                cap[u] = c
        if ok and _flow_ok(others, cap, None) == len(others):
            return True
    return False


def status(w0, left, spots, byes=0):
    """w0: team -> wins so far (ties count half); left: [(wk, home, away)] still to play; spots: playoff teams.
    Returns team -> dict(clinched, bye, eliminated, win_in, lose_out, win_out_in, next_opp)."""
    out = {}
    nxt = min((g[0] for g in left), default=None)
    for t in w0:
        mine = [g for g in left if t in g[1:]]
        first = next((g for g in mine if g[0] == nxt), None)
        lose_all = lambda g: False
        win_all = lambda g: True
        r = dict(next_opp=(first[2] if first and first[1] == t else first[1]) if first else None)
        r["clinched"] = not _can_push_out(t, w0, left, spots, lose_all)
        r["bye"] = bool(byes) and not _can_push_out(t, w0, left, byes, lose_all)
        r["eliminated"] = not _can_squeeze_in(t, w0, left, spots, win_all)
        r["bye_out"] = bool(byes) and not _can_squeeze_in(t, w0, left, byes, win_all)
        r["win_in"] = r["lose_out"] = r["win_out_in"] = False
        if not r["clinched"] and not r["eliminated"] and first:
            r["win_in"] = not _can_push_out(t, w0, left, spots, lambda g: g is first)
            r["lose_out"] = not _can_squeeze_in(t, w0, left, spots, lambda g: g is not first)
            r["win_out_in"] = not _can_push_out(t, w0, left, spots, win_all)
        out[t] = r
    return out


def byes_for(spots):
    """First-round byes in a single-elimination bracket of `spots` teams (6 -> 2, 4 -> 0, 7 -> 1)."""
    return (1 << max(0, (spots - 1).bit_length())) - spots if spots > 1 else 0


def _wins(SD, weeks, teams):
    w, pf = {t: 0.0 for t in teams}, {t: 0.0 for t in teams}
    for k in weeks:
        sc, opp = SD[k]["score"], SD[k]["opp"]
        for t in teams:
            if t not in sc:
                continue
            pf[t] += sc[t]
            o = opp.get(t)
            if o is None:
                continue
            w[t] += 1 if sc[t] > sc[o] else 0.5 if sc[t] == sc[o] else 0
    return w, pf


def _join(names):
    names = list(names)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " & " + names[-1]


def news(SCH, SD, W, teams):
    """The week's playoff news: list of (team, kind) with kind in clinched / bye / eliminated / field-in / field-out,
    plus records. Empty when nothing changed this week."""
    REG, POT = SCH["regweeks"], SCH["playoff_teams"]
    BYES = byes_for(POT)
    teams = sorted(teams)
    if W < 1 or W > REG or POT >= len(teams):
        return [], {}
    w0, pf0 = _wins(SD, range(1, W + 1), teams)
    left = [(g["wk"], g["home"], g["away"]) for g in SCH["games"] if W < g["wk"] <= REG and g.get("away")]
    st = status(w0, left, POT, BYES)
    wp, _ = _wins(SD, range(1, W), teams)
    lp = [(g["wk"], g["home"], g["away"]) for g in SCH["games"] if W - 1 < g["wk"] <= REG and g.get("away")]
    prev = status(wp, lp, POT, BYES) if W > 1 else {t: dict(clinched=False, bye=False, eliminated=False) for t in teams}
    order = sorted(teams, key=lambda t: (-w0[t], -pf0[t]))
    rec = {t: f"{w0[t]:g}\u2013{W - w0[t]:g}" for t in teams}
    out = []
    for t in order:
        if st[t]["bye"] and not prev[t]["bye"]:
            out.append((t, "bye"))
        elif st[t]["clinched"] and not prev[t]["clinched"]:
            out.append((t, "clinched"))
    for t in order:
        if st[t]["eliminated"] and not prev[t]["eliminated"]:
            out.append((t, "eliminated"))
    return out, dict(rec=rec, order=order, pot=POT, byes=BYES, left=REG - W, status=st)


STAMP = {"clinched": "Clinched", "bye": "Clinched a bye", "eliminated": "Eliminated"}


def section(SCH, SD, W, teams, SHORT, lg, esc, copy=None, fill=lambda s: s):
    """Returns (html, items, missing): the Breaking News box ("" when there is no news), the items for the printed
    paper [(team, kind, headline, text)] and the team ids that had no hand-written copy."""
    items, info = news(SCH, SD, W, teams)
    copy = copy or {}
    # catch-up: a team the copy names that clinched or was eliminated in an EARLIER week is shown too (used once,
    # week 11, when the box started; user 2026-11-24: "include every team that's eliminated", then only new changes)
    st = info.get("status", {})
    for k in copy:
        t = int(k) if str(k).isdigit() else None
        if t in st and t not in [x for x, _ in items]:
            kind = "bye" if st[t]["bye"] else "clinched" if st[t]["clinched"] else "eliminated" if st[t]["eliminated"] else None
            if kind:
                items.append((t, kind))
    if not items:
        return "", [], []
    rec, left, pot = info["rec"], info["left"], info["pot"]
    rows, plain, missing = [], [], []
    for t, kind in items:
        c = copy.get(str(t)) or {}
        if c.get("headline") and c.get("text"):
            h, x = c["headline"], c["text"]
        else:
            missing.append(t)
            if kind == "eliminated":
                h = f"{SHORT[t]} eliminated"
                x = f"At {rec[t]} with {left} week{'s' if left != 1 else ''} left, {{S{t}}} can no longer reach the top {pot}."
            else:
                h = f"{SHORT[t]} {'locks up a bye' if kind == 'bye' else 'clinches a playoff spot'}"
                x = f"{{S{t}}} ({rec[t]}) is in" + (" and skips round one." if kind == "bye" else f", with {left} week{'s' if left != 1 else ''} to spare.")
        plain.append((t, kind, h, re.sub(r"\{[TS](\d+)\}", lambda m: SHORT[int(m.group(1))], x)))
        rows.append(f'<article class="bn-i bn-{kind}">{lg(t, "lg-md")}<div><span class="bn-st">{esc(STAMP[kind])}</span>'
                    f'<h3>{esc(h)}</h3><p>{fill(esc(x))}</p></div></article>')
    css = """<style>
.bn{border:3px solid var(--rule);background:var(--sheet)}
.bn-bar{display:flex;align-items:center;gap:10px;background:var(--red);color:#fff;padding:6px 12px;font-family:var(--display);font-weight:900;font-size:1.3rem;letter-spacing:.06em;text-transform:uppercase}
.bn-bar::before{content:"";width:10px;height:10px;border-radius:50%;background:#fff;animation:bn-blink 1.2s steps(2,start) infinite}
@keyframes bn-blink{to{visibility:hidden}}
@media (prefers-reduced-motion:reduce){.bn-bar::before{animation:none}}
.bn-bar small{margin-left:auto;font-family:var(--mono);font-size:.66rem;font-weight:400;letter-spacing:.1em}
.bn-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr))}
.bn-i{display:grid;grid-template-columns:auto minmax(0,1fr);gap:12px;align-items:start;padding:12px 14px;border-top:1px solid var(--line)}
.bn-i h3{font-size:1.45rem;text-transform:uppercase;margin:4px 0 4px}
.bn-i p{font-size:.95rem}
.bn-st{font-family:var(--mono);font-size:.66rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;padding:2px 6px;border:1.5px solid currentColor}
.bn-clinched .bn-st,.bn-bye .bn-st{color:var(--blue)}
.bn-eliminated .bn-st{color:var(--red)}
@media (max-width:760px){.bn-bar{font-size:1.1rem}.bn-bar small{display:none}.bn-i{padding:10px 12px}.bn-i h3{font-size:1.25rem}}
</style>"""
    html_ = (f'<section class="bn" id="breaking" aria-label="Breaking news">{css}<div class="bn-bar">Breaking news'
             f'<small>Playoff race · week {W}</small></div><div class="bn-list">{"".join(rows)}</div></section>')
    return html_, plain, missing


LAUNCH = (2026, 11)  # season, week the box started: that edition also lists teams decided earlier (user, 2026-11-24)


def from_files(W, home="."):
    """For papers written without hand copy (multi/autocopy.py): this week's news and every team's status, read from
    data/week1..W_raw.txt and data/schedule.json in `home`. Returns (items, info, decided_week) or None.
    decided_week: team -> the week its current clinched/eliminated status was settled."""
    import os, json as _j
    from facts import load as _load
    p = lambda *a: os.path.join(home, *a)
    if not os.path.exists(p("data", "schedule.json")) or not all(os.path.exists(p("data", f"week{k}_raw.txt")) for k in range(1, W + 1)):
        return None
    SCH = _j.load(open(p("data", "schedule.json")))
    SD, teams = {}, set()
    for k in range(1, W + 1):
        _m, _s, _t, sched, _r, _x, _l = _load(p("data", f"week{k}_raw.txt"))
        sc, opp = {}, {}
        for gm in sched:
            if gm["wk"] == k and gm["away"]:
                sc[gm["home"]], sc[gm["away"]] = gm["hp"], gm["ap"]; opp[gm["home"]], opp[gm["away"]] = gm["away"], gm["home"]
        SD[k] = dict(score=sc, opp=opp); teams |= set(sc)
    items, info = news(SCH, SD, W, teams)
    if not info:
        return None
    decided = {}
    for t, s in info["status"].items():
        key = "bye" if s["bye"] else "clinched" if s["clinched"] else "eliminated" if s["eliminated"] else None
        if not key:
            continue
        k = W
        while k > 1:
            _, pinfo = news(SCH, {j: SD[j] for j in range(1, k)}, k - 1, teams)
            if not pinfo or not pinfo["status"][t][key]:
                break
            k -= 1
        decided[t] = k
    return items, info, decided


if __name__ == "__main__":
    # quick check: python3 playoffs.py W  -> prints each team's status
    import json, sys, re
    W = int(sys.argv[1]); SCH = json.load(open("data/schedule.json"))
    w0 = {}
    for g in SCH["games"]:
        if g["wk"] <= W and g.get("away"):
            for t in (g["home"], g["away"]): w0.setdefault(t, 0)
            if g["winner"] == "HOME": w0[g["home"]] += 1
            elif g["winner"] == "AWAY": w0[g["away"]] += 1
    left = [(g["wk"], g["home"], g["away"]) for g in SCH["games"] if W < g["wk"] <= SCH["regweeks"] and g.get("away")]
    for t, s in sorted(status(w0, left, SCH["playoff_teams"], byes_for(SCH["playoff_teams"])).items(), key=lambda x: -w0[x[0]]):
        print(t, w0[t], {k: v for k, v in s.items() if v})
