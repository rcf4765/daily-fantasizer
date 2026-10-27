"""Player Stats sections added 2026-10-19 at the user's request (all automatic):

- Trend Lines (#ps-trend): pick any player for his PPR points every week of the fantasy season (weeks 1-17)
  against his projection. Past weeks: the blended projection made that week (FantasyPros consensus + ESPN).
  Coming weeks with posted projections: the same blend. Later weeks: his rest-of-season points per game
  (Roster Radar value), zero on his bye (nflverse schedule). Targets and snap share under the chart.
- Defense Matchups (#ps-defense): PPR points each NFL defense has allowed per game to QBs, RBs, WRs and TEs
  (every fantasy-relevant player the fetch tracks, weeks 1..N), shaded against the league average, with
  who it faces next week.
(Waiver Targets was added and then removed at the user's request, 2026-10-19.)

Built inside the Player Stats pane (players.build), so the midweek refresh keeps them current.
"""
import html, json, os
from collections import defaultdict

esc = lambda s: html.escape(str(s))
SEASON_WEEKS = 17          # fantasy season: 14 regular-season weeks + 3 playoff weeks
POS = ["QB", "RB", "WR", "TE"]


def lg(t, size="lg-sm"): return f'<i class="lg lg-{t} {size}" aria-hidden="true"></i>'


def sec(id_, title, kicker, body):
    return f'<section class="sec" id="{id_}"><div class="sec-head"><h2>{title}</h2><span class="kicker">{kicker}</span></div>{body}</section>'


def _sched():
    f = "data/players/nfl_schedule.json"
    return json.load(open(f)) if os.path.exists(f) else None


# ------------------------------------------------------------------ trend lines
def trend(d, W, short, own_team):
    import strength as S
    S.ros_values(d)
    rawp = S.raw_proj(W)
    sch = _sched()
    byes = (sch or {}).get("byes", {})
    nxt = W + 1
    keep = []
    for p in d.P:
        rr = p.get("ros_rank")
        if p.get("owner") or (rr and rr <= {"QB": 32, "RB": 60, "WR": 72, "TE": 32}[p["pos"]]) or (p["g"] >= 2 and p["ppg"] >= 6):
            keep.append(p)
    rows = []
    for p in keep:
        g = set(d.games(p))
        u = d.use.get(p["key"], {})
        act, pj, tg, sn, flag = [], [], [], [], []
        for w in range(1, SEASON_WEEKS + 1):
            bye = w in byes.get(p["team"], [])
            a = round(p["act"][w]["pts"], 1) if (w <= W and w in g) else None
            v = S.proj_for(d, p, w, rawp)
            if v is None and w > nxt:
                v = 0.0 if bye else p["ros"]
                flag.append(2)                      # rest-of-season estimate
            else:
                flag.append(1 if v is not None else 0)
            if bye and w > W:
                v = 0.0
            act.append(a)
            pj.append(None if v is None else round(v, 1))
            tg.append(int(p["act"][w]["tgt"]) if (w <= W and w in g and p["act"][w].get("tgt") is not None) else None)
            s_ = u.get(w, {}).get("snap") if w <= W else None
            sn.append(None if s_ is None else round(s_ * 100))
        b = [w for w in byes.get(p["team"], []) if w <= SEASON_WEEKS]
        rows.append([p["name"], p["pos"], p["team"], p.get("owner") or 0, act, pj, tg, sn, flag, b[0] if b else 0,
                     round(p["ppg"], 1), round(p["ros"], 1)])
    rows.sort(key=lambda r: (r[3] == 0, r[3], -r[11]))
    default = next((r[0] for r in rows if r[3] == own_team), rows[0][0] if rows else "")
    data = {"W": W, "N": SEASON_WEEKS, "teams": {str(k): v for k, v in short.items()}, "p": rows, "def": default}
    body = (f'<div class="tl"><div class="tl-pick"><label><span class="kicker">Player</span><select id="tl-sel"></select></label>'
            f'<span class="tl-meta" id="tl-meta"></span></div>'
            f'<div class="tl-tiles" id="tl-tiles"></div>'
            f'<div class="tl-chart" id="tl-chart" role="img" aria-label="Weekly PPR points against projection"></div>'
            f'<div class="tl-key"><span><i class="k-act"></i>Actual</span><span><i class="k-pj"></i>Projected that week</span><span><i class="k-ros"></i>Rest-of-season estimate</span><span><i class="k-bye"></i>Bye</span></div>'
            f'<div class="tl-grid" id="tl-grid"></div></div>'
            f'<script type="application/json" id="tl-data">{json.dumps(data, separators=(",", ":")).replace("</", "<\\/")}</script>'
            f'<p class="note-s">Past weeks show the projection made before that week (consensus and ESPN, blended). Upcoming weeks use posted projections; '
            f'after that, his rest-of-season points per game from the consensus rankings, and zero on his bye. Weeks 15–17 are the fantasy playoffs.</p>')
    return sec("ps-trend", "Trend Lines", f"Actual vs. projected · weeks 1–{SEASON_WEEKS}", body)


# ------------------------------------------------------------------ defense matchups
def defense(d, W):
    sch = _sched()
    if not sch:
        return ""
    T = sch["teams"]
    allow = defaultdict(lambda: defaultdict(float)); games = defaultdict(set)
    for p in d.P:
        for w in d.games(p):
            if w > W:
                continue
            o = (T.get(p["team"], {}).get(str(w)) or {}).get("opp")
            if not o:
                continue
            allow[o][p["pos"]] += p["act"][w]["pts"]; games[o].add(w)
    if not allow:
        return ""
    dv = {o: [allow[o][ps] / len(games[o]) for ps in POS] for o in allow if games[o]}
    avg = [sum(v[i] for v in dv.values()) / len(dv) for i in range(4)]
    rank = {}
    for i in range(4):
        for r, o in enumerate(sorted(dv, key=lambda o: -dv[o][i]), 1):
            rank[(o, i)] = r
    order = sorted(dv, key=lambda o: -sum(dv[o][i] / avg[i] for i in range(4)))
    nxt = str(W + 1)

    def cls(r):
        return "d3" if r >= 1.3 else "d2" if r >= 1.15 else "d1" if r >= 1.05 else "s3" if r <= 0.7 else "s2" if r <= 0.85 else "s1" if r <= 0.95 else "d0"
    head = '<span class="dv-h"></span>' + "".join(f'<span class="dv-h">vs {p}</span>' for p in POS) + f'<span class="dv-h dv-o">Week {nxt} faces</span>'
    cells = ""
    for o in order:
        g = T.get(o, {}).get(nxt)
        faces = (("vs. " if g["home"] else "at ") + g["opp"]) if g else "bye"
        cells += f'<span class="dv-t">{esc(o)}</span>' + "".join(
            f'<span class="dv-c {cls(dv[o][i] / avg[i])}" title="{esc(o)} allows {dv[o][i]:.1f} PPR per game to {POS[i]}s (rank {rank[(o, i)]} of {len(dv)}; league average {avg[i]:.1f})">'
            f'<b class="num">{dv[o][i]:.1f}</b><small class="num">#{rank[(o, i)]}</small></span>' for i in range(4)) + f'<span class="dv-o">{esc(faces)}</span>'
    key = "".join(f'<span class="dv-c {c}">{t}</span>' for c, t in [("s3", "−30%"), ("s2", "−15%"), ("d0", "avg"), ("d2", "+15%"), ("d3", "+30%")])
    body = (f'<div class="dv-key"><span class="kicker">vs. league average</span>{key}</div>'
            f'<div class="dv-wrap"><div class="dv">{head}{cells}</div></div>'
            f'<p class="note-s">PPR points per game each defense has allowed to every QB, RB, WR and TE it faced, weeks 1–{W}. '
            f'#1 = most generous. Sorted softest to toughest overall. Blue: start your guys against them. Red: think twice. '
            f'League averages: QB {avg[0]:.1f}, RB {avg[1]:.1f}, WR {avg[2]:.1f}, TE {avg[3]:.1f}.</p>')
    return sec("ps-defense", "Defense Matchups", f"Points allowed by position · weeks 1–{W} · week {nxt} opponents", body)


def sections(d, W, short_names):
    short = {int(k): v for k, v in short_names.items()}
    LG = json.load(open("league.json")) if os.path.exists("league.json") else {}
    own_team = int(LG.get("owner_team") or 1)
    out = {}
    try:
        out["trend"] = trend(d, W, short, own_team)
    except Exception as e:
        print("trend lines skipped:", e); out["trend"] = ""
    try:
        out["defense"] = defense(d, W)
    except Exception as e:
        print("defense matchups skipped:", e); out["defense"] = ""
    return out


