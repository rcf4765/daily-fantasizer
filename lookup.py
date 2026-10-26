"""The Daily Fantasizer: Player Lookup (Player Stats tab, added 2026-10-26 at the user's request).

Type a player's name and get one card with everything we have on him, fantasy and real life, through the
edition's week W. It replaced the Current Data board and the "Every graded player" table (user, 2026-10-26),
so the card carries all of their numbers too:

- Fantasy: PPR/g and its rank at the position (2+ games, as Current Data ranked), last 3 with arrow, total PPR,
  expected PPR/g from volume (Volume vs. Scoring's fit), week W+1 blended projection and opponent, rest-of-season
  consensus rank, owner or FA, injury, bye.
- Graded (was "Every graded player"): every completed week's consensus position rank -> actual finish at the
  position, PPR points vs. the consensus projection, plus the season averages (avg rank, avg finish, spots vs.
  rank, points vs. projection).
- Usage (was Current Data): games, snap %, target share, air-yards share, WOPR, targets/g, touches/g.
- WR/TE: targets, catches, catch %, yards, TDs, air yards, aDOT, unrealized air yards (air yards on all targets
  minus the air yards he actually caught = air yards - (receiving yards - YAC)), YAC, YAC/catch, YAC over expected,
  separation, cushion, RACR, first downs, drops, broken tackles, red-zone / end-zone / deep (20+) targets.
- RB: everything above for his receiving work plus carries, rushing yards, YPC, TDs, yards before contact and after
  contact (totals and per carry), broken tackles, rush yards over expected per carry, 8+ man box %, red-zone and
  goal-line (inside the 5) carries, rushing first downs.
- QB: completions/attempts, comp %, yards, YPA, TDs, INTs, sacks, air yards, intended air yards per throw,
  YAC on his completions, CPOE, pressure %, bad-throw %, drops by his receivers, time to throw, aggressiveness,
  passing first downs, plus his rushing (carries, yards, TDs, yards before/after contact).
- Route tree: every target's depth (behind the line, 0-9, 10-19, 20+ air yards) and side (left, middle, right)
  from the play-by-play, drawn as routes fanning out from the line of scrimmage; line width = targets. Real route
  types (slant, go, out...) are not public for this season (nflverse participation data stops at 2024), so the
  tree shows where his targets went, not the route called. QBs get the same tree for their throws.
- Game log: one row per week.

Data: data/players/espn_players.json (fantasy points, projections, owner), usage.json, fp_week*.json, fp_ros.json,
adv.json (fetch_players.advanced) and nfl_schedule.json. Players: everyone with a game through week W.
"""
import html, json, os, re

esc = html.escape
POS = ["QB", "RB", "WR", "TE"]


def norm(n):
    n = n.lower().replace("’", "'")
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", n)
    return re.sub(r"[^a-z]", "", n)


TEAMFIX = {"LA": "LAR", "WAS": "WSH", "JAC": "JAX", "LVR": "LV"}


def _load(name):
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "players", name)
    return json.load(open(p)) if os.path.exists(p) else None


def r1(x, n=1):
    return None if x is None else round(x, n)


