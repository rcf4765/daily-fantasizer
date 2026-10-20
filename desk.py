"""Player Stats sections added 2026-10-19 at the user's request (all automatic):

- Trend Lines (#ps-trend): pick any player for his PPR points every week of the fantasy season (weeks 1-17)
  against his projection. Past weeks: the blended projection made that week (FantasyPros consensus + ESPN).
  Coming weeks with posted projections: the same blend. Later weeks: his rest-of-season points per game
  (Roster Radar value), zero on his bye (nflverse schedule). Targets and snap share under the chart.
- Defense Matchups (#ps-defense): PPR points each NFL defense has allowed per game to QBs, RBs, WRs and TEs
  (every fantasy-relevant player the fetch tracks, weeks 1..N), shaded against the league average, with
  who it faces next week.
- Waiver Targets (#ps-waiver): free agents ranked by rest-of-season value, each tagged with the league teams
  whose best starting lineup he'd improve and by how much (points per week).

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


# ------------------------------------------------------------------ waiver targets
def waiver(d, W, short):
    import strength as S
    import teams as TM
    S.ros_values(d)
    own = [p for p in d.P if p.get("owner")]
    roster = defaultdict(list)
    for p in own:
        roster[p["owner"]].append(p)
    val = lambda p: p["ros"]
    tot = lambda ps: sum(val(x) for _, x in TM._lineup(ps, val) if x)
    base = {t: tot(ps) for t, ps in roster.items()}
    fa = [p for p in d.P if not p.get("owner") and p.get("ros_rank") and p.get("inj") != "INJURY_RESERVE"]
    fa.sort(key=lambda p: -p["ros"])
    cards = []
    for p in fa[:60]:
        gains = sorted(((tot(roster[t] + [p]) - base[t], t) for t in roster), reverse=True)
        gains = [(g, t) for g, t in gains if g >= 0.3]
        if not gains:
            continue
        tags = "".join(f'<span class="wt-tag">{lg(t)}{esc(short[t])}<b class="num">+{g:.1f}</b></span>' for g, t in gains[:4])
        more = f'<span class="wt-more">+{len(gains) - 4} more</span>' if len(gains) > 4 else ""
        inj = p.get("inj", "ACTIVE")
        injt = f'<span class="inj">{esc(inj.replace("_", " ").lower())}</span>' if inj not in ("ACTIVE", "NORMAL", None) else ""
        cards.append(f'<article class="wt"><span class="kicker">{esc(p["pos"])}{p["ros_rank"]} rest of season · {esc(p["team"])}</span>'
                     f'<h3>{esc(p["name"])}{injt}</h3>'
                     f'<div class="wt-st"><span><b class="num">{p["ppg"]:.1f}</b>PPR/g</span><span><b class="num">{p.get("l3", 0):.1f}</b>last 3</span><span><b class="num">{p["ros"]:.1f}</b>ROS/g</span></div>'
                     f'<span class="kicker">Upgrade for · pts per week</span><div class="wt-tags">{tags}{more}</div></article>')
        if len(cards) == 8:
            break
    if not cards:
        cards = ['<article class="wt empty"><h3>The wire is dry</h3><span class="kicker">No free agent beats a starter on any roster</span></article>']
    body = (f'<div class="wt-grid">{"".join(cards)}</div>'
            f'<p class="note-s">Free agents with a rest-of-season consensus ranking, best first, shown when they&#39;d improve at least one team&#39;s best starting lineup '
            f'(QB, 2 RB, 2 WR, TE, FLEX). Tags show by how many rest-of-season points per week. Injured reserve left out.</p>')
    return sec("ps-waiver", "Waiver Targets", "Free agents by team need", body)


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
    try:
        out["waiver"] = waiver(d, W, short)
    except Exception as e:
        print("waiver targets skipped:", e); out["waiver"] = ""
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
/* Waiver Targets */
.wt-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,250px),1fr));gap:14px}
.wt{border:2px solid var(--rule);border-top:6px solid var(--hi);background:var(--sheet);padding:12px;display:grid;gap:6px;align-content:start}
.wt.empty{border-top-color:var(--silver)}
.wt h3{font-size:1.45rem;font-weight:900;text-transform:uppercase}
.wt h3 .inj{margin-left:6px;font-family:var(--mono);font-size:.6rem;vertical-align:middle}
.wt-st{display:flex;gap:14px;font-family:var(--mono);font-size:.66rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.wt-st span{display:grid}.wt-st b{font-size:1.05rem;color:var(--ink);letter-spacing:0}
.wt-tags{display:flex;flex-wrap:wrap;gap:5px}
.wt-tag{display:inline-flex;align-items:center;gap:5px;font-family:var(--mono);font-size:.68rem;border:1.5px solid var(--rule);padding:2px 6px 2px 3px;background:var(--paper)}
.wt-tag b{color:var(--blue)}
.wt-more{font-family:var(--mono);font-size:.66rem;color:var(--muted);align-self:center}
@media (max-width:760px){
  .tl-tiles{grid-template-columns:1fr 1fr}.tl-tiles b{font-size:1.2rem}
  .tl-grid{font-size:.62rem}.tl-grid .tl-l,.tl-grid .tl-h{font-size:.52rem}
  .dv{grid-template-columns:40px repeat(4,minmax(0,1fr)) 62px;min-width:0}.dv-c{flex-direction:column;align-items:center;gap:0;padding:4px 1px}.dv-c b{font-size:.74rem}.dv-o{font-size:.58rem;padding-left:4px}.dv-t{font-size:.85rem}
  .wt-grid{grid-template-columns:1fr 1fr!important;gap:8px}.wt{padding:9px}.wt h3{font-size:1.02rem;line-height:1}.wt-st{gap:8px}.wt-tag{font-size:.58rem}
}
"""