SCRIPT = r"""<script>
(function(){
  var el=document.getElementById('tl-data'); if(!el)return;
  var D=JSON.parse(el.textContent),P=D.p,T=D.teams,by={};P.forEach(function(r){by[r[0]]=r});
  var sel=document.getElementById('tl-sel'),ch=document.getElementById('tl-chart'),gr=document.getElementById('tl-grid'),meta=document.getElementById('tl-meta'),tiles=document.getElementById('tl-tiles');
  var groups={};P.forEach(function(r){var g=r[3]?T[r[3]]:'Free agents';(groups[g]=groups[g]||[]).push(r)});
  Object.keys(groups).forEach(function(g){var og=document.createElement('optgroup');og.label=g;
    groups[g].forEach(function(r){var o=document.createElement('option');o.value=r[0];o.textContent=r[0]+' ('+r[1]+', '+r[2]+')';og.appendChild(o)});sel.appendChild(og)});
  sel.value=D.def;
  function e(s){return String(s).replace(/[&<>"]/g,function(m){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]})}
  function f1(v){return v==null?'–':v.toFixed(1)}
  function draw(){
    var r=by[sel.value];if(!r)return;var A=r[4],J=r[5],G=r[6],S=r[7],F=r[8],bye=r[9],W=D.W,N=D.N;
    var cw=ch.clientWidth?Math.max(300,ch.clientWidth-8):720,vw=Math.min(cw,1100),vh=vw<520?220:250,l=28,rt=8,t=12,b=24,iw=vw-l-rt,ih=vh-t-b;
    var mx=5;A.concat(J).forEach(function(v){if(v!=null&&v>mx)mx=v});mx=Math.ceil(mx/5)*5;
    var X=function(w){return l+(w-0.5)/N*iw},Y=function(v){return t+ih-Math.max(0,v)/mx*ih};
    var s='<svg viewBox="0 0 '+vw+' '+vh+'" class="tl-svg">';
    for(var g=0;g<=mx;g+=(mx>40?10:5)){s+='<line class="tl-gl" x1="'+l+'" x2="'+(vw-rt)+'" y1="'+Y(g)+'" y2="'+Y(g)+'"/><text class="tl-ax" x="'+(l-6)+'" y="'+(Y(g)+4)+'" text-anchor="end">'+g+'</text>'}
    s+='<rect class="tl-po" x="'+(X(15)-iw/N/2)+'" y="'+t+'" width="'+(iw/N*3)+'" height="'+ih+'"/><text class="tl-ax" x="'+X(16)+'" y="'+(t+11)+'" text-anchor="middle">Playoffs</text>';
    s+='<line class="tl-now" x1="'+(X(W)+iw/N/2)+'" x2="'+(X(W)+iw/N/2)+'" y1="'+t+'" y2="'+(t+ih)+'"/>';
    if(bye)s+='<text class="tl-bye" x="'+X(bye)+'" y="'+(t+ih-6)+'" text-anchor="middle">BYE</text>';
    for(var w=1;w<=N;w++)s+='<text class="tl-ax" x="'+X(w)+'" y="'+(vh-8)+'" text-anchor="middle">'+w+'</text>';
    function path(vals,keep){var d='',on=false;for(var i=0;i<N;i++){var v=vals[i];if(v==null||!keep(i)){on=false;continue}d+=(on?'L':'M')+X(i+1).toFixed(1)+' '+Y(v).toFixed(1)+' ';on=true}return d}
    s+='<path class="tl-pj" d="'+path(J,function(i){return F[i]===1})+'"/>';
    var lastPj=-1;for(var i=0;i<N;i++)if(F[i]===1)lastPj=i;
    s+='<path class="tl-ros" d="'+path(J,function(i){return F[i]===2||i===lastPj})+'"/>';
    s+='<path class="tl-act" d="'+path(A,function(){return true})+'"/>';
    for(var i=0;i<N;i++){if(J[i]!=null&&F[i])s+='<circle class="'+(F[i]===2?'tl-dr':'tl-dp')+'" cx="'+X(i+1)+'" cy="'+Y(J[i])+'" r="3"><title>Week '+(i+1)+(F[i]===2?' estimate ':' projection ')+f1(J[i])+'</title></circle>';
      if(A[i]!=null)s+='<circle class="tl-da" cx="'+X(i+1)+'" cy="'+Y(A[i])+'" r="4.5"><title>Week '+(i+1)+': '+f1(A[i])+' PPR'+(J[i]!=null?' (projected '+f1(J[i])+')':'')+'</title></circle>'}
    s+='</svg>';ch.innerHTML=s;
    var pa=0,pp=0,n=0,beat=0,rest=0;for(var i=0;i<N;i++){if(A[i]!=null){pa+=A[i];n++;if(J[i]!=null){pp+=J[i];if(A[i]>=J[i])beat++}}else if(i>=W&&J[i]!=null)rest+=J[i]}
    meta.innerHTML=e(r[1])+' · '+e(r[2])+' · '+(r[3]?e(T[r[3]]):'Free agent')+(bye?' · bye week '+bye:'');
    tiles.innerHTML='<span><b class="num">'+pa.toFixed(1)+'</b>Actual, weeks 1–'+W+'</span><span><b class="num">'+pp.toFixed(1)+'</b>Projected for those games</span><span><b class="num">'+beat+' of '+n+'</b>Weeks he beat it</span><span><b class="num">'+rest.toFixed(0)+'</b>Projected, weeks '+(W+1)+'–'+N+'</span>';
    var h='<span class="tl-l"></span>';for(var w=1;w<=W;w++)h+='<span class="tl-h">Wk '+w+'</span>';
    h+='<span class="tl-l">PPR</span>';for(var i=0;i<W;i++)h+='<span>'+(A[i]==null?(i+1===bye?'bye':'–'):A[i].toFixed(1))+'</span>';
    h+='<span class="tl-l">Proj</span>';for(var i=0;i<W;i++)h+='<span>'+f1(J[i])+'</span>';
    h+='<span class="tl-l">Targets</span>';for(var i=0;i<W;i++)h+='<span>'+(G[i]==null?'–':G[i])+'</span>';
    h+='<span class="tl-l">Snap %</span>';for(var i=0;i<W;i++)h+='<span>'+(S[i]==null?'–':S[i]+'%')+'</span>';
    gr.style.gridTemplateColumns='64px repeat('+W+',minmax(0,1fr))';gr.innerHTML=h;
  }
  sel.addEventListener('change',draw);draw();
  var rw=ch.clientWidth;function re(){var w=ch.clientWidth;if(w&&Math.abs(w-rw)>40){rw=w;draw()}}
  if(window.ResizeObserver)new ResizeObserver(re).observe(ch);else addEventListener('resize',re);
})();
</script>"""