def section(d, W, short, own_team):
    import strength as S
    S.ros_values(d)
    rawp = S.raw_proj(W)
    adv = _load("adv.json") or []
    sch = _load("nfl_schedule.json") or {}
    T = sch.get("teams", {}); byes = sch.get("byes", {})
    A = {}
    for a in adv:
        k = norm(a["name"]) + "|" + a["pos"]
        if k in A and d.by.get(k) and d.by[k]["team"] != TEAMFIX.get(a["team"], a["team"]):
            continue
        A[k] = a
    # positional finish each completed week (same rule as Rankings vs. Actuals)
    graded = [w for w in d.final if w <= W and d.fp.get(w)]
    finish = {}
    for w in graded:
        for pos in POS:
            ps = sorted([p for p in d.P if p["pos"] == pos and w in p["act"]], key=lambda p: -p["act"][w]["pts"])
            for i, p in enumerate(ps, 1):
                finish[(w, p["key"])] = i
    # PPR/g rank at the position, 2+ games (the old Current Data order)
    prk = {}
    for pos in POS:
        for i, p in enumerate(sorted([p for p in d.P if p["pos"] == pos and p["g"] >= 2], key=lambda p: -p["ppg"]), 1):
            prk[p["key"]] = i
    nxt = W + 1
    rows = []
    for p in d.P:
        g = [w for w in d.games(p) if w <= W]
        if not g:
            continue
        a = A.get(p["key"], {"wk": {}})
        aw = {int(k): v for k, v in a["wk"].items() if int(k) <= W}
        tot, tree = _agg(aw, list(aw))
        u = d.use.get(p["key"], {})
        wopr = [u[w].get("wopr") for w in g if w in u and u[w].get("wopr") is not None]
        # weekly log: [week, opp, PPR, consensus proj, consensus pos rank, finish, line]
        log = []
        for w in range(1, W + 1):
            o = (T.get(p["team"], {}).get(str(w)) or {})
            opp = (("" if o.get("home") else "@") + o["opp"]) if o.get("opp") else ("BYE" if w in byes.get(p["team"], []) else "")
            e = d.ecr.get(p["key"], {}).get(w) if w in graded else None
            rk = int(re.sub(r"\D", "", e.get("pos_rank") or "") or 0) if e else 0
            pj = float(e["r2p_pts"]) if e and e.get("r2p_pts") not in (None, "") else None
            if w in g:
                v = aw.get(w, {}); act = p["act"][w]
                log.append([w, opp, r1(act["pts"]), r1(pj), rk or None, finish.get((w, p["key"])) if w in graded else None,
                            _line(p["pos"], v, act)])
            else:
                log.append([w, opp, None, r1(pj), rk or None, None, None])
        # one view per week played: that game's stats, trees and usage (user, 2026-10-26: week tabs)
        wv = {}
        for w in g:
            wt, wtr = _agg(aw, [w]) if w in aw else ({}, {})
            act = p["act"][w]
            for k, ek in (("tg", "tgt"), ("rec", "rec"), ("ry", "re_yds"), ("rtd", "re_td"), ("car", "ru_att"), ("uy", "ru_yds"),
                          ("utd", "ru_td"), ("att", "pa_att"), ("cmp", "pa_cmp"), ("py", "pa_yds"), ("ptd", "pa_td"), ("int", "pa_int")):
                if k not in wt and act.get(ek):
                    wt[k] = act[ek]
            uw = u.get(w, {})
            wv[str(w)] = {"t": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in wt.items() if v},
                          "tr": wtr.get("tree", {}), "ptr": wtr.get("ptree", {}),
                          "u": [r1(uw["snap"] * 100, 0) if uw.get("snap") is not None else None,
                                r1(uw["ts"] * 100, 1) if uw.get("ts") is not None else None,
                                r1(uw["ays"] * 100, 1) if uw.get("ays") is not None else None,
                                r1(uw.get("wopr"), 2), act.get("tgt") or 0, (act.get("ru_att") or 0) + (act.get("rec") or 0)]}
        gr = [x for x in log if x[2] is not None and x[4] and x[5]]
        gp = [x for x in log if x[2] is not None and x[3] is not None and x[0] in graded]
        bp = S.proj_for(d, p, nxt, rawp)
        if nxt in byes.get(p["team"], []) or p.get("inj") in ("OUT", "INJURY_RESERVE"):
            bp = 0.0
        on = T.get(p["team"], {}).get(str(nxt)) or {}
        ros = d.ros_by.get(p["key"]) or {}
        rows.append({
            "k": p["key"], "n": p["name"], "pos": p["pos"], "tm": p["team"], "o": p.get("owner") or 0,
            "inj": p.get("inj", "ACTIVE"), "g": len(g), "bye": (byes.get(p["team"]) or [0])[0],
            "ppg": r1(p["ppg"]), "l3": r1(p["l3"]), "tot": r1(sum(p["act"][w]["pts"] for w in g)),
            "xp": r1(p.get("xp")), "prk": prk.get(p["key"]), "np": r1(bp),
            "nopp": ((("" if on.get("home") else "@") + on["opp"]) if on.get("opp") else "BYE"),
            "rr": ros.get("pos_rank"), "ro": ros.get("rank_ecr"), "ros": r1(p.get("ros")),
            "u": [r1(p["snap"] * 100, 0) if p["snap"] is not None else None, r1(p["ts"] * 100, 1) if p["ts"] is not None else None,
                  r1(p["ays"] * 100, 1) if p["ays"] is not None else None, r1(sum(wopr) / len(wopr), 2) if wopr else None,
                  r1(p["tgt_g"]), r1(p["tch_g"])],
            "t": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in tot.items() if v},
            "tr": tree.get("tree", {}), "ptr": tree.get("ptree", {}),
            "gr": [len(gr), r1(sum(x[4] for x in gr) / len(gr), 1) if gr else None, r1(sum(x[5] for x in gr) / len(gr), 1) if gr else None,
                   r1(sum(x[4] - x[5] for x in gr) / len(gr), 1) if gr else None,
                   r1(sum(x[2] - x[3] for x in gp) / len(gp), 1) if gp else None],
            "lg": log, "wk": wv,
        })
    if not rows:
        return ""
    rows.sort(key=lambda r: (r["o"] == 0, r["o"], POS.index(r["pos"]), -(r["ros"] or 0)))
    mine = [r for r in rows if r["o"] == own_team]
    default = max(mine, key=lambda r: r["ros"] or 0)["k"] if mine else rows[0]["k"]
    data = {"W": W, "nx": nxt, "own": own_team, "teams": {str(k): v for k, v in short.items()}, "p": rows, "def": default,
            "graded": graded}
    body = (f'<div class="lk" id="lk"><div class="lk-ctl"><label class="lk-find"><span class="kicker">Type a player</span>'
            f'<input type="search" id="lk-q" placeholder="e.g. Amon-Ra St. Brown" autocomplete="off" spellcheck="false" aria-controls="lk-sug" aria-autocomplete="list"></label>'
            f'<div class="lk-sug" id="lk-sug" role="listbox" hidden></div>'
            f'<div class="lk-mine" id="lk-mine"></div></div>'
            f'<div class="lk-card" id="lk-card" aria-live="polite"></div></div>'
            f'<script type="application/json" id="lk-data">{json.dumps(data, separators=(",", ":")).replace("</", "<\\/")}</script>'
            f'<p class="note-s">{len(rows)} players: everyone with a game through week {W}. PPR rank = points per game among players at his position with 2+ games. '
            f'Graded weeks: the consensus rank before the week → where he actually finished at his position; vs proj = PPR points minus the consensus projection. '
            f'Unrealized air yards = air yards on all his targets minus the air yards on the balls he caught. Yards before/after contact, broken tackles, drops, bad throws and pressures are charted by PFR; '
            f'separation, YAC over expected, rush yards over expected, 8+ box %, time to throw and aggressiveness are Next Gen Stats (only weeks over their minimums count). '
            f'The route tree shows where his targets went (depth and side of every target); the route actually run isn\'t public for this season.</p>')
    return (f'<section class="sec" id="ps-lookup"><div class="sec-head"><h2>Player Lookup</h2><span class="kicker">Every number on one player · weeks 1–{W}</span></div>{body}</section>')


RATE_T = ("sep", "cush", "yacx", "iay")            # NGS receiving, weighted by targets
RATE_C = ("box8", "eff", "ttl")                     # NGS rushing, weighted by carries
RATE_A = ("ttt", "aggr", "qiay", "xcmp", "cpoe")    # passing, weighted by attempts
SKIP = ("ts", "ays", "wopr", "repa", "uepa", "pepa")


def _agg(aw, weeks):
    """Totals over the given weeks: counting stats summed, rate stats weighted, target/throw trees merged."""
    tot, tree, wsum = {}, {}, {}
    for w in weeks:
        v = aw.get(w, {})
        for k, x in v.items():
            if k in ("tree", "ptree"):
                for z, t in x.items():
                    c = tree.setdefault(k, {}).setdefault(z, [0, 0, 0])
                    for i in range(3):
                        c[i] += t[i]
            elif k in RATE_T + RATE_C + RATE_A:
                wt = (v.get("tg") if k in RATE_T else v.get("car") if k in RATE_C else v.get("att")) or 1
                wsum.setdefault(k, [0, 0]); wsum[k][0] += x * wt; wsum[k][1] += wt
            elif k == "ryoe":  # NGS rush yards over expected: only carries in weeks with an NGS row count
                tot["ryoe"] = tot.get("ryoe", 0) + x; tot["ryoe_c"] = tot.get("ryoe_c", 0) + (v.get("car", 0) or 0)
            elif isinstance(x, (int, float)) and k not in SKIP:
                tot[k] = tot.get(k, 0) + x
    for k, (s_, n_) in wsum.items():
        tot[k] = s_ / n_ if n_ else None
    return tot, tree


