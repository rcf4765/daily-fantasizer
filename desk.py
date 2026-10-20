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


def faceoff(d, W, short, own_team):
    import strength as S
    S.ros_values(d)
    rawp = S.raw_proj(W)
    sch = _sched(); byes = (sch or {}).get("byes", {})
    nxt = W + 1
    rows = []
    for p in d.P:
        if p["g"] < 1 or not _relevant(p):
            continue
        pj = S.proj_for(d, p, nxt, rawp)
        if nxt in byes.get(p["team"], []) or p.get("inj") in ("OUT", "INJURY_RESERVE"):
            pj = 0.0
        g = [w for w in d.games(p) if w <= W]
        pts = [p["act"][w]["pts"] for w in g]
        rows.append([p["name"], p["pos"], p["team"], p.get("owner") or 0, round(p["ppg"], 1), round(p["l3"], 1),
                     None if pj is None else round(pj, 1), round(p["ros"], 1), p.get("ros_rank") or 0,
                     round(p["tgt_g"], 1), round(p["tch_g"], 1), None if p["ts"] is None else round(p["ts"] * 100),
                     None if p["snap"] is None else round(p["snap"] * 100), round(max(pts), 1) if pts else 0, round(min(pts), 1) if pts else 0,
                     p.get("inj", "ACTIVE")])
    if len(rows) < 2:
        return ""
    rows.sort(key=lambda r: (r[3] == 0, r[3], -r[7]))
    mine = sorted([r for r in rows if r[3] == own_team and r[1] in ("RB", "WR", "TE")], key=lambda r: -r[7])
    # default: the owner team's two closest RB/WR/TE by rest-of-season value outside its top three (a real FLEX-type call)
    pair = None
    if len(mine) >= 2:
        playing = [r for r in mine if r[6]]  # skip byes and players ruled out for next week
        mine = playing if len(playing) >= 2 else mine
        cands = mine[2:] if len(mine) >= 4 else mine
        pair = min(((a, b) for i, a in enumerate(cands) for b in cands[i + 1:]), key=lambda ab: abs(ab[0][7] - ab[1][7]), default=None)
    data = {"teams": {str(k): v for k, v in short.items()}, "p": rows, "nxt": nxt,
            "def": [pair[0][0], pair[1][0]] if pair else [rows[0][0], rows[1][0]]}
    body = (f'<div class="fo"><div class="fo-pick"><label><span class="kicker">Player A</span><select id="fo-a"></select></label><span class="fo-vs">vs.</span>'
            f'<label><span class="kicker">Player B</span><select id="fo-b"></select></label></div>'
            f'<div class="fo-head" id="fo-head"></div><div class="fo-rows" id="fo-rows"></div><div class="fo-sum" id="fo-sum"></div></div>'
            f'<script type="application/json" id="fo-data">{json.dumps(data, separators=(",", ":")).replace("</", "<\\/")}</script>'
            f'<p class="note-s">Any two players who matter: rostered, ranked or scoring 6+ PPR per game. Week {nxt} projection is the blended number (zero on a bye or ruled out). '
            f'Rest of season = his consensus ranking turned into points per game. Floor and ceiling = his worst and best game so far.</p>')
    return sec("ps-faceoff", "Player Face-Off", "Any two players, stat by stat", body)


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
  /* Player Face-Off */
  var el=document.getElementById('fo-data'); if(!el)return;
  var D=JSON.parse(el.textContent),P=D.p,T=D.teams,by={};P.forEach(function(r){by[r[0]]=r});
  var A=document.getElementById('fo-a'),B=document.getElementById('fo-b'),H=document.getElementById('fo-head'),R=document.getElementById('fo-rows'),S=document.getElementById('fo-sum');
  [A,B].forEach(function(sel){var groups={};P.forEach(function(r){var g=r[3]?T[r[3]]:'Free agents';(groups[g]=groups[g]||[]).push(r)});
    Object.keys(groups).forEach(function(g){var og=document.createElement('optgroup');og.label=g;
      groups[g].forEach(function(r){var o=document.createElement('option');o.value=r[0];o.textContent=r[0]+' ('+r[1]+', '+r[2]+')';og.appendChild(o)});sel.appendChild(og)})});
  A.value=D.def[0];B.value=D.def[1];
  function e(s){return String(s).replace(/[&<>"]/g,function(m){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]})}
  // [label, index, higher is better?, format]
  var M=[['PPR per game',4,1,'f'],['Last 3 games',5,1,'f'],['Week '+D.nxt+' projection',6,1,'p'],['Rest of season, pts/g',7,1,'f'],['ROS position rank',8,-1,'r'],
         ['Ceiling (best game)',13,1,'f'],['Floor (worst game)',14,1,'f'],['Targets per game',9,1,'f'],['Touches per game',10,1,'f'],['Target share',11,1,'%'],['Snap share',12,1,'%']];
  function fmt(v,f){if(v==null)return '–';if(f==='r')return v?'#'+v:'–';if(f==='%')return v+'%';if(f==='p'&&v===0)return 'no game';return v.toFixed(1)}
  function side(r){var inj=(r[15]&&r[15]!=='ACTIVE'&&r[15]!=='NORMAL')?' <span class="inj">'+e(r[15].replace('_',' ').toLowerCase())+'</span>':'';
    return '<span class="kicker">'+e(r[1])+' · '+e(r[2])+'</span><b>'+e(r[0])+inj+'</b><span class="fo-own">'+(r[3]?'<i class="lg lg-'+r[3]+' lg-sm"></i>'+e(T[r[3]]):'<span class="own fa">FA</span>')+'</span>'}
  function draw(){var a=by[A.value],b=by[B.value];if(!a||!b)return;
    H.innerHTML='<div class="fo-ha">'+side(a)+'</div><span class="fo-hv">vs.</span><div class="fo-hb">'+side(b)+'</div>';
    var h='',wa=0,wb=0;
    M.forEach(function(m){var va=a[m[1]],vb=b[m[1]],f=m[3];
      var ca=(f==='r')?(va||999):(va==null?-1:va),cb=(f==='r')?(vb||999):(vb==null?-1:vb);
      var aw=a[0]!==b[0]&&(m[2]>0?ca>cb:ca<cb),bw=a[0]!==b[0]&&(m[2]>0?cb>ca:cb<ca);if(aw)wa++;if(bw)wb++;
      var mx=Math.max(ca,cb,0.1),la=f==='r'?(va?Math.max(6,100-va*1.6):0):Math.max(0,ca)/mx*100,lb=f==='r'?(vb?Math.max(6,100-vb*1.6):0):Math.max(0,cb)/mx*100;
      h+='<div class="fo-r"><span class="fo-a'+(aw?' win':'')+'"><b class="num">'+fmt(va,f)+'</b><i style="width:'+la.toFixed(1)+'%"></i></span><span class="fo-m">'+m[0]+'</span>'+
         '<span class="fo-b'+(bw?' win':'')+'"><i style="width:'+lb.toFixed(1)+'%"></i><b class="num">'+fmt(vb,f)+'</b></span></div>'});
    R.innerHTML=h;
    S.innerHTML='<span class="'+(wa>wb?'win':'')+'"><b class="num">'+wa+'</b>categories won</span><span class="fo-sv">'+(wa===wb?'Dead even':(wa>wb?e(a[0]):e(b[0]))+' takes it')+'</span><span class="'+(wb>wa?'win':'')+'"><b class="num">'+wb+'</b>categories won</span>';}
  A.addEventListener('change',draw);B.addEventListener('change',draw);draw();
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
/* Player Face-Off */
.fo{display:grid;gap:12px}
.fo-pick{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:10px;align-items:end}
.fo-pick label{display:grid;gap:4px;min-width:0}
.fo-pick select{font:inherit;font-size:.95rem;padding:7px 10px;border:2px solid var(--rule);background:var(--sheet);color:var(--ink);width:100%}
.fo-vs,.fo-hv{font-family:var(--display);font-weight:900;font-size:1.3rem;color:var(--muted);padding-bottom:6px;text-align:center}
.fo-head{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:10px;align-items:center;padding:12px 14px;border:3px solid var(--rule);background:radial-gradient(var(--dot) 1.2px,transparent 1.4px) 0 0/8px 8px,var(--sheet)}
.fo-ha,.fo-hb{display:grid;gap:3px;min-width:0}.fo-ha{text-align:right;justify-items:end}
.fo-head b{font-family:var(--display);font-weight:900;font-size:clamp(1.2rem,3vw,1.9rem);text-transform:uppercase;line-height:1}
.fo-head b .inj{font-family:var(--mono);font-size:.6rem;vertical-align:middle;margin-left:4px}
.fo-own{display:flex;align-items:center;gap:6px;font-size:.8rem;color:var(--muted)}
.fo-rows{display:grid}
.fo-r{display:grid;grid-template-columns:minmax(0,1fr) 150px minmax(0,1fr);gap:10px;align-items:center;padding:5px 0;border-bottom:1px solid var(--line)}
.fo-m{font-family:var(--mono);font-size:.66rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);text-align:center}
.fo-a,.fo-b{display:flex;align-items:center;gap:8px}.fo-a{flex-direction:row-reverse}
.fo-a i,.fo-b i{display:block;height:12px;max-width:70%;background:var(--silver)}
.fo-a.win i{background:var(--blue)}.fo-b.win i{background:var(--ink)}
.fo-a b,.fo-b b{font-size:.9rem;font-weight:400;min-width:56px}.fo-a b{text-align:left}.fo-b b{text-align:right}
.fo-a.win b,.fo-b.win b{font-weight:700}
.fo-sum{display:grid;grid-template-columns:1fr auto 1fr;gap:10px;align-items:center;border-top:3px solid var(--rule);padding-top:8px}
.fo-sum span{display:grid;font-family:var(--mono);font-size:.66rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.fo-sum span:first-child{text-align:right}
.fo-sum b{font-family:var(--display);font-size:2rem;font-weight:900;color:var(--ink);letter-spacing:0}
.fo-sum .win b{color:var(--blue)}
.fo-sum .fo-sv{font-family:var(--display);font-weight:900;font-size:1.05rem;color:var(--ink);text-align:center;letter-spacing:.02em}
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
  .fo-r{grid-template-columns:minmax(0,1fr) 92px minmax(0,1fr);gap:6px}.fo-m{font-size:.54rem;letter-spacing:.02em}.fo-a b,.fo-b b{font-size:.78rem;min-width:40px}
  .fo-head{padding:9px}.fo-own{font-size:.68rem}.fo-pick{gap:6px}.fo-pick select{font-size:.8rem;padding:6px}
  .st{aspect-ratio:1.05}.st .q{font-size:.52rem}
}
"""