CSS = r"""
/* Trend Lines */
.tl{display:grid;gap:12px}
.tl-pick{display:flex;flex-wrap:wrap;align-items:end;gap:10px 18px}
.tl-pick label{display:grid;gap:4px}
.tl-pick select{font:inherit;font-size:.95rem;padding:7px 10px;border:2px solid var(--rule);background:var(--sheet);color:var(--ink);min-width:min(100%,320px)}
.tl-meta{font-family:var(--mono);font-size:.75rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.tl-tiles{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:2px;background:var(--rule);border:2px solid var(--rule)}
.tl-tiles span{background:var(--sheet);padding:10px 12px;display:grid;gap:2px;font-family:var(--mono);font-size:.66rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.tl-tiles b{font-size:1.5rem;color:var(--ink);letter-spacing:0}
.tl-chart{border:2px solid var(--rule);background:var(--sheet);padding:6px 4px 0}
.tl-svg{display:block;width:100%;height:auto}
.tl-gl{stroke:var(--line);stroke-width:1}
.tl-ax{font-family:var(--mono);font-size:11px;fill:var(--muted)}
.tl-po{fill:var(--dot)}
.tl-now{stroke:var(--ink);stroke-width:1;stroke-dasharray:2 3}
.tl-bye{font-family:var(--mono);font-size:10px;font-weight:600;fill:var(--red)}
.tl-act{fill:none;stroke:var(--blue);stroke-width:2.5;stroke-linejoin:round}
.tl-pj{fill:none;stroke:var(--ink);stroke-width:1.5;stroke-dasharray:5 4}
.tl-ros{fill:none;stroke:var(--silver);stroke-width:1.5;stroke-dasharray:2 4}
.tl-da{fill:var(--blue);stroke:var(--sheet);stroke-width:1.5}
.tl-dp{fill:var(--sheet);stroke:var(--ink);stroke-width:1.5}
.tl-dr{fill:var(--sheet);stroke:var(--silver);stroke-width:1.5}
.tl-key{display:flex;flex-wrap:wrap;gap:6px 16px;font-family:var(--mono);font-size:.66rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.tl-key i{display:inline-block;width:18px;vertical-align:middle;margin-right:5px}
.tl-key .k-act{border-top:2.5px solid var(--blue)}.tl-key .k-pj{border-top:1.5px dashed var(--ink)}.tl-key .k-ros{border-top:1.5px dotted var(--silver)}
.tl-key .k-bye{width:auto}.tl-key .k-bye::before{content:"BYE";color:var(--red);font-style:normal;font-weight:600}
.tl-grid{display:grid;gap:2px;font-family:var(--mono);font-size:.74rem;text-align:center}
.tl-grid span{padding:4px 2px;background:var(--paper)}
.tl-grid .tl-l,.tl-grid .tl-h{background:none;color:var(--muted);font-size:.64rem;letter-spacing:.06em;text-transform:uppercase}
.tl-grid .tl-l{text-align:left}
/* Defense Matchups */
.dv-key{display:flex;flex-wrap:wrap;align-items:center;gap:4px}
.dv-key .kicker{margin-right:6px}
.dv-key .dv-c{padding:3px 8px;font-family:var(--mono);font-size:.66rem}
.dv-wrap{overflow-x:auto}
.dv{display:grid;grid-template-columns:52px repeat(4,minmax(54px,1fr)) minmax(84px,1fr);gap:2px;min-width:420px}
.dv-h{font-family:var(--mono);font-size:.64rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);padding:2px 0;text-align:center}
.dv-t{font-family:var(--display);font-weight:800;font-size:1rem;display:flex;align-items:center}
.dv-c{display:flex;align-items:baseline;justify-content:center;gap:5px;padding:5px 2px;background:var(--heat0);color:var(--ink)}
.dv-c b{font-size:.86rem}.dv-c small{font-size:.6rem;opacity:.75}
.dv-c.d1{background:color-mix(in srgb,var(--blue) 18%,var(--sheet))}
.dv-c.d2{background:color-mix(in srgb,var(--blue) 42%,var(--sheet))}
.dv-c.d3{background:var(--blue);color:var(--blue-ink)}
.dv-c.s1{background:color-mix(in srgb,var(--red) 16%,var(--sheet))}
.dv-c.s2{background:color-mix(in srgb,var(--red) 38%,var(--sheet))}
.dv-c.s3{background:var(--red);color:#fff}
.dv-o{font-family:var(--mono);font-size:.7rem;color:var(--muted);display:flex;align-items:center;padding-left:8px}
.dv-h.dv-o{justify-content:flex-start}
@media (max-width:760px){
  .tl-tiles{grid-template-columns:1fr 1fr}.tl-tiles b{font-size:1.2rem}
  .tl-grid{font-size:.62rem}.tl-grid .tl-l,.tl-grid .tl-h{font-size:.52rem}
  .dv{grid-template-columns:40px repeat(4,minmax(0,1fr)) 62px;min-width:0}.dv-c{flex-direction:column;align-items:center;gap:0;padding:4px 1px}.dv-c b{font-size:.74rem}.dv-o{font-size:.58rem;padding-left:4px}.dv-t{font-size:.85rem}
}
"""


# ====================================================================== added 2026-10-19 (second batch)
# Player Face-Off, Steady or Streaky. (Margin Map was turned down; Risers & Fallers was added and then removed, 2026-10-19.)
import statistics as _st


def _relevant(p):
    rr = p.get("ros_rank")
    return bool(p.get("owner")) or (rr and rr <= {"QB": 32, "RB": 60, "WR": 72, "TE": 32}[p["pos"]]) or p["ppg"] >= 6


def _allowed(d, W):
    """Defense -> PPR per game allowed to each position (QB, RB, WR, TE), weeks 1..W, and the league averages."""
    sch = _sched()
    if not sch:
        return {}, [0, 0, 0, 0]
    T = sch["teams"]
    allow = defaultdict(lambda: defaultdict(float)); games = defaultdict(set)
    for p in d.P:
        for w in d.games(p):
            if w > W:
                continue
            o = (T.get(p["team"], {}).get(str(w)) or {}).get("opp")
            if o:
                allow[o][p["pos"]] += p["act"][w]["pts"]; games[o].add(w)
    dv = {o: [allow[o][ps] / len(games[o]) for ps in POS] for o in allow if games[o]}
    avg = [sum(v[i] for v in dv.values()) / len(dv) for i in range(4)] if dv else [0, 0, 0, 0]
    return dv, avg


PLAYOFFS = (15, 16, 17)


def faceoff(d, W, short, own_team):
    """Player Face-Off (user, 2026-10-27): type any two players; short term, long term and usage side by side,
    with a verdict for each horizon and a roster call (who to grab off waivers, who to drop)."""
    import strength as S
    import lookup as L
    S.ros_values(d)
    rawp = S.raw_proj(W)
    sch = _sched() or {}; byes = sch.get("byes", {}); T = sch.get("teams", {})
    dv, avg = _allowed(d, W)
    soft = {}  # (defense, pos index) -> rank, 1 = gives up the most
    for i in range(4):
        for r, o in enumerate(sorted(dv, key=lambda o: -dv[o][i]), 1):
            soft[(o, i)] = r
    ndef = len(dv)
    adv = L.adv_totals(d, W)
    nxt = W + 1
    r1 = lambda x, n=1: None if x is None else round(x, n)
    rows = []
    for p in d.P:
        if p["g"] < 1 or not _relevant(p):
            continue
        pi = POS.index(p["pos"])
        out = p.get("inj") in ("OUT", "INJURY_RESERVE")
        pj = []
        for w in (nxt, nxt + 1):
            v = S.proj_for(d, p, w, rawp)
            if w in byes.get(p["team"], []) or (out and w == nxt):
                v = 0.0
            pj.append(r1(v))
        g = [w for w in d.games(p) if w <= W]
        pts = [p["act"][w]["pts"] for w in g]
        # next opponent: points his position scores against them vs. league average
        o = (T.get(p["team"], {}).get(str(nxt)) or {})
        mu = None
        if o.get("opp") and o["opp"] in dv and avg[pi]:
            mu = [("" if o.get("home") else "@") + o["opp"], round(dv[o["opp"]][pi] / avg[pi] * 100), soft[(o["opp"], pi)]]
        # fantasy playoffs (weeks 15-17): average softness of the three opponents, byes flagged
        po, pv = [], []
        for w in PLAYOFFS:
            x = (T.get(p["team"], {}).get(str(w)) or {})
            if x.get("opp"):
                po.append(("" if x.get("home") else "@") + x["opp"])
                if x["opp"] in dv and avg[pi]:
                    pv.append(dv[x["opp"]][pi] / avg[pi])
            else:
                po.append("BYE")
        bye = [w for w in byes.get(p["team"], []) if w > W]
        t = adv.get(p["key"], {})
        rz = (t.get("rzt") or 0) + (t.get("rzc") or 0)
        sd = (sum((x - sum(pts) / len(pts)) ** 2 for x in pts) / len(pts)) ** .5 if pts else None
        u = d.use.get(p["key"], {})
        wopr = [u[w].get("wopr") for w in g if w in u and u[w].get("wopr") is not None]
        ros = d.ros_by.get(p["key"]) or {}
        rr = ros.get("pos_rank") or ""
        rows.append({
            "n": p["name"], "k": p["key"], "pos": p["pos"], "tm": p["team"], "o": p.get("owner") or 0, "inj": p.get("inj", "ACTIVE"),
            "rp": r1(p.get("own_pct"), 0), "g": len(g),
            # short term
            "p1": pj[0], "p2": pj[1], "l3": r1(p["l3"]), "mu": mu,
            "ts3": None if p["ts_l3"] is None else r1(p["ts_l3"] * 100), "sn3": None if p["snap_l3"] is None else r1(p["snap_l3"] * 100, 0),
            # long term
            "ros": r1(p.get("ros")), "rr": int("".join(c for c in str(rr) if c.isdigit()) or 0), "ppg": r1(p["ppg"]),
            "xp": r1(p.get("xp")), "po": po, "pv": round(sum(pv) / len(pv) * 100) if pv else None, "bye": bye[0] if bye else 0,
            "hi": r1(max(pts)) if pts else 0, "lo": r1(min(pts)) if pts else 0, "sd": r1(sd),
            # usage (season)
            "ts": None if p["ts"] is None else r1(p["ts"] * 100), "sn": None if p["snap"] is None else r1(p["snap"] * 100, 0),
            "ays": None if p["ays"] is None else r1(p["ays"] * 100), "wopr": r1(sum(wopr) / len(wopr), 2) if wopr else None,
            "tg": r1(p["tgt_g"]), "tch": r1(p["tch_g"]), "rz": r1(rz / len(g)) if g else None,
        })
    if len(rows) < 2:
        return ""
    rows.sort(key=lambda r: (r["o"] == 0, r["o"], POS.index(r["pos"]), -(r["ros"] or 0)))
    # default: the owner team's weakest RB/WR/TE (drop candidate) against the best free agent at his position by rest of season
    mine = [r for r in rows if r["o"] == own_team and r["pos"] in ("RB", "WR", "TE") and r["inj"] not in ("INJURY_RESERVE",)]
    pair = None
    if mine:
        weak = min(mine, key=lambda r: r["ros"] or 0)
        fa = [r for r in rows if not r["o"] and r["pos"] == weak["pos"]]
        if fa:
            pair = [max(fa, key=lambda r: r["ros"] or 0)["k"], weak["k"]]
    data = {"teams": {str(k): v for k, v in short.items()}, "p": rows, "nxt": nxt, "nd": ndef,
            "def": pair or [rows[0]["k"], rows[1]["k"]]}
    body = (f'<div class="fo"><div class="fo-pick"><label><span class="kicker">Player A</span><select id="fo-a"></select></label><span class="fo-vs">vs.</span>'
            f'<label><span class="kicker">Player B</span><select id="fo-b"></select></label></div>'
            f'<div class="fo-head" id="fo-head"></div><div class="fo-call" id="fo-call" aria-live="polite"></div><div class="fo-rows" id="fo-rows"></div></div>'
            f'<script type="application/json" id="fo-data">{json.dumps(data, separators=(",", ":")).replace("</", "<\\/")}</script>'
            f'<details class="fo-how"><summary>How this works</summary><p class="note-s">Type any part of a name, a team name, or “FA” for free agents. Players who matter are listed: rostered, ranked or scoring 6+ PPR per game. '
            f'<b>Short term</b> = weeks {nxt}–{nxt + 1}: blended projections (zero on a bye or ruled out) and how many points his position scores against his week {nxt} opponent '
            f'(100 = league average). <b>Long term</b>: rest of season = his consensus ranking turned into points per game; expected = what his targets, carries and air yards '
            f'usually score (above it = running hot, below = due); playoffs = his weeks {PLAYOFFS[0]}–{PLAYOFFS[-1]} opponents vs. his position. '
            f'<b>Usage</b> is season-long, with the last-3-games trend. Rostered % is ESPN-wide.</p></details>')
    return sec("ps-faceoff", "Player Face-Off", "Type two players · waiver or drop, now and later", body)