def _line(pos, v, act):
    """Compact game-log stats for one week."""
    g = lambda k: v.get(k, 0) or 0
    if pos == "QB":
        return [int(g("cmp") or act.get("pa_cmp", 0)), int(g("att") or act.get("pa_att", 0)), int(g("py") or act.get("pa_yds", 0)),
                int(g("ptd") or act.get("pa_td", 0)), int(g("int") or act.get("pa_int", 0)), int(g("car")), int(g("uy")), int(g("utd"))]
    if pos == "RB":
        return [int(g("car") or act.get("ru_att", 0)), int(g("uy") or act.get("ru_yds", 0)), int(g("ybc")), int(g("yaco")),
                int(g("tg") or act.get("tgt", 0)), int(g("rec") or act.get("rec", 0)), int(g("ry") or act.get("re_yds", 0)), int(g("utd") + g("rtd"))]
    return [int(g("tg") or act.get("tgt", 0)), int(g("rec") or act.get("rec", 0)), int(g("ry") or act.get("re_yds", 0)), int(g("ay")),
            int(g("yac")), int(g("rtd") or act.get("re_td", 0)), round((v.get("ts") or 0) * 100)]


SCRIPT = r"""<script>
(function(){
  var src=document.getElementById('lk-data');if(!src)return;
  var D=JSON.parse(src.textContent),P=D.p,T=D.teams,byk={};P.forEach(function(p){byk[p.k]=p});
  var q=document.getElementById('lk-q'),sug=document.getElementById('lk-sug'),card=document.getElementById('lk-card'),mine=document.getElementById('lk-mine');
  function e(s){return String(s==null?'':s).replace(/[&<>"]/g,function(m){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]})}
  function f(x,n){return x==null||isNaN(x)?'–':(+x).toFixed(n==null?1:n)}
  function pc(x,n){return x==null?'–':(+x).toFixed(n==null?0:n)+'%'}
  function i0(x){return x==null?'–':Math.round(x).toLocaleString()}
  function fold(s){return s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/[^a-z ]/g,'')}
  P.forEach(function(p){p._s=fold(p.n)});
  function owner(p){return p.o?'<span class="own"><i class="lg lg-'+p.o+' lg-sm"></i><em>'+e(T[p.o]||'')+'</em></span>':'<span class="own fa">FA</span>'}
  // ---- search ----
  var hits=[],sel=-1;
  function find(t){
    t=fold(t).trim();if(!t)return [];
    var a=[],b=[];
    P.forEach(function(p){var i=p._s.indexOf(t);if(i===0||p._s.indexOf(' '+t)>=0)a.push(p);else if(i>0)b.push(p)});
    var by=function(x,y){return (y.ppg||0)-(x.ppg||0)};
    return a.sort(by).concat(b.sort(by)).slice(0,8);
  }
  function drawSug(){
    if(!hits.length){sug.hidden=true;sug.innerHTML='';return}
    sug.innerHTML=hits.map(function(p,i){return '<button type="button" role="option" class="lk-opt'+(i===sel?' on':'')+'" data-k="'+e(p.k)+'" aria-selected="'+(i===sel)+'">'+
      '<b>'+e(p.n)+'</b><small>'+e(p.pos)+' · '+e(p.tm)+'</small>'+owner(p)+'<span class="num">'+f(p.ppg)+'</span></button>'}).join('');
    sug.hidden=false;
  }
  q.addEventListener('input',function(){hits=find(q.value);sel=hits.length?0:-1;drawSug()});
  q.addEventListener('keydown',function(ev){
    if(ev.key==='ArrowDown'&&hits.length){sel=(sel+1)%hits.length;drawSug();ev.preventDefault()}
    else if(ev.key==='ArrowUp'&&hits.length){sel=(sel-1+hits.length)%hits.length;drawSug();ev.preventDefault()}
    else if(ev.key==='Enter'){if(hits[sel]){pick(hits[sel].k)}ev.preventDefault()}
    else if(ev.key==='Escape'){hits=[];drawSug()}
  });
  sug.addEventListener('mousedown',function(ev){ev.preventDefault()});
  sug.addEventListener('click',function(ev){var b=ev.target.closest('.lk-opt');if(b)pick(b.dataset.k)});
  q.addEventListener('blur',function(){setTimeout(function(){hits=[];drawSug()},150)});
  function pick(k){var p=byk[k];if(!p)return;q.value=p.n;hits=[];drawSug();show(p);q.blur();
    mine.querySelectorAll('button').forEach(function(b){b.classList.toggle('on',b.dataset.k===k)})}
  // quick picks: the owner's team
  var own=P.filter(function(p){return p.o===D.own}).sort(function(a,b){return (b.ros||0)-(a.ros||0)});
  if(own.length){mine.innerHTML='<span class="kicker">'+e(T[D.own]||'Your team')+'</span>'+own.map(function(p){return '<button type="button" data-k="'+e(p.k)+'">'+e(p.n.replace(/ (Jr\.?|Sr\.?|II|III|IV|V)$/,'').split(' ').slice(-1)[0])+' <small>'+e(p.pos)+'</small></button>'}).join('');
    mine.addEventListener('click',function(ev){var b=ev.target.closest('button');if(b)pick(b.dataset.k)})}
  // ---- pieces ----
  var VIEW='S',DV=1,CUR=null;
  function n(x){x=x||0;return DV===1?i0(x):f(x/DV)}
  function tile(lbl,val,sub,cls){return '<div class="lk-t'+(cls?' '+cls:'')+'"><em>'+lbl+'</em><b class="num">'+val+'</b>'+(sub?'<small>'+sub+'</small>':'')+'</div>'}
  function grid(title,items){return '<div class="lk-blk"><h4>'+title+(DV>1&&title!=='Usage'?' <small>per game</small>':'')+'</h4><div class="lk-g">'+items.map(function(x){return '<span'+(x[2]?' title="'+e(x[2])+'"':'')+'><em>'+x[0]+'</em><b class="num">'+x[1]+'</b></span>'}).join('')+'</div></div>'}
  var ZD={B:'Behind the line',S:'Short (0–9)',M:'Intermediate (10–19)',D:'Deep (20+)'},ZS={L:'left',M:'middle',R:'right'};
  function tree(tr,qb){
    var keys=Object.keys(tr);if(!keys.length)return '<p class="note-s">No targets charted yet.</p>';
    var mx=Math.max.apply(null,keys.map(function(z){return tr[z][0]})),tot=keys.reduce(function(s,z){return s+tr[z][0]},0);
    var X={L:42,M:120,R:198},Y={D:30,M:82,S:128,B:178},LOS=152,ox=120,oy=qb?206:LOS;
    var s='<svg viewBox="0 0 240 222" class="lk-tree" role="img" aria-label="'+(qb?'Where his throws went':'Where his targets went')+'">';
    s+='<rect x="2" y="4" width="236" height="214" rx="3" class="tf"/>';
    [[10,'20+'],[56,'10'],[104,'0']].forEach(function(r){s+='<line x1="2" x2="238" y1="'+r[0]+'" y2="'+r[0]+'" class="tg"/>'});
    s+='<line x1="80" x2="80" y1="4" y2="218" class="tg dash"/><line x1="160" x2="160" y1="4" y2="218" class="tg dash"/>';
    s+='<line x1="2" x2="238" y1="'+LOS+'" y2="'+LOS+'" class="los"/>';
    s+='<text x="236" y="20" class="tl" text-anchor="end">20+</text><text x="236" y="66" class="tl" text-anchor="end">10–19</text><text x="236" y="114" class="tl" text-anchor="end">0–9</text><text x="236" y="'+(LOS-4)+'" class="tl" text-anchor="end">LOS</text>';
    keys.sort(function(a,b){return tr[a][0]-tr[b][0]}).forEach(function(z){
      var t=tr[z],cx=X[z[1]],cy=Y[z[0]],w=1.4+6*t[0]/mx,op=.35+.65*t[0]/mx;
      // stem straight up, then break toward the zone (a route), or flat out for screens
      var sx=ox+(cx-ox)*.18,sy=z[0]==='B'?oy:Math.max(cy+(oy-cy)*.45,cy+14);
      var d=z[0]==='B'?'M'+ox+' '+oy+' Q'+(ox+(cx-ox)*.6)+' '+(oy+4)+' '+cx+' '+cy:'M'+ox+' '+oy+' L'+sx+' '+sy+' L'+cx+' '+cy;
      s+='<path d="'+d+'" class="rt" style="stroke-width:'+w.toFixed(1)+';opacity:'+op.toFixed(2)+'"><title>'+ZD[z[0]]+' '+ZS[z[1]]+': '+t[0]+(qb?' throws, ':' targets, ')+t[1]+' caught, '+t[2]+' yds</title></path>';
    });
    keys.forEach(function(z){var t=tr[z],cx=X[z[1]],cy=Y[z[0]];
      s+='<g class="rz"><circle cx="'+cx+'" cy="'+cy+'" r="11"/><text x="'+cx+'" y="'+(cy+3.5)+'" text-anchor="middle"'+(DV>1?' style="font-size:8px"':'')+'>'+(DV===1?t[0]:(t[0]/DV).toFixed(1))+'</text><title>'+ZD[z[0]]+' '+ZS[z[1]]+': '+t[0]+(qb?' throws, ':' targets, ')+t[1]+' caught, '+t[2]+' yds</title></g>'});
    s+='<circle cx="'+ox+'" cy="'+oy+'" r="4.5" class="org"/>';
    s+='</svg>';
    // share by depth
    var dep={B:0,S:0,M:0,D:0},cat={B:0,S:0,M:0,D:0};keys.forEach(function(z){dep[z[0]]+=tr[z][0];cat[z[0]]+=tr[z][1]});
    var bars=['D','M','S','B'].map(function(k){return '<span><em>'+{D:'Deep 20+',M:'10–19',S:'0–9',B:'Behind'}[k]+'</em><i style="width:'+(tot?dep[k]/tot*100:0).toFixed(0)+'%"></i><b class="num">'+(DV===1?dep[k]:(dep[k]/DV).toFixed(1))+'<small> · '+(dep[k]?Math.round(cat[k]/dep[k]*100)+'%':'–')+'</small></b></span>'}).join('');
    return '<div class="lk-treew">'+s+'<div class="lk-dep"><div class="kicker">'+(qb?'Throws':'Targets')+(DV>1?' per game':'')+' by depth · catch rate</div>'+bars+'</div></div>';
  }
  function weeks(p){
    var L=p.lg,mx=Math.max.apply(null,L.map(function(x){return Math.max(x[2]||0,x[3]||0)}).concat([10]));
    var h='<div class="lk-wk" style="--n:'+L.length+'">';
    L.forEach(function(x){
      var hasPts=x[2]!=null,beat=hasPts&&x[3]!=null?x[2]-x[3]:null;
      h+='<button type="button" class="lk-w'+(String(VIEW)===String(x[0])?' sel':'')+'" data-v="'+x[0]+'" aria-label="Week '+x[0]+'"><div class="lk-bar">'+(hasPts?'<i class="'+(beat==null?'':beat>=0?'up':'dn')+'" style="height:'+(x[2]/mx*100).toFixed(1)+'%"><b class="num">'+f(x[2])+'</b></i>':'<span class="lk-dnp">'+(x[1]==='BYE'?'bye':'–')+'</span>')+
        (x[3]!=null?'<u style="bottom:'+(x[3]/mx*100).toFixed(1)+'%" title="Consensus projection '+f(x[3])+'"></u>':'')+'</div>'+
        '<span class="lk-wl">W'+x[0]+'<small>'+e(x[1]||'')+'</small></span>'+
        '<span class="lk-rf num">'+(x[4]&&x[5]?p.pos+x[4]+'→'+p.pos+x[5]:x[4]&&hasPts?p.pos+x[4]+'→?':'')+'</span>'+
        '<span class="lk-vp num '+(beat==null?'':beat>=0?'up':'dn')+'">'+(beat==null?'':(beat>0?'+':'')+beat.toFixed(1))+'</span></button>';
    });
    return h+'</div>';
  }
  function glog(p){
    var H={QB:['Cmp/Att','Pass yds','TD','INT','Rush','Rush yds','Rush TD'],RB:['Carries','Rush yds','YBC','YAC','Tgt','Rec','Rec yds','TD'],WR:['Tgt','Rec','Yds','Air yds','YAC','TD','Tgt share'],TE:['Tgt','Rec','Yds','Air yds','YAC','TD','Tgt share']}[p.pos];
    var rows=p.lg.filter(function(x){return x[6]}).map(function(x){var l=x[6],c;
      if(p.pos==='QB')c=[l[0]+'/'+l[1],l[2],l[3],l[4],l[5],l[6],l[7]];
      else if(p.pos==='RB')c=l;
      else c=l.slice(0,6).concat([l[6]+'%']);
      return '<tr><td>W'+x[0]+'</td><td>'+e(x[1])+'</td><td class="n"><b>'+f(x[2])+'</b></td><td class="n">'+f(x[3])+'</td>'+c.map(function(v){return '<td class="n">'+v+'</td>'}).join('')+'</tr>'}).join('');
    return '<details class="lk-log"><summary>Game log</summary><div class="tbl-wrap"><table class="lk-gl"><thead><tr><th>Wk</th><th>Opp</th><th class="n">PPR</th><th class="n">Proj</th>'+H.map(function(x){return '<th class="n">'+x+'</th>'}).join('')+'</tr></thead><tbody>'+rows+'</tbody></table></div></details>';
  }
  function receiving(p,t,full){
    var tg=t.tg||0,rec=t.rec||0,ry=t.ry||0,ay=t.ay||0,yac=t.yac||0,real=ry-yac,unr=ay-real;
    var it=[['Targets',n(tg)],['Catches',n(rec)],['Catch %',tg?pc(rec/tg*100):'–'],['Rec yards',n(ry)],['Rec TD',n(t.rtd||0)],
      ['Air yards',n(ay),'Air yards on every target'],['aDOT',tg?f(ay/tg):'–','Average depth of target'],['Unrealized air yds',n(unr),'Air yards on targets he didn\'t turn into catch yardage: air yards − (rec yards − YAC)'],
      ['YAC',n(yac),'Yards after the catch'],['YAC / catch',rec?f(yac/rec):'–'],['YAC over exp.',t.yacx==null?'–':(t.yacx>0?'+':'')+f(t.yacx),'Next Gen Stats, per catch'],
      ['Separation',t.sep==null?'–':f(t.sep)+' yd','Next Gen Stats: yards from the nearest defender at the catch or incompletion'],['Cushion',t.cush==null?'–':f(t.cush)+' yd'],
      ['RACR',ay>0?f(ry/ay,2):'–','Receiving yards per air yard'],['1st downs',n(t.rfd||0)],['Drops',n(t.drp||0)],['Broken tackles',n(t.rbrk||0)],
      ['Red-zone tgts',n(t.rzt||0)],['End-zone tgts',n(t.ezt||0)],['Deep tgts 20+',n(t.dpt||0)]];
    if(!full)it=[it[0],it[1],it[2],it[3],it[4],it[6],it[8],it[9],it[17]];
    return grid(full?'Receiving':'Receiving work',it);
  }
  function show(p){
    CUR=p;var inj=(p.inj&&p.inj!=='ACTIVE'&&p.inj!=='NORMAL')?' <span class="inj">'+e(p.inj.replace('_',' ').toLowerCase())+'</span>':'';
    var wkv=(VIEW!=='S'&&VIEW!=='A')?p.wk[VIEW]:null;
    var isW=VIEW!=='S'&&VIEW!=='A',lw=isW?p.lg[VIEW-1]:null;
    var t=isW?(wkv?wkv.t:{}):p.t,g=p.g,u=isW?(wkv?wkv.u:[null,null,null,null,0,0]):p.u;
    DV=VIEW==='A'?g:1;
    var lp=p.l3-p.ppg,ar=lp>1?'▲':lp<-1?'▼':'•',ac=lp>1?'up':lp<-1?'dn':'';
    var big=isW?(lw&&lw[2]!=null?'<b class="num">'+f(lw[2])+'</b><span>PPR · week '+VIEW+'<br><em>'+e(lw[1]||'')+'</em></span>':'<b class="num">–</b><span>week '+VIEW+'<br><em>'+(lw&&lw[1]==='BYE'?'bye':'did not play')+'</em></span>')
      :'<b class="num">'+f(p.ppg)+'</b><span>PPR / game<br><em>'+(p.prk?p.pos+p.prk+' at the position':'fewer than 2 games')+'</em></span>';
    var h='<div class="lk-head"><div><span class="kicker">'+e(p.pos)+' · '+e(p.tm)+' · '+g+' game'+(g===1?'':'s')+(p.bye?' · bye wk '+p.bye:'')+'</span>'+
      '<h3>'+e(p.n)+inj+'</h3>'+owner(p)+'</div><div class="lk-big">'+big+'</div></div>';
    // view tabs: whole season, per-game average, each week
    h+='<div class="lk-views" role="group" aria-label="Which weeks"><button type="button" class="pt" data-v="S" aria-pressed="'+(VIEW==='S')+'">Season</button><button type="button" class="pt" data-v="A" aria-pressed="'+(VIEW==='A')+'">Average</button>'+
      p.lg.map(function(x){var played=!!p.wk[x[0]];return '<button type="button" class="pt'+(played?'':' nog')+'" data-v="'+x[0]+'" aria-pressed="'+(String(VIEW)===String(x[0]))+'" title="'+(played?'Week '+x[0]+' '+e(x[1]||''):x[1]==='BYE'?'Bye':'No game')+'">Wk '+x[0]+'</button>'}).join('')+'</div>';
    if(isW){
      var beat=lw&&lw[2]!=null&&lw[3]!=null?lw[2]-lw[3]:null;
      h+='<div class="lk-tiles">'+tile('Week '+VIEW+' PPR',lw&&lw[2]!=null?f(lw[2]):'–',lw&&lw[1]?e(lw[1]==='BYE'?'bye week':lw[1]):'')+
        tile('Projected',lw&&lw[3]!=null?f(lw[3]):'–','consensus, before the week')+
        tile('vs projection',beat==null?'–':(beat>0?'+':'')+f(beat),beat==null?'':beat>=0?'beat it':'missed it',beat==null?'':beat>=0?'up':'dn')+
        tile('Ranked',lw&&lw[4]?p.pos+lw[4]:'–','consensus before the week')+
        tile('Finished',lw&&lw[5]?p.pos+lw[5]:'–','at his position',lw&&lw[4]&&lw[5]?(lw[5]<=lw[4]?'up':'dn'):'')+'</div>';
    } else {
      h+='<div class="lk-tiles">'+tile('Last 3','<span class="'+ac+'">'+f(p.l3)+' '+ar+'</span>','vs '+f(p.ppg)+' season')+
        (VIEW==='A'?tile('PPR / game',f(p.ppg),p.prk?p.pos+p.prk+' at the position':''):tile('Total PPR',f(p.tot),'weeks 1–'+D.W))+
        tile('Expected',f(p.xp),p.xp==null?'needs 3 games':((p.ppg-p.xp>=0?'+':'')+f(p.ppg-p.xp)+' vs volume'),p.xp!=null&&p.ppg-p.xp>=0?'up':p.xp!=null?'dn':'')+
        tile('Week '+D.nx+' proj',f(p.np),e(p.nopp))+
        tile('Rest of season',e(p.rr||'–'),p.ro?'overall '+p.ro+(p.ros?' · '+f(p.ros)+'/g':''):'unranked')+'</div>';
    }
    // graded weeks
    var G=p.gr;
    h+='<div class="lk-blk"><h4>Week by week · graded</h4>'+weeks(p)+
      '<div class="lk-gs">'+(G[0]?'<span><em>Graded weeks</em><b class="num">'+G[0]+'</b></span><span><em>Avg rank</em><b class="num">'+p.pos+Math.round(G[1])+'</b></span><span><em>Avg finish</em><b class="num">'+p.pos+Math.round(G[2])+'</b></span>'+
        '<span><em>Spots vs rank</em><b class="num '+(G[3]>=0?'up':'dn')+'">'+(G[3]>0?'+':'')+f(G[3])+'</b></span>':'<span><em>Graded weeks</em><b class="num">0</b></span>')+
        '<span><em>Pts vs proj</em><b class="num '+(G[4]==null?'':G[4]>=0?'up':'dn')+'">'+(G[4]==null?'–':(G[4]>0?'+':'')+f(G[4]))+'</b></span></div>'+
      '<div class="lk-key"><span><i class="k-up"></i>Beat projection</span><span><i class="k-dn"></i>Missed</span><span><i class="k-pj"></i>Consensus projection</span><span>WR12→WR5 = ranked → finished</span></div></div>';
    // usage
    var played=!isW||!!wkv;
    if(!played){h+='<p class="lk-none">'+(lw&&lw[1]==='BYE'?'Bye week: no game.':'He didn\'t play in week '+VIEW+'.')+'</p>';card.innerHTML=h;return}
    var gl=isW?['Opponent',e(lw[1]||'')]:['Games',g];
    if(p.pos==='QB')h+=grid('Usage',[gl,['Snap %',pc(u[0])],[isW?'Pass att':'Pass att / g',isW?n(t.att):f((t.att||0)/g)],[isW?'Dropbacks':'Dropbacks / g',isW?n((t.att||0)+(t.sk||0)):f(((t.att||0)+(t.sk||0))/g)],[isW?'Carries':'Carries / g',isW?n(t.car):f((t.car||0)/g)]]);
    else h+=grid('Usage',[gl,['Snap %',pc(u[0])],['Target share',pc(u[1],1)],['Air-yd share',p.pos==='RB'||p.pos==='QB'?'–':pc(u[2],1)],['WOPR',u[3]==null?'–':f(u[3],2),'Weighted opportunity: 1.5 × target share + 0.7 × air-yards share'],[isW?'Targets':'Targets / g',isW?n(u[4]):f(u[4])],[isW?'Touches':'Touches / g',isW?n(u[5]):f(u[5])]]);
    var c=t.car||0;
    if(p.pos==='RB'){
      h+=grid('Rushing',[['Carries',n(c)],['Rush yards',n(t.uy||0)],['YPC',c?f((t.uy||0)/c):'–'],['Rush TD',n(t.utd||0)],
        ['Yds before contact',n(t.ybc||0),'PFR charting'],['YBC / carry',c&&t.ybc!=null?f((t.ybc||0)/c):'–'],['Yds after contact',n(t.yaco||0),'PFR charting'],['YAC / carry',c?f((t.yaco||0)/c):'–'],
        ['Broken tackles',n((t.brk||0)+(t.rbrk||0)),'Rushing and receiving'],['RYOE / carry',t.ryoe_c?((t.ryoe/t.ryoe_c>0?'+':'')+f(t.ryoe/t.ryoe_c)):'–','Next Gen Stats rush yards over expected'],
        ['8+ in box',t.box8==null?'–':pc(t.box8),'Share of carries against 8+ defenders (NGS)'],['Red-zone carries',n(t.rzc||0)],['Goal-line carries',n(t.glc||0),'Inside the 5'],['Rush 1st downs',n(t.ufd||0)],['Fumbles lost',n(t.fl||0)]]);
      h+=receiving(p,t,false);
    } else if(p.pos==='QB'){
      var at=t.att||0,cm=t.cmp||0;
      h+=grid('Passing',[['Cmp / Att',n(cm)+'/'+n(at)],['Comp %',at?pc(cm/at*100,1):'–'],['Pass yards',n(t.py||0)],['YPA',at?f((t.py||0)/at):'–'],['Pass TD',n(t.ptd||0)],['INT',n(t.int||0)],
        ['Sacks',n(t.sk||0)],['Air yards',n(t.pay||0),'Air yards on all his throws'],['Intended air / att',t.qiay==null?'–':f(t.qiay),'NGS average intended air yards'],['YAC on his throws',n(t.pyac||0)],
        ['CPOE',t.cpoe==null?'–':(t.cpoe>0?'+':'')+f(t.cpoe),'Completion % over expected'],['Pressure %',at?pc((t.prs||0)/(at+(t.sk||0))*100):'–','PFR: pressured on dropbacks'],
        ['Bad-throw %',at?pc((t.bad||0)/at*100,1):'–','PFR charting'],['Drops by receivers',n(t.pdrp||0)],['Time to throw',t.ttt==null?'–':f(t.ttt,2)+'s','NGS'],
        ['Aggressiveness',t.aggr==null?'–':pc(t.aggr),'NGS: throws into tight windows'],['Pass 1st downs',n(t.pfd||0)],['Fumbles lost',n(t.fl||0)]]);
      h+=grid('Rushing',[['Carries',n(c)],['Rush yards',n(t.uy||0)],['YPC',c?f((t.uy||0)/c):'–'],['Rush TD',n(t.utd||0)],['Yds before contact',n(t.ybc||0)],['Yds after contact',n(t.yaco||0)],['Red-zone carries',n(t.rzc||0)]]);
    } else {
      h+=receiving(p,t,true);
      if(c)h+=grid('Rushing',[['Carries',n(c)],['Rush yards',n(t.uy||0)],['Rush TD',n(t.utd||0)],['Yds after contact',n(t.yaco||0)]]);
    }
    var tr=isW?(p.pos==='QB'?wkv.ptr:wkv.tr):(p.pos==='QB'?p.ptr:p.tr);
    h+='<div class="lk-blk"><h4>'+(p.pos==='QB'?'Passing tree':'Route tree')+' <small>'+(p.pos==='QB'?'where his throws went':'where his targets went')+' · '+(isW?'week '+VIEW:VIEW==='A'?'per game, weeks 1–'+D.W:'weeks 1–'+D.W)+'</small></h4>'+tree(tr,p.pos==='QB')+'</div>';
    if(!isW)h+=glog(p);
    card.innerHTML=h;
  }
  card.addEventListener('click',function(ev){var b=ev.target.closest('[data-v]');if(!b||!CUR)return;
    var v=b.dataset.v;VIEW=(v==='S'||v==='A')?v:+v;show(CUR);
    var nb=card.querySelector('.lk-views [data-v="'+v+'"]');if(nb)nb.focus({preventScroll:true});});
  pick(D.def);q.value='';
})();
</script>"""

