"""The Daily Fantasizer: tap-to-explain abbreviations and a Top button that stays put (user, 2026-10-26).

BLOCK sits at the very end of template.html (between <!--gloss--> and <!--/gloss-->), so every new edition has it.
`python3 glossary.py FILE...` puts the same block into already-built pages (idempotent: an older copy is replaced).

1. Abbreviations: every abbreviation in the page's text (PPR, YAC, aDOT, WOPR, RYOE, ROS, FA, D/ST, NFL team codes,
   position ranks like WR12...) gets a dotted underline; tapping or clicking it opens a small bubble that spells it
   out. Stat labels in Player Lookup that carry an explanation (title) open the same bubble on tap. Text that is
   re-drawn later (Player Lookup, Start/Sit, Face-Off...) is picked up by a MutationObserver. Buttons, inputs,
   selects, links, SVG and big headlines are left alone.
2. Top button (phones): it stays in the bottom-right corner of what you see. With the page zoomed or panned sideways
   (the usual reason a fixed button drifts on iPhones) it is pinned to the visual viewport; otherwise plain CSS
   fixed positioning with the safe-area inset. Also: no sideways panning on browsers without overflow-x: clip.
"""
import sys

BLOCK = r"""<!--gloss-->
<style>
abbr.ac{text-decoration:underline dotted;text-decoration-thickness:1px;text-underline-offset:2px;cursor:help;-webkit-tap-highlight-color:transparent}
abbr.ac:hover{text-decoration-style:solid}
.gl-tip{position:absolute;z-index:60;max-width:min(280px,calc(100vw - 24px));background:var(--ink,#151a24);color:var(--sheet,#fff);font:500 .82rem/1.35 var(--body,system-ui);padding:8px 10px;border-radius:3px;box-shadow:0 4px 14px rgba(0,0,0,.28);pointer-events:none}
.gl-tip b{font-family:var(--mono,monospace);font-size:.74rem;letter-spacing:.04em;display:block;margin-bottom:2px;color:var(--hi,#f2d23c)}
.gl-tip[hidden]{display:none}
@supports not (overflow:clip){@media (max-width:760px),(pointer:coarse) and (max-width:1100px){html,body{overflow-x:hidden}}}
@media (max-width:760px),(pointer:coarse) and (max-width:1100px){
  .m-top{right:calc(14px + env(safe-area-inset-right,0px))!important;bottom:calc(18px + env(safe-area-inset-bottom,0px))!important}
  .m-top.pinned{right:auto!important;bottom:auto!important;transform-origin:0 0}
}
</style>
<script>
(function(){
  // ---- Top button: keep it in the bottom-right corner of the screen ----
  var top=document.querySelector('.m-top'),vv=window.visualViewport;
  if(top&&vv){
    var raf=0;
    function pin(){raf=0;
      var zoomed=Math.abs(vv.scale-1)>0.01||vv.offsetLeft>0.5||Math.abs(document.documentElement.clientWidth-vv.width)>1;
      if(!zoomed){top.classList.remove('pinned');top.style.left=top.style.top=top.style.transform='';return}
      var s=1/vv.scale,w=40*s;
      top.classList.add('pinned');
      top.style.left=(vv.offsetLeft+vv.width-14*s-w)+'px';
      top.style.top=(vv.offsetTop+vv.height-18*s-w)+'px';
      top.style.transform='scale('+s+')';
    }
    function q(){if(!raf)raf=requestAnimationFrame(pin)}
    vv.addEventListener('resize',q);vv.addEventListener('scroll',q);addEventListener('scroll',q,{passive:true});q();
  }
  // ---- abbreviations: tap to see what they mean ----
  var G={"PPR":"Points per reception: 1 fantasy point for every catch",
    "ROS":"Rest of season","FA":"Free agent: on nobody's roster in our league","D/ST":"Defense / special teams","FLEX":"Flex spot: a running back, wide receiver or tight end",
    "QB":"Quarterback","RB":"Running back","WR":"Wide receiver","TE":"Tight end","K":"Kicker",
    "IR":"Injured reserve","MVP":"Most valuable player","TD":"Touchdown","TDs":"Touchdowns","INT":"Interception","INTs":"Interceptions",
    "YAC":"Yards after catch (on runs: yards after contact)","YBC":"Yards before contact: rushing yards gained before a defender touches him",
    "aDOT":"Average depth of target: how far downfield, on average, his targets are thrown (air yards per target)",
    "RACR":"Receiver air conversion ratio: receiving yards per air yard thrown his way",
    "WOPR":"Weighted opportunity rating: 1.5 × target share + 0.7 × air-yards share",
    "RYOE":"Rush yards over expected (Next Gen Stats): yards gained beyond what blocking and defenders predicted",
    "CPOE":"Completion percentage over expected: completions beyond what the throw difficulty predicted",
    "YPC":"Yards per carry","YPA":"Yards per pass attempt","LOS":"Line of scrimmage","NGS":"Next Gen Stats: the NFL's player-tracking data",
    "PFR":"Pro Football Reference: charts yards before/after contact, broken tackles, drops, pressures","ECR":"Expert consensus ranking",
    "ESPN":"ESPN, the league's host and one of the projection sources","NFL":"National Football League","PF":"Points for","PA":"Points against",
    "Tgt":"Targets: passes thrown his way","Tgts":"Targets: passes thrown his way","Proj":"Projected points",
    "Opp":"Opponent","Yds":"Yards","Wk":"Week","Wks":"Weeks",
    "ARI":"Arizona Cardinals","ATL":"Atlanta Falcons","BAL":"Baltimore Ravens","BUF":"Buffalo Bills","CAR":"Carolina Panthers","CHI":"Chicago Bears",
    "CIN":"Cincinnati Bengals","CLE":"Cleveland Browns","DAL":"Dallas Cowboys","DEN":"Denver Broncos","DET":"Detroit Lions","GB":"Green Bay Packers",
    "HOU":"Houston Texans","IND":"Indianapolis Colts","JAX":"Jacksonville Jaguars","KC":"Kansas City Chiefs","LV":"Las Vegas Raiders",
    "LAC":"Los Angeles Chargers","LAR":"Los Angeles Rams","LA":"Los Angeles Rams","MIA":"Miami Dolphins","MIN":"Minnesota Vikings","NE":"New England Patriots",
    "NO":"New Orleans Saints","NYG":"New York Giants","NYJ":"New York Jets","PHI":"Philadelphia Eagles","PIT":"Pittsburgh Steelers","SF":"San Francisco 49ers",
    "SEA":"Seattle Seahawks","TB":"Tampa Bay Buccaneers","TEN":"Tennessee Titans","WSH":"Washington Commanders","WAS":"Washington Commanders"};
  var POSN={QB:'quarterback',RB:'running back',WR:'wide receiver',TE:'tight end',K:'kicker'};
  var TEAMS=/^(ARI|ATL|BAL|BUF|CAR|CHI|CIN|CLE|DAL|DEN|DET|GB|HOU|IND|JAX|KC|LV|LAC|LAR|LA|MIA|MIN|NE|NO|NYG|NYJ|PHI|PIT|SF|SEA|TB|TEN|WSH|WAS)$/;
  var keys=Object.keys(G).sort(function(a,b){return b.length-a.length}).map(function(k){return k.replace(/[\/]/g,'\\/')});
  var RX=new RegExp('(^|[^A-Za-z0-9/])((?:QB|RB|WR|TE)\\d{1,3}|'+keys.join('|')+')(?![A-Za-z0-9])','g');
  var SKIP='script,style,svg,button,select,option,input,textarea,a,abbr,label.vs-find,h1,.masthead,.lk-head h3,.pn b,.gl-tip,[contenteditable],.tabs,.lk-views,.vd,.lk-lc';
  function mean(t){var m=/^(QB|RB|WR|TE)(\d+)$/.exec(t);if(m)return 'No. '+m[2]+' '+POSN[m[1]]+' (rank at the position)';return G[t]}
  function walk(root){
    if(!root||root.nodeType!==1||(root.closest&&root.closest(SKIP)))return;
    var tw=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode:function(n){
      if(!n.nodeValue||n.nodeValue.length<2||!/[A-Z]/.test(n.nodeValue))return NodeFilter.FILTER_REJECT;
      var p=n.parentElement;return p&&!p.closest(SKIP)?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_REJECT}});
    var list=[],n;while((n=tw.nextNode()))list.push(n);
    list.forEach(function(t){
      var s=t.nodeValue,out=null,last=0,m;RX.lastIndex=0;
      while((m=RX.exec(s))){
        var w=m[2];
        // team codes only stand alone (opponent cells, "DET" under a name), not inside sentences like "NO way"
        if(TEAMS.test(w)&&!/^\s*@?\s*$/.test(s.replace(w,'').replace(/[·,@vs.()\-–—]/g,'')))continue;
        if(!mean(w))continue;
        out=out||document.createDocumentFragment();
        var st=m.index+m[1].length;
        out.appendChild(document.createTextNode(s.slice(last,st)));
        var a=document.createElement('abbr');a.className='ac';a.title=mean(w);a.textContent=w;a.tabIndex=0;out.appendChild(a);
        last=st+w.length;
      }
      if(out){out.appendChild(document.createTextNode(s.slice(last)));t.parentNode.replaceChild(out,t)}
    });
  }
  var tip=document.createElement('div');tip.className='gl-tip';tip.hidden=true;tip.setAttribute('role','tooltip');document.body.appendChild(tip);
  var cur=null;
  function show(el,word,text){
    cur=el;tip.innerHTML='<b></b><span></span>';tip.firstChild.textContent=word;tip.lastChild.textContent=text;tip.hidden=false;
    var r=el.getBoundingClientRect(),tw=tip.offsetWidth,th=tip.offsetHeight,x=r.left+r.width/2-tw/2+scrollX,y=r.top+scrollY-th-8;
    x=Math.max(scrollX+12,Math.min(x,scrollX+document.documentElement.clientWidth-tw-12));
    if(r.top-th-8<0)y=r.bottom+scrollY+8;
    tip.style.left=x+'px';tip.style.top=y+'px';
  }
  function hide(){tip.hidden=true;cur=null}
  document.addEventListener('click',function(ev){
    var a=ev.target.closest&&ev.target.closest('abbr.ac');
    var lab=!a&&ev.target.closest&&ev.target.closest('.lk-g span[title]');
    if(a){ev.preventDefault();if(cur===a)return hide();show(a,a.textContent,a.title);return}
    if(lab){if(cur===lab)return hide();var em=lab.querySelector('em');show(lab,em?em.textContent:'',lab.title);return}
    if(cur)hide();
  },true);
  document.addEventListener('keydown',function(ev){var a=document.activeElement;
    if((ev.key==='Enter'||ev.key===' ')&&a&&a.matches&&a.matches('abbr.ac')){ev.preventDefault();a.click()}
    if(ev.key==='Escape')hide()});
  addEventListener('scroll',function(){if(cur)hide()},{passive:true});
  addEventListener('resize',function(){if(cur)hide()});
  // whole page once (in slices so the page stays responsive), then anything re-drawn later
  var secs=[].slice.call(document.querySelectorAll('section,.sec,main,.page>div'));
  if(!secs.length)secs=[document.body];
  var idle=window.requestIdleCallback||function(f){return setTimeout(f,30)};
  (function step(){var s=secs.shift();if(s)walk(s);if(secs.length)idle(step);else walk(document.body)})();
  var pend=[],tm=0;
  new MutationObserver(function(ms){ms.forEach(function(m){m.addedNodes.forEach(function(x){if(x.nodeType===1&&!x.closest('abbr.ac,.gl-tip'))pend.push(x)})});
    if(!tm)tm=setTimeout(function(){tm=0;var p=pend;pend=[];p.forEach(function(x){if(x.isConnected)walk(x)})},60)})
    .observe(document.body,{childList:true,subtree:true});
})();
</script>
<!--/gloss-->"""


def inject(html):
    a, b = html.find("<!--gloss-->"), html.find("<!--/gloss-->")
    if a >= 0 and b > a:
        return html[:a] + BLOCK + html[b + len("<!--/gloss-->"):]
    i = html.rfind("</body>")
    return html[:i] + BLOCK + "\n" + html[i:] if i >= 0 else html + "\n" + BLOCK + "\n"


if __name__ == "__main__":
    for f in sys.argv[1:]:
        s = open(f, encoding="utf-8").read()
        open(f, "w", encoding="utf-8").write(inject(s))
        print("glossary in", f)