def steady(d, W, short):
    rows = []
    for p in d.P:
        g = [w for w in d.games(p) if w <= W]
        if len(g) < 3 or p["ppg"] < 6:
            continue
        pts = [p["act"][w]["pts"] for w in g]
        o = p.get("owner") or 0
        rows.append({"n": p["name"], "pos": p["pos"], "tm": p["team"], "o": o, "on": short.get(o, "Free agent") if o else "Free agent",
                     "g": len(g), "ppg": round(_st.mean(pts), 1), "sd": round(_st.pstdev(pts), 1), "lo": round(min(pts), 1),
                     "md": round(_st.median(pts), 1), "hi": round(max(pts), 1), "l3": round(p["l3"], 1),
                     "wk": [round(x, 1) for x in pts], "inj": p.get("inj", "ACTIVE"), "k": p["key"]})
    if len(rows) < 5:
        return ""
    import math as _m
    xs = [r["ppg"] for r in rows]; ys = [r["sd"] for r in rows]
    xh = _m.ceil(max(xs) / 5) * 5; yh = _m.ceil(max(ys) / 5) * 5
    xl = 5
    X = lambda v: (v - xl) / (xh - xl) * 100; Y = lambda v: 100 - v / yh * 100
    sk = [r for r in rows if r["pos"] != "QB"]
    mx = _st.median([r["ppg"] for r in sk]); my = _st.median([r["sd"] for r in sk])
    top = sorted(sk, key=lambda r: -r["ppg"])[:40]
    lab = {r["k"] for r in sorted(top, key=lambda r: r["sd"])[:3] + sorted(top, key=lambda r: -r["sd"])[:3]}
    dots = "".join(f'<button type="button" class="vd p-{r["pos"]}{" lab" if r["k"] in lab else ""}{" fa" if not r["o"] else ""}{" off" if r["pos"] == "QB" else ""}" data-i="{i}" '
                   f'style="left:{X(r["ppg"]):.1f}%;top:{Y(r["sd"]):.1f}%" aria-label="{esc(r["n"])}, {r["ppg"]} PPR per game, swing {r["sd"]}">'
                   + f'<em>{esc(r["n"].split(" ")[-1] if r["n"].split(" ")[-1] not in ("Jr.", "Sr.", "II", "III") else r["n"].split(" ")[-2])}</em>'
                   + '</button>' for i, r in enumerate(rows))
    xt = "".join(f'<span style="left:{X(v):.0f}%">{v}</span>' for v in range(xl, xh + 1, 5))
    yt = "".join(f'<span style="top:{Y(v):.0f}%">{v}</span>' for v in range(0, yh + 1, 5))
    tms = sorted({r["o"] for r in rows if r["o"]}, key=lambda t: short.get(t, ""))
    opts = ('<option value="0">All teams</option>' + "".join(f'<option value="{t}">{esc(short[t])}</option>' for t in tms)
            + '<option value="-1">Free agents</option>')
    # own classes (st-pos), not .vs-f: the Volume vs. Scoring script listens to every .vs-f button,
    # which made these toggle twice and cancel out (fixed 2026-10-19)
    controls = ('<div class="vs-ctl st-ctl"><label class="st-team"><span class="kicker">Team</span>'
                f'<select id="st-team">{opts}</select></label>'
                '<div class="st-pos" role="group" aria-label="Positions">'
                + "".join(f'<button type="button" class="pt" data-f="{x}" aria-pressed="{"false" if x == "QB" else "true"}"><i class="sw p-{x}"></i>{x}</button>' for x in ("RB", "WR", "TE", "QB"))
                + '</div></div>')
    chart = (f'<div class="vs-wrap st-wrap"><span class="sc-y">Week-to-week swing</span><div class="vs st" id="st-plot">'
             f'<span class="st-mx" style="left:{X(mx):.1f}%"></span><span class="st-my" style="top:{Y(my):.1f}%"></span>'
             f'<span class="q st-q1">Boom or bust</span><span class="q st-q2">Steady studs</span><span class="q st-q3">Lottery tickets</span><span class="q st-q4">Steady, low ceiling</span>'
             f'{dots}<div class="vs-tip" id="st-tip" role="status" hidden></div><div class="st-y">{yt}</div></div>'
             f'<div class="vs-x">{xt}</div><span class="sc-x"><span>PPR points per game</span></span></div>'
             '<div class="legend"><span><i class="sw p-RB"></i>RB</span><span><i class="sw p-WR"></i>WR</span><span><i class="sw p-TE"></i>TE</span><span><i class="sw p-QB"></i>QB</span>'
             '<span><i class="st-sw"></i>median of RB/WR/TE</span></div>'
             f'<script type="application/json" id="st-data">{json.dumps(rows, separators=(",", ":")).replace("</", "<\\/")}</script>')
    body = (f'{controls}{chart}<p class="note-s">Each dot is a player with 3+ games and 6+ PPR per game, weeks 1–{W}. Across: points per game. Up: how much his weekly '
            f'score swings (standard deviation). Bottom right = high scoring and reliable; top right = big weeks and duds. Hover or tap a dot for the player; pick a team to spotlight its players; tap a position to show or hide it. '
            f'QBs score on a different scale, so they start hidden. With few games the swing is noisy and settles as the season goes on.</p>')
    return sec("ps-steady", "Steady or Streaky", f"Points per game vs. week-to-week swing · weeks 1–{W}", body)


def sections2(d, W, short_names, own_team):
    short = {int(k): v for k, v in short_names.items()}
    out = {}
    for k, f, a in (("faceoff", faceoff, (d, W, short, own_team)), ("steady", steady, (d, W, short))):
        try:
            out[k] = f(*a)
        except Exception as e:
            print(k, "skipped:", e); out[k] = ""
    return out