CSS = r"""
/* player lookup */
.lk{display:grid;gap:16px}
.lk-ctl{position:relative;display:grid;gap:10px}
.lk-find{display:grid;gap:4px;max-width:460px}
.lk-find input{font:inherit;font-size:1.05rem;padding:10px 12px;border:2px solid var(--rule);background:var(--sheet);color:var(--ink);width:100%}
.lk-find input:focus{outline:3px solid var(--hi);outline-offset:1px}
.lk-sug{position:absolute;z-index:8;top:66px;left:0;width:min(460px,100%);background:var(--sheet);border:2px solid var(--rule);box-shadow:4px 4px 0 var(--rule);display:grid}
.lk-sug[hidden]{display:none}
.lk-opt{appearance:none;background:none;border:0;border-bottom:1px solid var(--line);font:inherit;color:inherit;text-align:left;cursor:pointer;display:grid;grid-template-columns:minmax(0,1fr) auto auto;grid-template-rows:auto auto;column-gap:10px;padding:7px 10px;align-items:center}
.lk-opt b{grid-column:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lk-opt small{grid-column:1;font-family:var(--mono);font-size:.62rem;color:var(--muted)}
.lk-opt .own{grid-column:2;grid-row:1/span 2}.lk-opt .own em{display:none}
.lk-opt .num{grid-column:3;grid-row:1/span 2;font-size:.9rem}
.lk-opt.on,.lk-opt:hover{background:var(--paper)}
.lk-mine{display:flex;flex-wrap:wrap;gap:4px;align-items:center}
.lk-mine .kicker{margin-right:4px}
.lk-mine button{appearance:none;font:inherit;font-size:.78rem;padding:3px 8px;border:1.5px solid var(--rule);background:var(--sheet);color:var(--ink);cursor:pointer}
.lk-mine button small{font-family:var(--mono);font-size:.56rem;color:var(--muted)}
.lk-mine button.on{background:var(--ink);color:var(--sheet)}.lk-mine button.on small{color:var(--silver)}
.lk-card{display:grid;gap:18px;border:3px solid var(--rule);border-top:10px solid var(--honolulu);padding:18px;background:var(--sheet);min-width:0}
.lk-head{display:flex;justify-content:space-between;align-items:end;gap:14px;flex-wrap:wrap}
.lk-head>div:first-child{display:grid;gap:6px}
.lk-head h3{font-size:clamp(2rem,6vw,3.2rem);font-weight:900;text-transform:uppercase;line-height:.95}
.lk-head h3 .inj{font-size:.8rem;vertical-align:.5em}
.lk-big{display:flex;align-items:center;gap:10px}
.lk-big b{font-size:3.4rem;line-height:1;color:var(--blue)}
.lk-big span{font-family:var(--mono);font-size:.68rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.lk-big em{font-style:normal;color:var(--ink);text-transform:none;letter-spacing:0;font-size:.78rem}
.lk-tiles{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}
.lk-t{display:grid;gap:2px;padding:10px 12px;background:var(--paper);border-left:4px solid var(--honolulu)}
.lk-t em{font-style:normal;font-family:var(--mono);font-size:.58rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.lk-t b{font-size:1.45rem;line-height:1.1}
.lk-t small{font-size:.72rem;color:var(--muted)}
.lk-t.up{border-left-color:var(--blue)}.lk-t.dn{border-left-color:var(--red)}
.lk-blk{display:grid;gap:10px;min-width:0}
.lk-blk h4{font-family:var(--display);font-size:1.35rem;font-weight:800;text-transform:uppercase;border-bottom:2px solid var(--rule);padding-bottom:4px}
.lk-blk h4 small{font-family:var(--mono);font-size:.62rem;font-weight:400;letter-spacing:.06em;color:var(--muted);text-transform:uppercase;margin-left:6px}
.lk-g{display:grid;grid-template-columns:repeat(auto-fill,minmax(118px,1fr));gap:1px;padding:1px}
.lk-g span{display:grid;gap:1px;padding:7px 9px;background:var(--sheet);box-shadow:0 0 0 1px var(--line)}
.lk-g span[title]{cursor:help}
.lk-g em{font-style:normal;font-family:var(--mono);font-size:.56rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lk-g span[title] em{text-decoration:underline dotted;text-underline-offset:2px}
.lk-g b{font-size:1.02rem}
/* week / season / average switch */
.lk-views{display:flex;flex-wrap:wrap;gap:4px;border-bottom:2px solid var(--rule);padding-bottom:10px}
.lk-views .pt{padding:5px 10px}
.lk-views .pt.nog{opacity:.5;text-decoration:line-through}
.lk-views .pt[aria-pressed="true"]{background:var(--honolulu);border-color:var(--honolulu);color:#fff;opacity:1}
.lk-none{font-family:var(--display);font-size:1.6rem;font-weight:800;text-transform:uppercase;color:var(--muted)}
/* week by week */
.lk-wk{display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:6px;align-items:end}
.lk-w{appearance:none;background:none;border:0;padding:2px 0;font:inherit;color:inherit;cursor:pointer;display:grid;gap:2px;text-align:center;min-width:0}
.lk-w:hover .lk-bar{background-color:var(--paper)}
.lk-w.sel{outline:2px solid var(--honolulu);outline-offset:1px}
.lk-w:focus-visible{outline:3px solid var(--hi)}
.lk-bar{position:relative;height:120px;background:linear-gradient(var(--line) 1px,transparent 1px) 0 0/100% 25%;border-bottom:2px solid var(--rule)}
.lk-bar i{position:absolute;left:14%;right:14%;bottom:0;background:var(--silver);display:block}
.lk-bar i.up{background:var(--blue)}.lk-bar i.dn{background:var(--red)}
.lk-bar i b{position:absolute;left:50%;transform:translateX(-50%);top:-17px;font-size:.72rem;white-space:nowrap}
.lk-bar u{position:absolute;left:4%;right:4%;height:0;border-top:3px solid var(--hi);text-decoration:none}
.lk-dnp{position:absolute;bottom:4px;left:0;right:0;font-family:var(--mono);font-size:.62rem;color:var(--muted);text-transform:uppercase}
.lk-wl{font-family:var(--mono);font-size:.7rem;font-weight:600;display:grid}
.lk-wl small{font-weight:400;font-size:.58rem;color:var(--muted)}
.lk-rf{font-size:.62rem;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lk-vp{font-size:.7rem;font-weight:600;min-height:1em}
.lk-gs{display:flex;flex-wrap:wrap;gap:6px 22px;padding-top:4px}
.lk-gs span{display:grid}
.lk-gs em{font-style:normal;font-family:var(--mono);font-size:.56rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.lk-gs b{font-size:1.1rem}
.lk-key{display:flex;flex-wrap:wrap;gap:4px 14px;font-family:var(--mono);font-size:.62rem;color:var(--muted)}
.lk-key span{display:inline-flex;align-items:center;gap:5px}
.lk-key i{display:inline-block;width:10px;height:10px}
.lk-key .k-up{background:var(--blue)}.lk-key .k-dn{background:var(--red)}.lk-key .k-pj{height:0;border-top:3px solid var(--hi)}
/* route tree */
.lk-treew{display:grid;grid-template-columns:minmax(0,300px) minmax(0,1fr);gap:20px;align-items:center}
.lk-tree{width:100%;height:auto;display:block}
.lk-tree .tf{fill:color-mix(in srgb,var(--honolulu) 7%,var(--sheet));stroke:var(--rule);stroke-width:1.5}
.lk-tree .tg{stroke:var(--line);stroke-width:1}.lk-tree .tg.dash{stroke-dasharray:3 4}
.lk-tree .los{stroke:var(--honolulu);stroke-width:2}
.lk-tree .tl{font-family:var(--mono);font-size:7.5px;fill:var(--muted)}
.lk-tree .rt{fill:none;stroke:var(--blue);stroke-linecap:round;stroke-linejoin:round}
.lk-tree .rz circle{fill:var(--sheet);stroke:var(--ink);stroke-width:1.5}
.lk-tree .rz text{font-family:var(--mono);font-size:9.5px;font-weight:600;fill:var(--ink)}
.lk-tree .org{fill:var(--ink)}
.lk-dep{display:grid;gap:8px;max-width:460px}
.lk-dep span{display:grid;grid-template-columns:72px minmax(0,1fr) 84px;align-items:center;gap:8px}
.lk-dep em{font-style:normal;font-family:var(--mono);font-size:.62rem;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
.lk-dep i{display:block;height:10px;background:var(--blue);min-width:2px}
.lk-dep b{font-size:.9rem}.lk-dep b small{font-size:.66rem;color:var(--muted);font-weight:400}
/* game log */
.lk-log summary{cursor:pointer;font-family:var(--display);font-size:1.15rem;font-weight:800;text-transform:uppercase}
.lk-log .tbl-wrap{overflow-x:auto;margin-top:8px}
table.lk-gl{min-width:560px;font-size:.84rem}
table.lk-gl td,table.lk-gl th{padding:5px 6px;white-space:nowrap}
@media (max-width:760px){
  .lk-card{padding:12px;border-width:2px;border-top-width:8px}
  .lk-tiles{grid-template-columns:repeat(2,minmax(0,1fr))}
  .lk-tiles .lk-t:last-child{grid-column:1/-1}
  .lk-views .pt{padding:5px 7px;font-size:.66rem;flex:1 0 auto}
  .lk-big b{font-size:2.6rem}
  .lk-g{grid-template-columns:repeat(3,minmax(0,1fr))}
  .lk-g span{padding:6px 7px}.lk-g b{font-size:.92rem}
  .lk-g em{white-space:normal;line-height:1.15}
  .lk-bar{height:96px}
  .lk-wk{gap:3px}
  .lk-rf{font-size:.5rem}
  .lk-treew{grid-template-columns:minmax(0,1fr)}
  .lk-tree{max-width:300px;margin:0 auto}
  table.lk-gl{display:table!important;min-width:520px}
  table.lk-gl thead{position:static!important;width:auto!important;height:auto!important;clip:auto!important}
  table.lk-gl tr{display:table-row!important;padding:0!important}
  table.lk-gl td{display:table-cell!important;background:none!important}
  table.lk-gl td::before{display:none!important}
  .lk-log .tbl-wrap{overflow-x:auto!important}
}
"""