SCRIPT += r"""<script>
(function(){
  /* Type-to-search player boxes (user, 2026-10-27): turns a <select> into a search box. The select stays as the
     value holder, so the scripts that read it (Start / Sit, Face-Off) don't change. Matches any part of the name,
     the team's name, the NFL team or position; "FA" lists free agents. */
  function norm(s){return String(s||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/[.'’]/g,'')}
  function e(s){return String(s==null?'':s).replace(/[&<>"]/g,function(m){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]})}
  window.dfCombo=function(sel){
    if(!sel||sel.dataset.combo)return;sel.dataset.combo=1;
    var items=[].map.call(sel.options,function(o){var g=o.parentNode.tagName==='OPTGROUP'?o.parentNode.label:'';
      var m=o.textContent.match(/^(.*?) \((\w+), (\w+)\)(.*)$/)||[0,o.textContent,'','',''];
      return {v:o.value,n:m[1],pos:m[2],tm:m[3],x:m[4],g:g,s:norm(m[1]+' '+m[2]+' '+m[3]+' '+g+(g==='Free agents'?' fa':''))}});
    var box=document.createElement('div');box.className='cb';
    var inp=document.createElement('input');inp.type='search';inp.className='cb-in';inp.autocomplete='off';inp.spellcheck=false;
    inp.setAttribute('role','combobox');inp.setAttribute('aria-expanded','false');inp.setAttribute('aria-autocomplete','list');
    inp.placeholder='Type a player, team or “FA”';
    var lid=sel.id+'-list',ul=document.createElement('ul');ul.className='cb-list';ul.id=lid;ul.setAttribute('role','listbox');ul.hidden=true;inp.setAttribute('aria-controls',lid);
    var lab=sel.closest('label');if(lab){var k=lab.querySelector('.kicker');if(k)inp.setAttribute('aria-label',k.textContent)}
    sel.hidden=true;sel.tabIndex=-1;sel.after(box);box.appendChild(inp);box.appendChild(ul);
    var hits=[],cur=-1;
    function label(){var it=items.filter(function(i){return i.v===sel.value})[0];inp.value=it?it.n:''}
    function render(){var q=norm(inp.value).trim().split(/\s+/).filter(Boolean);
      hits=items.filter(function(i){return q.every(function(w){return i.s.indexOf(w)>=0})});
      // names that start with what was typed come first
      if(q.length){var f=q[0];hits.sort(function(a,b){var x=norm(a.n),y=norm(b.n);var sa=x.indexOf(f)===0||x.indexOf(' '+f)>=0?0:1,sb=y.indexOf(f)===0||y.indexOf(' '+f)>=0?0:1;return sa-sb})}
      hits=hits.slice(0,30);cur=hits.length?0:-1;
      ul.innerHTML=hits.length?hits.map(function(i,j){return '<li role="option" id="'+lid+'-'+j+'" data-j="'+j+'"'+(j===cur?' aria-selected="true"':'')+'><b>'+e(i.n)+'</b><small>'+e(i.pos)+' · '+e(i.tm)+e(i.x)+'</small><em>'+(i.g==='Free agents'?'FA':e(i.g))+'</em></li>'}).join(''):'<li class="cb-none">No player matches</li>';
      open(true)}
    function open(on){ul.hidden=!on;inp.setAttribute('aria-expanded',on?'true':'false');if(!on)inp.removeAttribute('aria-activedescendant')}
    function mark(){[].forEach.call(ul.children,function(li,j){if(j===cur){li.setAttribute('aria-selected','true');li.scrollIntoView({block:'nearest'});inp.setAttribute('aria-activedescendant',lid+'-'+j)}else li.removeAttribute('aria-selected')})}
    function choose(j){var it=hits[j];if(!it)return;sel.value=it.v;open(false);label();inp.blur();sel.dispatchEvent(new Event('change'))}
    inp.addEventListener('focus',function(){inp.select();render()});
    inp.addEventListener('input',render);
    inp.addEventListener('keydown',function(ev){
      if(ev.key==='ArrowDown'||ev.key==='ArrowUp'){ev.preventDefault();if(ul.hidden)render();if(!hits.length)return;cur=(cur+(ev.key==='ArrowDown'?1:-1)+hits.length)%hits.length;mark()}
      else if(ev.key==='Enter'){ev.preventDefault();choose(cur)}
      else if(ev.key==='Escape'){open(false);label();inp.blur()}});
    ul.addEventListener('pointerdown',function(ev){ev.preventDefault()});
    ul.addEventListener('click',function(ev){var li=ev.target.closest('li[data-j]');if(li)choose(+li.dataset.j)});
    inp.addEventListener('blur',function(){setTimeout(function(){open(false);label()},120)});
    sel.addEventListener('change',label);label();
  };
})();
(function(){
  /* Player Face-Off (user, 2026-10-27): short term, long term, usage; a verdict per horizon and a roster call */
  var el=document.getElementById('fo-data'); if(!el)return;
  var D=JSON.parse(el.textContent),P=D.p,T=D.teams,by={};P.forEach(function(r){by[r.k]=r});
  var A=document.getElementById('fo-a'),B=document.getElementById('fo-b'),H=document.getElementById('fo-head'),R=document.getElementById('fo-rows'),C=document.getElementById('fo-call');
  [A,B].forEach(function(sel){var groups={};P.forEach(function(r){var g=r.o?T[r.o]:'Free agents';(groups[g]=groups[g]||[]).push(r)});
    Object.keys(groups).forEach(function(g){var og=document.createElement('optgroup');og.label=g;
      groups[g].forEach(function(r){var o=document.createElement('option');o.value=r.k;o.textContent=r.n+' ('+r.pos+', '+r.tm+')';og.appendChild(o)});sel.appendChild(og)})});
  A.value=D.def[0];B.value=D.def[1];
  function e(s){return String(s==null?'':s).replace(/[&<>"]/g,function(m){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]})}
  function f1(v){return v==null?'–':(+v).toFixed(1)}
  function arrow(now,season){if(now==null||season==null)return '';var d=now-season;return d>=2?' <span class="fo-tr up" title="Last 3 games: '+now+'%">▲</span>':d<=-2?' <span class="fo-tr dn" title="Last 3 games: '+now+'%">▼</span>':''}
  // [label, value(r) for comparing, text(r), higher better (1) / lower (-1) / no winner (0), help]
  var nx=D.nxt;
  var G=[
   ['Short term · weeks '+nx+'–'+(nx+1),[
    ['Week '+nx+' projection',function(r){return r.p1},function(r){return r.p1===0?'no game':f1(r.p1)},1],
    ['Week '+(nx+1)+' projection',function(r){return r.p2},function(r){return r.p2===0?'no game':f1(r.p2)},1],
    ['Next 2 weeks',function(r){return r.p1==null&&r.p2==null?null:(r.p1||0)+(r.p2||0)},function(r){return r.p1==null&&r.p2==null?'–':f1((r.p1||0)+(r.p2||0))},1],
    ['Last 3 games, PPR/g',function(r){return r.l3},function(r){return f1(r.l3)},1],
    ['Week '+nx+' matchup',function(r){return r.mu?r.mu[1]:null},function(r){return r.mu?r.mu[1]+' <small>'+e(r.mu[0])+'</small>':(r.p1===0?'bye':'–')},1,'Points his position scores against this defense, 100 = league average'],
    ['Target share, last 3',function(r){return r.ts3},function(r){return r.ts3==null?'–':r.ts3.toFixed(1)+'%'},1],
    ['Snap share, last 3',function(r){return r.sn3},function(r){return r.sn3==null?'–':r.sn3+'%'},1]]],
   ['Long term · rest of season',[
    ['Rest of season, pts/g',function(r){return r.ros},function(r){return f1(r.ros)},1],
    ['ROS position rank',function(r){return r.rr||null},function(r){return r.rr?r.pos+r.rr:'unranked'},-1],
    ['PPR per game',function(r){return r.ppg},function(r){return f1(r.ppg)+' <small>'+r.g+' g</small>'},1],
    ['Expected PPR/g',function(r){return r.xp},function(r){if(r.xp==null)return '–';var d=r.ppg-r.xp;return f1(r.xp)+' <small class="'+(d>=0?'hot':'due')+'">'+(d>=1?'running hot':d<=-1?'due to bounce':'on pace')+'</small>'},1,'What his targets, carries and air yards usually score'],
    ['Playoff matchups',function(r){return r.pv},function(r){return (r.pv==null?'–':r.pv)+' <small>'+r.po.map(e).join(' ')+'</small>'},1,'Weeks 15–17 opponents vs. his position, 100 = average'],
    ['Bye still to come',function(r){return null},function(r){return r.bye?'week '+r.bye:'done'},0],
    ['Ceiling (best game)',function(r){return r.hi},function(r){return f1(r.hi)},1],
    ['Floor (worst game)',function(r){return r.lo},function(r){return f1(r.lo)},1],
    ['Week-to-week swing',function(r){return r.g>=3?r.sd:null},function(r){return r.g>=3?'±'+f1(r.sd):'–'},-1,'Lower = steadier']]],
   ['Usage · season',[
    ['Target share',function(r){return r.ts},function(r){return r.ts==null?'–':r.ts.toFixed(1)+'%'+arrow(r.ts3,r.ts)},1],
    ['Snap share',function(r){return r.sn},function(r){return r.sn==null?'–':r.sn+'%'+arrow(r.sn3,r.sn)},1],
    ['Air-yard share',function(r){return r.pos==='QB'?null:r.ays},function(r){return r.ays==null||r.pos==='QB'?'–':r.ays.toFixed(1)+'%'},1],
    ['WOPR',function(r){return r.wopr},function(r){return r.wopr==null?'–':r.wopr.toFixed(2)},1,'Weighted opportunity: 1.5 × target share + 0.7 × air-yard share'],
    ['Targets per game',function(r){return r.tg},function(r){return f1(r.tg)},1],
    ['Touches per game',function(r){return r.tch},function(r){return f1(r.tch)},1],
    ['Red-zone looks / g',function(r){return r.rz},function(r){return f1(r.rz)},1,'Red-zone targets + carries per game']]]];
  function side(r,c){var inj=(r.inj&&r.inj!=='ACTIVE'&&r.inj!=='NORMAL')?'<span class="inj">'+e(r.inj.replace('_',' ').toLowerCase())+'</span>':'';
    return '<div class="fo-card fo-c'+c+'"><div class="fo-crest">'+(r.o?'<i class="lg lg-'+r.o+' lg-md"></i>':'<span class="fo-fa">FA</span>')+'</div>'+
      '<div class="fo-id"><span class="fo-tag">'+e(r.pos)+' · '+e(r.tm)+'</span><b class="fo-nm">'+e(r.n)+'</b>'+inj+
      '<span class="fo-own">'+(r.o?e(T[r.o]):'Free agent')+'</span>'+
      (r.rp!=null?'<span class="fo-rp" title="Rostered in '+r.rp+'% of ESPN leagues"><i style="width:'+Math.min(100,r.rp)+'%"></i></span><small class="fo-rpt">'+r.rp+'% rostered on ESPN</small>':'')+'</div></div>'}
  function last(n){return n.split(' ').filter(function(w){return !/^(jr\.?|sr\.?|ii|iii|iv)$/i.test(w)}).pop()}
  function draw(){var a=by[A.value],b=by[B.value];if(!a||!b)return;var same=a.k===b.k;
    H.innerHTML=side(a,'a')+'<span class="fo-hv">vs</span>'+side(b,'b');
    var h='',score=[];
    G.forEach(function(g){var wa=0,wb=0,rows='';
      g[1].forEach(function(m){var va=m[1](a),vb=m[1](b),dir=m[3];
        var aw=!same&&dir&&va!=null&&vb!=null&&(dir>0?va>vb:va<vb),bw=!same&&dir&&va!=null&&vb!=null&&(dir>0?vb>va:vb<va);
        if(dir&&va!=null&&vb==null&&!same)aw=true;if(dir&&vb!=null&&va==null&&!same)bw=true;
        if(aw)wa++;if(bw)wb++;
        var la=0,lb=0;if(dir>0&&va!=null&&vb!=null){var mx=Math.max(va,vb,0.1);la=Math.max(0,va)/mx*100;lb=Math.max(0,vb)/mx*100}
        else if(dir<0&&va!=null&&vb!=null){var mn=Math.max(Math.min(va,vb),0.1);la=mn/Math.max(va,0.1)*100;lb=mn/Math.max(vb,0.1)*100}
        rows+='<div class="fo-r'+(dir?'':' fo-nb')+'"'+(m[4]?' title="'+e(m[4])+'"':'')+'><span class="fo-a'+(aw?' win':'')+'"><b class="num">'+m[2](a)+'</b>'+(dir?'<span class="fo-t"><i style="width:'+la.toFixed(1)+'%"></i></span>':'')+'</span>'+
           '<span class="fo-m">'+m[0]+(m[4]?' <abbr title="'+e(m[4])+'">?</abbr>':'')+'</span>'+
           '<span class="fo-b'+(bw?' win':'')+'">'+(dir?'<span class="fo-t"><i style="width:'+lb.toFixed(1)+'%"></i></span>':'')+'<b class="num">'+m[2](b)+'</b></span></div>'});
      score.push([wa,wb]);
      var tot=wa+wb||1,gt=g[0].split(' · ');
      h+='<div class="fo-g"><div class="fo-gh"><h4>'+gt[0]+(gt[1]?' <small>'+gt[1]+'</small>':'')+'</h4>'+
         '<div class="fo-sc"><b class="fo-sa'+(wa>wb?' win':'')+'">'+wa+'</b><span class="fo-split"><i class="fo-sa" style="width:'+(wa/tot*100).toFixed(1)+'%"></i><i class="fo-sb" style="width:'+(wb/tot*100).toFixed(1)+'%"></i></span><b class="fo-sb'+(wb>wa?' win':'')+'">'+wb+'</b></div>'+
         '</div>'+rows+'</div>'});
    R.innerHTML=h;
    if(same){C.innerHTML='<p>Pick two different players.</p>';return}
    // verdicts: short term = next two weeks' projected points; long term = rest-of-season points per game
    var sa=(a.p1||0)+(a.p2||0),sb=(b.p1||0)+(b.p2||0),la=a.ros||0,lb=b.ros||0;
    var sw=Math.abs(sa-sb)<1.5?null:(sa>sb?a:b),lw=Math.abs(la-lb)<0.5?null:(la>lb?a:b);
    function v(t,w,d,u){return '<div class="fo-v '+(w?(w===a?'fo-wa':'fo-wb'):'fo-wt')+'"><span class="fo-vk">'+t+'</span><b>'+(w?e(last(w.n)):'Toss-up')+'</b><small>'+(w?'by '+d.toFixed(1)+' '+u:'within '+(u==='pts'?'1.5 points':'half a point a game'))+'</small></div>'}
    var call='';
    var fa=!a.o&&b.o?a:!b.o&&a.o?b:null,kept=fa?(fa===a?b:a):null;
    if(fa){
      var dL=(fa.ros||0)-(kept.ros||0),dS=((fa.p1||0)+(fa.p2||0))-((kept.p1||0)+(kept.p2||0)),F=e(fa.n),K=e(kept.n),f=e(last(fa.n)),k=e(last(kept.n));
      var now=dS>=1.5?'better the next two weeks too':dS>-1.5?'about even the next two weeks':'';
      if(dL>=1&&dS>-1.5)call='<b>Grab '+F+', drop '+K+'.</b> '+f+' is worth '+dL.toFixed(1)+' more points a game the rest of the way and '+now+'.';
      else if(dL>=1)call='<b>Stash '+F+'</b> if you have the room. '+k+' is the better play the next two weeks, but '+f+' should be worth '+dL.toFixed(1)+' more a game after that.';
      else if(dL>-1){
        if(dS>=3)call='<b>Fine to swap for the short term.</b> '+f+' projects '+dS.toFixed(1)+' more the next two weeks and the rest of the season is close.';
        else call='<b>Close call, lean '+(dL>=0?f:k)+'.</b> They\'re within a point a game over the rest of the season; '+(dS>=1.5?f+' has the better next two weeks':dS<=-1.5?k+' has the better next two weeks':'the next two weeks are even')+'. Check the usage trend before dropping anyone.';
      }
      else if(dS>=3)call='<b>Streamer only.</b> '+f+' projects '+dS.toFixed(1)+' more the next two weeks, but '+k+' is worth '+(-dL).toFixed(1)+' more a game over the season. Don\'t drop '+k+' for him unless you need the points now.';
      else call='<b>Keep '+K+'.</b> '+f+' isn\'t an upgrade: '+(-dL).toFixed(1)+' fewer points a game the rest of the way.';
      if(fa.rp!=null&&fa.rp>=50&&dL>=1)call+=' He\'s rostered in '+fa.rp+'% of ESPN leagues, so claim him before someone else does.';
    } else if(!a.o&&!b.o){
      call=lw?'<b>If you add one, take '+e(lw.n)+'</b>'+(sw&&sw!==lw?' for the long run; '+e(last(sw.n))+' is the better one-week stream.':'.'):'<b>Toss-up</b> between the two free agents.';
    } else {
      call=lw&&(sw===lw||!sw)?'<b>'+e(lw.n)+'</b> is the better hold, now and later.':lw&&sw?'<b>'+e(sw.n)+'</b> for the next two weeks, <b>'+e(lw.n)+'</b> for the rest of the season.':sw?'<b>'+e(sw.n)+'</b> for the next two weeks; long term it\'s close.':'<b>Too close to call.</b>';
    }
    call=call.replace(/\.(<\/b>)?\./g,'.$1');
    var plain=call.replace(/<[^>]+>/g,''),tag=/^Grab/.test(plain)?['Grab','go']:/^Stash/.test(plain)?['Stash','go']:/^Fine to swap/.test(plain)?['Swap','go']:/^Streamer/.test(plain)?['Stream','mid']:
      /^Keep/.test(plain)?['Keep','stop']:/^Close call/.test(plain)?['Close call','mid']:/^If you add/.test(plain)?['Add','go']:/^(Toss|Too close)/.test(plain)?['Toss-up','mid']:['Hold','mid'];
    C.innerHTML='<div class="fo-vs2">'+v('Short term',sw,Math.abs(sa-sb),'pts')+v('Long term',lw,Math.abs(la-lb),'pts/g')+'</div><div class="fo-say"><span class="fo-pill '+tag[1]+'">'+tag[0]+'</span><p>'+call+'</p></div>';
  }
  A.addEventListener('change',draw);B.addEventListener('change',draw);draw();
  [A,B,document.getElementById('ss-a'),document.getElementById('ss-b')].forEach(function(s){if(s)window.dfCombo(s)});
})();
(function(){
  /* Steady or Streaky: same hover/tap card behaviour as Volume vs. Scoring */
  var plot=document.getElementById('st-plot'),src=document.getElementById('st-data');if(!plot||!src)return;
  var info=JSON.parse(src.textContent),tip=document.getElementById('st-tip'),tm=document.getElementById('st-team');
  var dots=[].slice.call(plot.querySelectorAll('.vd')),pinned=null,show={RB:1,WR:1,TE:1,QB:0};
  function e(s){return String(s==null?'':s).replace(/[&<>"]/g,function(m){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]})}
  function html(p){
    var own=p.o?'<i class="lg lg-'+p.o+'"></i>'+e(p.on):'<span class="own fa">FA</span>';
    var inj=(p.inj&&p.inj!=='ACTIVE'&&p.inj!=='NORMAL')?' <span class="inj">'+e(p.inj.replace('_',' ').toLowerCase())+'</span>':'';
    var mx=Math.max.apply(null,p.wk.concat([1]));
    var bars='<span class="st-bars">'+p.wk.map(function(v){return '<i style="height:'+Math.max(4,v/mx*100).toFixed(0)+'%" title="'+v+'"></i>'}).join('')+'</span>';
    return '<span class="kicker">'+e(p.pos)+' · '+e(p.tm)+' · '+p.g+' games</span><b class="nm">'+e(p.n)+'</b>'+inj+
      '<span class="tt-own">'+own+'</span>'+
      '<span>'+p.ppg.toFixed(1)+' PPR/g · swing ±'+p.sd.toFixed(1)+'</span>'+bars+
      '<span class="tt-g"><span><em>Floor</em><b>'+p.lo.toFixed(1)+'</b></span><span><em>Median</em><b>'+p.md.toFixed(1)+'</b></span><span><em>Ceiling</em><b>'+p.hi.toFixed(1)+'</b></span>'+
      '<span><em>Last 3</em><b>'+p.l3.toFixed(1)+'</b></span></span>';
  }
  function place(d){
    var p=info[+d.dataset.i];tip.innerHTML=html(p);tip.hidden=false;
    var x=parseFloat(d.style.left),y=parseFloat(d.style.top);
    tip.style.left=tip.style.right=tip.style.top=tip.style.bottom='';
    if(x>55)tip.style.right=(100-x+2)+'%';else tip.style.left=(x+2)+'%';
    if(y>55)tip.style.bottom=(100-y+2)+'%';else tip.style.top=(y+2)+'%';
  }
  function hide(){if(pinned){place(pinned)}else{tip.hidden=true}}
  function pin(d){dots.forEach(function(x){x.classList.toggle('on',x===d)});pinned=d;if(d){place(d)}else{tip.hidden=true}}
  function filter(){
    var team=+tm.value,on=team!==0;
    dots.forEach(function(d){
      var p=info[+d.dataset.i],mine=team===-1?!p.o:p.o===team;
      d.classList.toggle('off',!show[p.pos]);
      d.classList.toggle('hit',on&&mine);d.classList.toggle('dim',on&&!mine);
    });
    plot.classList.toggle('searching',on);
    if(pinned&&(pinned.classList.contains('off')||pinned.classList.contains('dim')))pin(null);
  }
  function near(ev,max){
    var best=null,bd=max*max;
    dots.forEach(function(d){if(d.classList.contains('off'))return;
      var r=d.getBoundingClientRect(),dx=r.left+r.width/2-ev.clientX,dy=r.top+r.height/2-ev.clientY,dd=dx*dx+dy*dy;if(dd<bd){bd=dd;best=d}});
    return best;
  }
  var hov=null;
  plot.addEventListener('pointermove',function(ev){if(ev.pointerType!=='mouse')return;var d=near(ev,22);if(d===hov)return;hov=d;
    dots.forEach(function(x){x.classList.toggle('hov',x===d)});if(d)place(d);else hide()});
  plot.addEventListener('pointerleave',function(){hov=null;dots.forEach(function(x){x.classList.remove('hov')});hide()});
  dots.forEach(function(d){d.addEventListener('focus',function(){place(d)});d.addEventListener('blur',hide)});
  document.addEventListener('click',function(ev){if(pinned&&!plot.contains(ev.target)&&!ev.target.closest('.st-ctl'))pin(null)});
  plot.addEventListener('click',function(ev){var d=ev.detail===0&&ev.target.classList.contains('vd')?ev.target:near(ev,30);pin(d&&pinned!==d?d:null)});
  tm.addEventListener('change',filter);
  document.querySelectorAll('.st-pos .pt').forEach(function(b){b.addEventListener('click',function(){
    var on=b.getAttribute('aria-pressed')!=='true';b.setAttribute('aria-pressed',on?'true':'false');
    show[b.dataset.f]=on?1:0;filter()})});
  filter();
})();
</script>"""

CSS += r"""
/* Player Face-Off (restyled 2026-10-27): A in Honolulu blue, B in yellow (user); yellow is a fill, text on it stays ink; bars grow out from the middle */
.fo{--fa:var(--honolulu);--fb:var(--hi);display:grid;gap:14px}
.fo-pick{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:10px;align-items:end}
.fo-pick label{display:grid;gap:4px;min-width:0}
.fo-pick label:first-child .cb-in{border-left:6px solid var(--fa)}
.fo-pick label:last-child .cb-in{border-left:6px solid var(--fb)}
.fo-vs{font-family:var(--display);font-weight:900;font-size:1.1rem;color:var(--muted);padding-bottom:9px;text-align:center}
.fo-head{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:10px;align-items:stretch}
.fo-hv{align-self:center;width:42px;height:42px;border-radius:50%;display:grid;place-items:center;background:var(--rule);color:var(--sheet);font-family:var(--display);font-weight:900;font-size:.95rem;text-transform:uppercase}
.fo-card{display:grid;grid-template-columns:auto minmax(0,1fr);gap:12px;align-items:center;padding:14px;background:var(--sheet);border:2px solid var(--line);min-width:0}
.fo-ca{border-top:8px solid var(--fa)}.fo-cb{border-top:8px solid var(--fb);grid-template-columns:minmax(0,1fr) auto;text-align:right}
.fo-cb .fo-crest{order:2}.fo-cb .fo-id{justify-items:end}
.fo-crest .lg-md{width:52px;height:52px}
.fo-fa{display:grid;place-items:center;width:52px;height:52px;border-radius:50%;background:var(--paper);color:var(--ink);border:2px dashed var(--muted);font-family:var(--mono);font-weight:700;font-size:.85rem}
.fo-id{display:grid;gap:3px;min-width:0}
.fo-tag{font-family:var(--mono);font-size:.66rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.fo-nm{font-family:var(--display);font-weight:900;font-size:clamp(1.15rem,2.6vw,1.75rem);text-transform:uppercase;line-height:1;overflow-wrap:anywhere}
.fo-ca .fo-nm{color:var(--fa)}
.fo-id .inj{justify-self:start;font-family:var(--mono);font-size:.6rem}.fo-cb .fo-id .inj{justify-self:end}
.fo-own{font-size:.82rem;color:var(--ink);font-weight:600}
.fo-rp{display:block;width:100%;max-width:150px;height:5px;background:var(--line);border-radius:3px;overflow:hidden;margin-top:3px}
.fo-rp i{display:block;height:100%;background:var(--fa);border-radius:3px}.fo-cb .fo-rp i{background:var(--fb);margin-left:auto}
.fo-rpt{font-family:var(--mono);font-size:.6rem;color:var(--muted)}
/* verdict */
.fo-call{display:grid;gap:12px;padding:14px;background:var(--sheet);border:3px solid var(--rule)}
.fo-vs2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.fo-v{display:grid;gap:2px;padding:10px 12px;border-left:6px solid var(--line);background:var(--paper)}
.fo-v.fo-wa{border-color:var(--fa)}.fo-v.fo-wb{border-color:var(--fb)}
.fo-vk{font-family:var(--mono);font-size:.62rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.fo-v b{font-family:var(--display);font-weight:900;font-size:1.5rem;text-transform:uppercase;line-height:1.05}
.fo-v.fo-wa b{color:var(--fa)}.fo-v.fo-wt b{color:var(--muted)}
.fo-v.fo-wb{background:var(--fb);border-color:var(--fb)}.fo-v.fo-wb b,.fo-v.fo-wb small,.fo-v.fo-wb .fo-vk{color:var(--hi-ink)}
.fo-v small{font-family:var(--mono);font-size:.66rem;color:var(--muted)}
.fo-say{display:flex;gap:10px;align-items:flex-start}
.fo-say p{margin:0;font-size:.98rem;line-height:1.45}
.fo-pill{flex:none;font-family:var(--mono);font-weight:700;font-size:.66rem;letter-spacing:.08em;text-transform:uppercase;padding:4px 9px;border-radius:999px;margin-top:2px;white-space:nowrap}
.fo-pill.go{background:var(--blue);color:var(--blue-ink)}.fo-pill.mid{background:var(--paper);color:var(--ink);box-shadow:inset 0 0 0 2px var(--rule)}.fo-pill.stop{background:var(--rule);color:var(--sheet)}
/* groups */
.fo-rows{display:grid;gap:18px}
.fo-g{display:grid}
.fo-gh{display:grid;gap:8px;padding-bottom:8px;border-bottom:3px solid var(--rule);margin-bottom:2px}
.fo-gh h4{font-family:var(--display);font-weight:900;font-size:1.15rem;text-transform:uppercase;margin:0;text-align:center;letter-spacing:.01em}
.fo-gh h4 small{display:block;font-family:var(--mono);font-weight:400;font-size:.62rem;letter-spacing:.08em;color:var(--muted);margin-top:2px}
.fo-sc{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:10px;align-items:center}
.fo-sc b{font-family:var(--display);font-weight:900;font-size:1.25rem;min-width:24px;text-align:center;color:var(--muted)}
.fo-sc b.fo-sa.win{color:var(--fa)}.fo-sc b.fo-sb.win{color:var(--hi-ink);background:var(--fb);border-radius:4px;padding:0 6px}
.fo-split{display:flex;height:8px;border-radius:4px;overflow:hidden;background:var(--line);gap:2px}
.fo-split i{display:block;height:100%}.fo-split i.fo-sa{background:var(--fa)}.fo-split i.fo-sb{background:var(--fb)}
/* rows */
.fo-r{display:grid;grid-template-columns:minmax(0,1fr) 150px minmax(0,1fr);gap:10px;align-items:center;padding:7px 0;border-bottom:1px solid var(--line)}
.fo-m{font-family:var(--mono);font-size:.64rem;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);text-align:center;line-height:1.3}
.fo-m abbr{text-decoration:none;border:1px solid var(--line);border-radius:50%;padding:0 4px;font-size:.55rem;cursor:help}
.fo-a,.fo-b{display:flex;align-items:center;gap:8px;min-width:0}
.fo-t{flex:1;display:flex;height:10px;background:var(--paper);border-radius:5px;overflow:hidden;min-width:0}
.fo-a .fo-t{justify-content:flex-end}
.fo-t i{display:block;height:100%;border-radius:5px;background:var(--silver)}
.fo-a.win .fo-t i{background:var(--fa);opacity:1}.fo-b.win .fo-t i{background:var(--fb);opacity:1}
.fo-a b,.fo-b b{font-size:.92rem;font-weight:500;flex:0 0 96px;width:96px;overflow-wrap:anywhere;line-height:1.15}
.fo-a b{text-align:left}.fo-b b{text-align:right}
.fo-a.win b{font-weight:800;color:var(--fa)}.fo-b.win b{font-weight:800}
.fo-nb .fo-a b,.fo-nb .fo-b b{flex:1;width:auto}
.fo-a b small,.fo-b b small{font-family:var(--mono);font-size:.6rem;font-weight:400;color:var(--muted);display:block;line-height:1.2;white-space:normal;margin-top:1px}
.fo-a b small.hot,.fo-b b small.hot{color:var(--red)}.fo-a b small.due,.fo-b b small.due{color:var(--blue)}
.fo-how summary{cursor:pointer;font-family:var(--mono);font-size:.7rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);padding:6px 0}
.fo-how[open] summary{color:var(--ink)}
.fo-tr{font-size:.7rem;font-weight:700}.fo-tr.up{color:var(--blue)}.fo-tr.dn{color:var(--red)}
/* type-to-search player box (user, 2026-10-27) */
.cb{position:relative;min-width:0}
.cb-in{font:inherit;font-size:.95rem;padding:8px 10px;border:2px solid var(--rule);background:var(--sheet);color:var(--ink);width:100%;min-width:0;border-radius:0;-webkit-appearance:none;appearance:none}
.cb-in:focus{outline:3px solid var(--hi);outline-offset:0}
.cb-list{position:absolute;z-index:30;left:0;right:0;top:100%;margin:2px 0 0;padding:0;list-style:none;max-height:300px;overflow-y:auto;background:var(--sheet);border:2px solid var(--rule);box-shadow:0 6px 18px rgba(0,0,0,.18)}
.cb-list li{display:grid;grid-template-columns:minmax(0,1fr) auto;column-gap:8px;padding:7px 10px;cursor:pointer;border-bottom:1px solid var(--line)}
.cb-list li b{font-weight:600;font-size:.92rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cb-list li small{grid-column:1;font-family:var(--mono);font-size:.62rem;color:var(--muted)}
.cb-list li em{grid-column:2;grid-row:1/span 2;align-self:center;font-style:normal;font-family:var(--mono);font-size:.62rem;color:var(--muted);text-align:right;max-width:110px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cb-list li[aria-selected="true"],.cb-list li:hover{background:var(--paper)}
.cb-list li.cb-none{cursor:default;color:var(--muted);font-size:.85rem}
/* Steady or Streaky (reuses the Volume vs. Scoring plot styles) */
.p-QB{background:var(--silver)}
.sw.p-QB{width:10px;height:10px;border-radius:50%}
.st{aspect-ratio:1.6}
.st-mx{position:absolute;top:0;bottom:0;border-left:1.5px dashed var(--red);pointer-events:none}
.st-my{position:absolute;left:0;right:0;border-top:1.5px dashed var(--red);pointer-events:none}
.st .q{position:absolute;font-family:var(--mono);font-size:.62rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);pointer-events:none}
.st-q1{right:8px;top:6px}.st-q2{right:8px;bottom:6px}.st-q3{left:8px;top:6px}.st-q4{left:8px;bottom:6px}
.st-y{position:absolute;left:-30px;top:0;bottom:0;width:24px;font-family:var(--mono);font-size:.64rem;color:var(--muted);pointer-events:none}
.st-y span{position:absolute;right:0;transform:translateY(-50%)}
.st-wrap{grid-template-columns:34px minmax(0,1fr)}
.st-sw{display:inline-block;width:16px;border-top:1.5px dashed var(--red);vertical-align:middle}
.st-team{display:grid;gap:4px}
.st-team select{font:inherit;font-size:.95rem;padding:7px 10px;border:2px solid var(--rule);background:var(--sheet);color:var(--ink);min-width:220px}
.st-pos{display:flex;flex-wrap:wrap;gap:4px}.st-pos .pt{display:inline-flex;align-items:center;gap:6px}.st-pos .pt .sw{border:1.5px solid var(--sheet)}.st-pos .pt[aria-pressed="false"]{opacity:.55}
.st .vd:not(.lab) em{display:none}.st.searching .vd em{display:none}.st.searching .vd.hit em{display:block}
.st-bars{display:flex;align-items:flex-end;gap:3px;height:34px;border-bottom:1px solid var(--line)}
.st-bars i{display:block;flex:1;background:var(--blue);min-height:2px}
@media (max-width:760px){
  .fo-pick{grid-template-columns:1fr;gap:4px}.fo-pick .fo-vs{padding:0;font-size:.9rem}.cb-in{font-size:16px}
  .fo-head{grid-template-columns:1fr 1fr;gap:6px;position:relative}
  .fo-hv{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:32px;height:32px;font-size:.72rem;z-index:1;box-shadow:0 0 0 3px var(--sheet)}
  .fo-card,.fo-cb{grid-template-columns:1fr;gap:6px;padding:10px;text-align:left}
  .fo-cb{text-align:right}.fo-cb .fo-crest{order:0;justify-self:end}
  .fo-crest .lg-md,.fo-fa{width:36px;height:36px}.fo-fa{font-size:.7rem}
  .fo-nm{font-size:1.05rem}.fo-own{font-size:.72rem}.fo-rp{max-width:none}
  .fo-call{padding:10px}.fo-v{padding:8px 9px}.fo-v b{font-size:1.1rem}.fo-say p{font-size:.88rem}.fo-say{flex-direction:column;gap:6px}
  .fo-gh h4{font-size:1rem}
  .fo-r{grid-template-columns:minmax(0,1fr) 84px minmax(0,1fr);gap:6px;padding:6px 0}.fo-m{font-size:.52rem;letter-spacing:.02em}
  .fo-a,.fo-b{gap:5px}.fo-a b,.fo-b b{font-size:.8rem;flex:0 0 54px;width:54px}.fo-t{height:8px}
  .fo-a b small,.fo-b b small{font-size:.52rem}
  .st{aspect-ratio:1.05}.st .q{font-size:.52rem}
}
"""
