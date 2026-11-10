"""The Daily Fantasizer: a Print button at the bottom of This Week's Paper (user, 2026-11-10).

Tapping it downloads the paper tab as an old-time newspaper PDF (daily-fantasizer-weekN.pdf): masthead with ears
and dateline, a banner headline (the first biggest-news story), three justified Times columns with column rules,
drop caps, agate-type box scores with dot leaders, section heads between rules, "-30-" at the end, and a
cream paper texture. The PDF is written in the browser from what is on the paper tab (no libraries, no network,
works offline and on the members-only site), so every edition and every league gets it automatically.
Graphics-only blocks (Roster Radar, the Matchup radar, hero strips) are left out; their numbers appear as text.

render.py puts `block(season, week)` where template.html has <!--PRINT--> (after the League & Teams link card).
The dateline is the Tuesday the edition comes out: Labor Day + 8 days + 7 x (week - 1), so renders stay reproducible.
"""
import datetime

WIDTHS = {"R":[250,333,408,500,500,833,778,180,333,333,500,564,250,333,250,278,500,500,500,500,500,500,500,500,500,500,278,278,564,564,564,444,921,722,667,667,722,611,556,722,722,333,389,722,611,889,722,722,556,722,667,556,611,722,722,944,722,722,611,333,278,333,469,500,333,444,500,444,500,444,333,500,500,278,278,500,278,778,500,500,500,500,333,389,278,500,500,722,500,500,444,480,200,480,541,350,500,350,333,500,444,1000,500,500,333,1000,556,333,889,350,611,350,350,333,333,444,444,350,500,1000,333,980,389,333,722,350,444,722,250,333,500,500,500,500,200,500,333,760,276,500,564,333,760,333,400,564,300,300,333,500,453,250,333,300,310,500,750,750,750,444,722,722,722,722,722,722,889,667,611,611,611,611,333,333,333,333,722,722,722,722,722,722,722,564,722,722,722,722,722,722,556,500,444,444,444,444,444,444,667,444,444,444,444,444,278,278,278,278,500,500,500,500,500,500,500,564,500,500,500,500,500,500,500,500],"B":[250,333,555,500,500,1000,833,278,333,333,500,570,250,333,250,278,500,500,500,500,500,500,500,500,500,500,333,333,570,570,570,500,930,722,667,722,722,667,611,778,778,389,500,778,667,944,722,778,611,778,722,556,667,722,722,1000,722,722,667,333,278,333,581,500,333,500,556,444,556,444,333,500,556,278,333,556,278,833,556,500,556,556,444,389,333,556,500,722,500,500,444,394,220,394,520,350,500,350,333,500,500,1000,500,500,333,1000,556,333,1000,350,667,350,350,333,333,500,500,350,500,1000,333,1000,389,333,722,350,444,722,250,333,500,500,500,500,220,500,333,747,300,500,570,333,747,333,400,570,300,300,333,556,540,250,333,300,330,500,750,750,750,500,722,722,722,722,722,722,1000,722,667,667,667,667,389,389,389,389,722,722,778,778,778,778,778,570,778,722,722,722,722,722,611,556,500,500,500,500,500,500,722,444,444,444,444,444,278,278,278,278,500,556,500,500,500,500,500,570,500,556,556,556,556,500,556,500],"I":[250,333,420,500,500,833,778,214,333,333,500,675,250,333,250,278,500,500,500,500,500,500,500,500,500,500,333,333,675,675,675,500,920,611,611,667,722,611,611,722,722,333,444,667,556,833,667,722,611,722,611,500,556,722,611,833,611,556,556,389,278,389,422,500,333,500,500,444,500,444,278,500,500,278,278,444,278,722,500,500,500,500,389,389,278,500,444,667,444,444,389,400,275,400,541,350,500,350,333,500,556,889,500,500,333,1000,500,333,944,350,556,350,350,333,333,556,556,350,500,889,333,980,389,333,667,350,389,556,250,389,500,500,500,500,275,500,333,760,276,500,675,333,760,333,400,675,300,300,333,500,523,250,333,300,310,500,750,750,750,500,611,611,611,611,611,611,889,667,611,611,611,611,333,333,333,333,722,667,722,722,722,722,722,675,722,722,722,722,722,556,611,500,500,500,500,500,500,500,667,444,444,444,444,444,278,278,278,278,500,500,500,500,500,500,500,675,500,500,500,500,500,444,500,444],"X":[250,389,555,500,500,833,778,278,333,333,500,570,250,333,250,278,500,500,500,500,500,500,500,500,500,500,333,333,570,570,570,500,832,667,667,667,722,667,667,722,778,389,500,667,611,889,722,722,611,722,667,556,611,722,667,889,667,611,611,333,278,333,570,500,333,500,500,444,500,444,333,500,556,278,278,500,278,778,556,500,500,500,389,389,278,556,444,667,500,444,389,348,220,348,570,350,500,350,333,500,500,1000,500,500,333,1000,556,333,944,350,611,350,350,333,333,500,500,350,500,1000,333,1000,389,333,722,350,389,611,250,389,500,500,500,500,220,500,333,747,266,500,606,333,747,333,400,570,300,300,333,576,500,250,333,300,300,500,750,750,750,500,667,667,667,667,667,667,944,667,667,667,667,667,389,389,389,389,722,722,722,722,722,722,722,570,722,722,722,722,722,611,611,500,500,500,500,500,500,500,722,444,444,444,444,444,278,278,278,278,500,556,500,500,500,500,500,570,500,556,556,556,556,444,500,444]}  # Adobe AFM widths for the four standard Times fonts, WinAnsi codes 32-255

CSS = """<style>
.print-ed{display:flex;justify-content:center;margin:22px 0 6px}
.print-btn{font-family:var(--mono);font-size:.86rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;padding:11px 30px;background:var(--sheet);color:var(--ink);border:3px solid var(--rule);box-shadow:4px 4px 0 var(--blue);cursor:pointer;-webkit-tap-highlight-color:transparent}
.print-btn:hover{background:var(--ink);color:var(--sheet)}
.print-btn:active{transform:translate(2px,2px);box-shadow:2px 2px 0 var(--blue)}
.print-btn:disabled{opacity:.6;cursor:progress}
@media print{.print-ed{display:none}}
</style>"""

JS = r"""(function(){
var btn=document.getElementById('pe-btn');if(!btn)return;
var FW=/*WIDTHS*/;
var FN={R:'/F1',B:'/F2',I:'/F3',X:'/F4'};
var WIN={8364:128,8218:130,402:131,8222:132,8230:133,8224:134,8225:135,710:136,8240:137,352:138,8249:139,338:140,381:142,8216:145,8217:146,8220:147,8221:148,8226:149,8211:150,8212:151,732:152,8482:153,353:154,8250:155,339:156,382:158,376:159};
var SUB={8722:'\x96',8209:'-',8208:'-',8201:' ',8239:' ',8203:'',8644:'<>',8594:'->',8592:'<-',8599:'+',8600:'-',9650:'+',9660:'-',10003:'',9733:'*',9734:'*',8805:'>=',8804:'<=',8776:'~'};
function enc(s){var o='';s=String(s||'');for(var i=0;i<s.length;i++){var c=s.codePointAt(i);if(c>65535)i++;
  if(c>=32&&c<127)o+=s[i];else if(c>=160&&c<256)o+=String.fromCharCode(c);else if(WIN[c])o+=String.fromCharCode(WIN[c]);
  else if(SUB[c]!=null)o+=SUB[c];else if(c===9||c===10||c===13)o+=' ';}
  return o.replace(/ +/g,' ').trim();}
function tw(s,f,z,cs){var t=0;for(var i=0;i<s.length;i++){var c=s.charCodeAt(i);t+=(c>=32&&c<256)?FW[f][c-32]:500;}return t*z/1000+(cs||0)*s.length;}
function pe(s){return s.replace(/\\/g,'\\\\').replace(/\(/g,'\\(').replace(/\)/g,'\\)');}
function n2(v){return (Math.round(v*100)/100).toFixed(2);}
function up(s){return s.toUpperCase().replace(/\xDF/g,'SS');}
function T(el){return el?el.textContent.replace(/\s+/g,' ').trim():'';}
function q(r,s){return r?r.querySelector(s):null;}
function qa(r,s){return r?Array.prototype.slice.call(r.querySelectorAll(s)):[];}
function own(el){if(!el)return'';var t='';for(var i=0;i<el.childNodes.length;i++){var k=el.childNodes[i];if(k.nodeType===3)t+=k.textContent;}return t.replace(/\s+/g,' ').trim();}

// ---------- page geometry: US Letter, three columns ----------
var PW=612,PH=792,M=36,COLS=3,GUT=15,CW=(PW-2*M-GUT*(COLS-1))/COLS,FOOT=M+18;
var INK='0.13 0.11 0.09',PAPER='0.957 0.925 0.851';
var BODY={f:'R',z:8.8,l:10.7};

function txt(o,f,z,x,y,s,cs,ws){o.push('BT '+FN[f]+' '+z+' Tf '+(cs||0).toFixed(2)+' Tc '+(ws||0).toFixed(3)+' Tw '+x.toFixed(2)+' '+y.toFixed(2)+' Td ('+pe(s)+') Tj ET');}
function hl(o,x1,x2,y,w){o.push(w.toFixed(2)+' w '+x1.toFixed(2)+' '+y.toFixed(2)+' m '+x2.toFixed(2)+' '+y.toFixed(2)+' l S');}
function vl(o,x,y1,y2,w){o.push(w.toFixed(2)+' w '+x.toFixed(2)+' '+y1.toFixed(2)+' m '+x.toFixed(2)+' '+y2.toFixed(2)+' l S');}
function base(top,z,l){return top-(l-z)/2-z*0.78;}
function fit(s,f,z,w,cs){if(tw(s,f,z,cs)<=w)return s;while(s.length>1&&tw(s+'...',f,z,cs)>w)s=s.slice(0,-1);return s.replace(/\s+$/,'')+'...';}

// ---------- line builders (every block becomes a list of lines that flow down the columns) ----------
function words(s,f,z,w){var out=[];s.split(' ').forEach(function(x){if(!x)return;while(tw(x,f,z)>w&&x.length>1){var k=x.length-1;while(k>1&&tw(x.slice(0,k)+'-',f,z)>w)k--;out.push(x.slice(0,k)+'-');x=x.slice(k);}out.push(x);});return out;}
function wrap(s,f,z,wf,cs){var ws=words(s,f,z,wf(0)),lines=[],cur='';
  ws.forEach(function(x){var t=cur?cur+' '+x:x;if(!cur||tw(t,f,z,cs)<=wf(lines.length))cur=t;else{lines.push(cur);cur=x;}});
  if(cur)lines.push(cur);return lines;}
function para(raw,o){o=o||{};var s=enc(raw);if(!s)return[];var f=o.f||BODY.f,z=o.z||BODY.z,l=o.l||BODY.l,ind=o.ind==null?9:o.ind,al=o.al||'j',L=[];
  var dc=null,dw=0,dz=0;
  if(o.drop&&s.length>40&&/[A-Za-z0-9]/.test(s[0])){dc=s[0];s=s.slice(1);dz=(2*l+0.662*z)/0.676;dw=tw(dc,'B',dz)+3;ind=0;}
  var wf=function(i){return CW-(dc&&i<3?dw:0)-(i===0?ind:0);};
  var ls=wrap(s,f,z,wf);
  ls.forEach(function(t,i){var last=i===ls.length-1;
    L.push({h:l,kn:!!(dc&&i<2),d:function(op,x,top,w){var off=(dc&&i<3?dw:0)+(i===0?ind:0),ww=w-off,b=base(top,z,l),nat=tw(t,f,z),ws=0;
      if(dc&&i===0)txt(op,'B',dz,x,base(top,z,l)-2*l,dc);
      var gaps=(t.match(/ /g)||[]).length;
      if(al==='j'&&!last&&gaps){ws=(ww-nat)/gaps;if(ws>z*0.7)ws=0;}
      var xx=al==='c'?x+(w-nat)/2:al==='r'?x+w-nat:x+off;
      txt(op,f,z,xx,b,t,0,ws);}});});
  return L;}
function center(raw,f,z,l,o){o=o||{};var s=enc(raw);if(o.caps)s=up(s);var cs=o.cs||0;if(!s)return[];
  var ls=wrap(s,f,z,function(){return CW-4;},cs);
  return ls.map(function(t,i){return {h:l,kn:o.kn!==false,d:function(op,x,top,w){var nat=tw(t,f,z,cs);txt(op,f,z,x+(w-nat)/2,base(top,z,l),t,cs);}};});}
function rule(kind,h){return {h:h||6,sp:true,d:function(op,x,top,w){var y=top-(h||6)/2;
  if(kind==='thin')hl(op,x,x+w,y,0.5);else if(kind==='thick')hl(op,x,x+w,y,1.6);
  else if(kind==='double'){hl(op,x,x+w,y+1.3,1.4);hl(op,x,x+w,y-1.2,0.4);}
  else if(kind==='short'){hl(op,x+w*0.36,x+w*0.64,y,0.6);}
  else if(kind==='orn'){hl(op,x+w*0.3,x+w*0.46,y,0.5);hl(op,x+w*0.54,x+w*0.7,y,0.5);op.push(INK+' rg '+(x+w/2).toFixed(2)+' '+(y+2.2).toFixed(2)+' m '+(x+w/2+2.2).toFixed(2)+' '+y.toFixed(2)+' l '+(x+w/2).toFixed(2)+' '+(y-2.2).toFixed(2)+' l '+(x+w/2-2.2).toFixed(2)+' '+y.toFixed(2)+' l f');}}};}
function gap(h){return {h:h,sp:true,d:function(){}};}
function agate(left,right,o){o=o||{};var f=o.f||'R',fr=o.fr||f,z=o.z||8,l=o.l||9.8,a=enc(left),b=enc(right);
  return {h:l,kn:!!o.kn,d:function(op,x,top,w){var y=base(top,z,l),wb=tw(b,fr,z),aa=fit(a,f,z,w-wb-8),wa=tw(aa,f,z);
    txt(op,f,z,x,y,aa);txt(op,fr,z,x+w-wb,y,b);
    var dots='',dw=tw('.','R',z)+1.2,n=Math.floor((w-wa-wb-6)/dw);if(n>1){for(var i=0;i<n;i++)dots+='.';txt(op,'R',z,x+w-wb-3-n*dw,y,dots,1.2);}}};}
function row3(a,m,b,o){o=o||{};var z=o.z||7.6,l=o.l||9.4;a=enc(a);m=enc(m);b=enc(b);
  return {h:l,d:function(op,x,top,w){var y=base(top,z,l),mw=26,side=(w-mw)/2-2;
    var fa=o.aw?'B':'R',fb=o.bw?'B':'R',aa=fit(a,fa,z,side),bb=fit(b,fb,z,side);
    txt(op,fa,z,x,y,aa);txt(op,'X',z,x+(w-tw(m,'X',z))/2,y,m);txt(op,fb,z,x+w-tw(bb,fb,z),y,bb);}};}
function head(raw,z){z=z||12.5;return center(raw,'B',z,z*1.08);}
function kick(raw){return center(raw,'R',6.6,8.6,{caps:true,cs:0.45});}
function deck(raw,z){z=z||8.6;return center(raw,'I',z,z*1.2);}
function secHead(title,sub){var L=[rule('thick',5),gap(2)].concat(center(title,'B',11,12.5,{caps:true,cs:0.9}));
  if(sub)L=L.concat(center(sub,'I',7.4,9));L.push(rule('thin',6));L.push(gap(2));
  L.forEach(function(x){x.kn=true;});return L;}
function endStory(){return [gap(3),rule('short',7),gap(3)];}
function bullets(arr){var L=[];arr.forEach(function(s){L=L.concat(para('• '+s,{f:'I',z:7.8,l:9.4,ind:0,al:'l'}));});return L;}

// ---------- read the paper tab ----------
function collect(){
  var P=document.getElementById('paper'),mast=document.querySelector('.mast'),C={stories:[]};
  var mk=qa(mast,'.mast-top > .kicker').map(T),ms=qa(mast,'.mast-sub span').map(T);
  C.official=mk[0]||'';C.vol=(mk[1]||'').split('·').slice(0,2).join('·').trim();
  C.edition=ms[0]||'';C.format=ms[1]||'';C.price=ms[2]||'';
  C.week=(C.edition.match(/\d+/)||[''])[0];C.date=btn.getAttribute('data-date')||'';
  var L=[],banner=null;
  // the biggest news: first card is the banner, the rest are front-page stories
  qa(P,'.ups-card').forEach(function(c,i){
    var st=qa(c,'.stamp').map(T).join(' · '),k=T(q(c,'.ups-top .kicker')),h=T(q(c,'.ups-h'));
    var W=q(c,'.ups-w'),Lo=q(c,'.ups-l'),body=[];
    if(i===0){banner={head:h,deck:(st?st+': ':'')+k};body=body.concat(kick(st?st+' · '+k:k));}
    else{body=body.concat(kick(st)).concat(head(h,11.5)).concat(deck(k,8));}
    body.push(gap(3));
    if(W&&Lo){body.push(agate(T(q(W,'.ups-n'))+' ('+T(q(W,'small'))+')',T(q(W,'b')),{fr:'B',kn:true}));
      body.push(agate(T(q(Lo,'.ups-n'))+' ('+T(q(Lo,'small'))+')',T(q(Lo,'b')),{kn:true}));
      body.push(agate('Margin',T(q(c,'.ups-m b')),{f:'I',kn:true}));body.push(gap(3));}
    qa(c,'p').forEach(function(p,j){body=body.concat(para(T(p),{drop:i===0&&j===0}));});
    var salt=qa(c,'.ups-salt span').map(T);if(salt.length){body.push(gap(2));body=body.concat(bullets(salt));}
    body=body.concat(endStory());L=L.concat(body);});
  var an=q(P,'.announce');
  if(an){L=L.concat(kick(T(q(an,'.kicker'))||'Announcements')).concat(head(T(q(an,'h3')),11.5));qa(an,'p').forEach(function(p){L=L.concat(para(T(p)));});L=L.concat(endStory());}
  // page one: hero score box + lead story
  var lead=q(P,'article.lead'),hero=q(P,'section.hero');
  if(lead){var lh=T(q(lead,'h2'));
    if(!banner)banner={head:lh,deck:T(q(lead,'.deck'))};
    else{L=L.concat(kick(T(q(lead,'.kicker'))||'Page one')).concat(head(lh,13)).concat(deck(T(q(lead,'.deck'))));}
    L.push(gap(3));
    if(hero){var sd=qa(hero,'.hero-top .side');if(sd.length===2){L.push(agate(T(q(sd[0],'.tname')),T(q(sd[0],'.score')),{fr:'B',kn:true}));
      L.push(agate(T(q(sd[1],'.tname')),T(q(sd[1],'.score')),{kn:true}));
      L.push(agate(T(q(hero,'.mid span'))||'Margin',T(q(hero,'.mid b')),{f:'I',kn:true}));L.push(gap(3));}}
    qa(lead,'p:not(.deck)').forEach(function(p,j){L=L.concat(para(T(p),{drop:j===0}));});L=L.concat(endStory());}
  // sidebar boxes
  qa(P,'.side-col .box').forEach(function(b){L.push(rule('double',6));L=L.concat(kick(T(q(b,'.kicker')))).concat(head(T(q(b,'h3')),11));L.push(gap(2));
    qa(b,'.minibars > div').forEach(function(r){var s=r.querySelectorAll('span');L.push(agate(T(s[0]),T(r.querySelector('.num'))));});
    L.push(gap(2));qa(b,'p').forEach(function(p){L=L.concat(para(T(p)));});L.push(gap(2));L.push(rule('double',6));L.push(gap(6));});
  // by the numbers
  var tiles=qa(P,'.tiles .tile');
  if(tiles.length){L=L.concat(secHead(q(P,'.tiles').getAttribute('aria-label')||'By the numbers'));
    tiles.forEach(function(t){var s=T(q(t,'.tile-s'));L.push(agate(T(q(t,'.tile-k'))+(s?' ('+s+')':''),T(q(t,'b'))));});L=L.concat(endStory());}
  // the scoreboard
  var g=document.getElementById('games');
  if(g){L=L.concat(secHead(T(q(g,'.sec-head h2')),T(q(g,'.sec-head .kicker'))));
    qa(g,'article.game').forEach(function(a,i){if(i)L.push(rule('short',8));
      L=L.concat(kick(T(q(a,'.g-head .kicker'))+' · by '+T(q(a,'.margin')).replace(/^\+/,'')));
      L=L.concat(head(T(q(a,'h3')),10.5));
      qa(a,'.gl-lane').forEach(function(ln,j){var v=q(ln,'.br-val');L.push(agate(T(q(ln,'.br-name'))+' ('+T(q(v,'em'))+')',own(v),{fr:j===0?'B':'R',kn:true,z:7.8}));});
      var fl=T(q(a,'.flag'));if(fl)L=L.concat(para(fl,{f:'I',z:7.8,l:9.4,ind:0,al:'c'}));
      qa(a,'p').forEach(function(p){L=L.concat(para(T(p)));});});
    L=L.concat(endStory());}
  // points by position
  var po=document.getElementById('positions');
  var prs=qa(po,'.pr').filter(function(r){return T(q(r,'.pr-v'));});
  if(po&&prs.length){L=L.concat(secHead(T(q(po,'.sec-head h2')),'Starters only · * best in the league'));
    prs.forEach(function(r){L.push(agate(T(q(r,'.br-name')),T(q(r,'.pr-v')),{fr:'B',kn:true}));
      var segs=qa(r,'.ps').map(function(s){var t=(s.getAttribute('data-tip')||'').split('·');return t.length>1?t[0].trim()+' '+t[1].replace(/pts/,'').trim()+(s.classList.contains('king')?'*':''):'';}).filter(Boolean);
      L=L.concat(para(segs.join(', '),{f:'R',z:7.2,l:8.6,ind:0,al:'l'}));L.push(gap(2));});
    L=L.concat(endStory());}
  // manager of the week
  var ho=q(P,'.honor');
  if(ho){L=L.concat(secHead(T(q(ho,'.kicker'))||'Manager of the week'));L=L.concat(head(T(q(ho,'h3')),12));
    var bg=q(ho,'.big');L=L.concat(deck(own(bg)+' '+T(q(bg,'small')),8.4));L.push(gap(3));qa(ho,'p').forEach(function(p){L=L.concat(para(T(p)));});L=L.concat(endStory());}
  // police blotter + missing persons
  var bl=document.getElementById('blotter');
  if(bl){var secs=qa(bl,'.sec');
    var b1=secs[0];if(b1&&qa(b1,'.case').length){L=L.concat(secHead(T(q(b1,'h2')),T(q(b1,'.sec-head .kicker'))));
      qa(b1,'.case').forEach(function(c,i){if(i)L.push(rule('short',8));L=L.concat(kick('Booking no. '+T(q(c,'.mug-no'))+' · '+T(q(c,'.kicker'))));L=L.concat(head(T(q(c,'h3')),10.5));qa(c,'p').forEach(function(p){L=L.concat(para(T(p)));});});
      L=L.concat(endStory());}
    var b2=q(bl,'.crime-side .sec');if(b2&&qa(b2,'.poster').length){L=L.concat(secHead(T(q(b2,'h2')),T(q(b2,'.sec-head .kicker'))));
      qa(b2,'.poster').forEach(function(c,i){if(i)L.push(rule('short',8));var nums=qa(c,'.pa .num').map(T);
        L=L.concat(kick(T(q(c,'.poster-top .kicker'))||'Missing'));L=L.concat(center(T(q(c,'h3')),'B',11,12.5,{caps:true,cs:0.6}));
        if(nums.length>1)L=L.concat(deck('Projected '+nums[0]+' · Found '+nums[1],8));qa(c,'p').forEach(function(p){L=L.concat(para(T(p),{al:'c',ind:0}));});});
      L=L.concat(endStory());}}
  // forecast
  var fc=document.getElementById('forecast');
  if(fc&&qa(fc,'.fc').length){L=L.concat(secHead(T(q(fc,'.sec-head h2')),T(q(fc,'.sec-head .kicker'))));
    qa(fc,'.fc').forEach(function(c){var t=qa(c,'.fc-vs b').map(T),sp=qa(c,'.fc-split .num').map(T),od=T(q(c,'.odds span'));
      L.push(agate((t[0]||'')+' '+T(q(c,'.fc-vs em'))+' vs. '+(t[1]||''),od,{fr:'I',kn:true}));
      var p=T(q(c,'p'));L=L.concat(para((sp.length>1?'Season avg '+sp[0]+' to '+sp[1]+'. ':'')+p,{f:'I',z:7.4,l:8.8,ind:0,al:'l'}));L.push(gap(2));});
    L=L.concat(endStory());}
  // matchup of the week
  var mw=document.getElementById('matchup');
  if(mw&&q(mw,'.mw-head')){L=L.concat(secHead(T(q(mw,'.sec-head h2')),T(q(mw,'.sec-head .kicker'))));
    var ta=T(q(mw,'.mw-ta b'))+' ('+T(q(mw,'.mw-ta small'))+')',tb=T(q(mw,'.mw-tb b'))+' ('+T(q(mw,'.mw-tb small'))+')';
    L=L.concat(head(ta+' vs. '+tb,11));L=L.concat(deck('Projected spread: '+T(q(mw,'.mw-mid b'))+' · '+T(q(mw,'.mw-mid small')),8));L.push(gap(3));
    var rows=qa(mw,'.mw-row');if(rows.length){L.push(row3(T(q(mw,'.mw-ta b')),'',T(q(mw,'.mw-tb b')),{aw:1,bw:1}));L.push(rule('thin',4));}
    rows.forEach(function(r){var a=q(r,'.mw-a'),b=q(r,'.mw-b');
      var sa=(T(q(a,'em'))+' '+T(q(a,'b'))).trim(),sb=(T(q(b,'b'))+' '+T(q(b,'em'))).trim();
      if(r.classList.contains('mw-tot'))L.push(rule('thin',4));
      L.push(row3(sa,T(q(r,'.mw-s')),sb,{aw:a&&a.classList.contains('win'),bw:b&&b.classList.contains('win')}));});
    var nt=T(q(mw,'.note-s'));if(nt){L.push(gap(3));L=L.concat(para(nt,{f:'I',z:7.2,l:8.6,ind:0}));}
    L=L.concat(endStory());}
  // the end mark
  L=L.concat([gap(4)]).concat(center('— 30 —','B',9,12,{kn:false}));
  C.banner=banner;C.lines=L;return C;}

// ---------- paper texture, masthead, running heads ----------
function rnd(seed){var s=seed>>>0;return function(){s=(s*1664525+1013904223)>>>0;return s/4294967296;};}
function texture(op,pg){var r=rnd(9001+pg*77);op.push(PAPER+' rg 0 0 '+PW+' '+PH+' re f');
  for(var i=0;i<26;i++){var g=(0.86+r()*0.07).toFixed(3);op.push(g+' '+(g*0.97).toFixed(3)+' '+(g*0.9).toFixed(3)+' rg '+(r()*PW).toFixed(1)+' '+(r()*PH).toFixed(1)+' '+(6+r()*30).toFixed(1)+' '+(0.4+r()*1.4).toFixed(1)+' re f');}
  for(var j=0;j<520;j++){var k=r(),c=(0.45+r()*0.35).toFixed(2),s=(0.25+k*0.7).toFixed(2);op.push(c+' '+c+' '+(c*0.92).toFixed(2)+' rg '+(r()*PW).toFixed(1)+' '+(r()*PH).toFixed(1)+' '+s+' '+s+' re f');}
  op.push(INK+' rg '+INK+' RG');}
function tri(op,y,z,l,a,b,c,fb){var w=PW-2*M,f='R',cs=0.6;a=up(enc(a));b=up(enc(b));c=up(enc(c));
  while(z>5&&tw(a,f,z,cs)+tw(b,fb||f,z,cs)+tw(c,f,z,cs)>w-24)z-=0.2;var yb=base(y,z,l);
  txt(op,f,z,M,yb,a,cs);txt(op,fb||f,z,M+(w-tw(b,fb||f,z,cs))/2,yb,b,cs);txt(op,f,z,PW-M-tw(c,f,z,cs),yb,c,cs);return y-l;}
function masthead(op,C){var y=PH-M,w=PW-2*M;
  y=tri(op,y,6.8,10,C.vol,C.official,C.edition);hl(op,M,PW-M,y-1,0.5);y-=4;
  var ear=104,eh=50,et=y-3;
  [[M,['“All the Scores','That Fit,','We Print.”'],'I'],[PW-M-ear,['LATE CITY EDITION','Week '+C.week+' · Final scores','Forecast: excuses, heavy'],'R']].forEach(function(e){
    op.push('0.6 w '+e[0].toFixed(2)+' '+(et-eh).toFixed(2)+' '+ear+' '+eh+' re S');
    e[1].forEach(function(s,i){s=enc(s);var f=(e[2]==='R'&&i===0)?'B':e[2],z=i===0?8:7.2;txt(op,f,z,e[0]+(ear-tw(s,f,z))/2,et-15-i*11.5,s);});});
  var title=enc('The Daily Fantasizer'),tz=Math.min(54,(w-2*ear-24)*1000/tw(title,'B',1000));
  txt(op,'B',tz,M+(w-tw(title,'B',tz))/2,et-eh/2-tz*0.33,title);
  y=et-eh-6;hl(op,M,PW-M,y,2);hl(op,M,PW-M,y-3,0.5);y-=5;
  y=tri(op,y,7,12,C.format,C.date,C.price,'B');hl(op,M,PW-M,y-1,0.5);hl(op,M,PW-M,y-4,1.6);return y-10;}
function runhead(op,C){var y=tri(op,PH-M,6.8,10,'The Daily Fantasizer',C.date,C.edition);hl(op,M,PW-M,y-1,0.5);hl(op,M,PW-M,y-3.5,1.4);return y-12;}
function footer(op,C,n){hl(op,M,PW-M,FOOT-6,0.5);var s=enc('— '+n+' —'),z=7.5,y=FOOT-15;
  txt(op,'R',z,M,y,up(enc(C.official)),0.5);txt(op,'B',z,M+(PW-2*M-tw(s,'B',z))/2,y,s);var r=up(enc(C.vol));txt(op,'R',z,PW-M-tw(r,'R',z,0.5),y,r,0.5);}
function banner(op,C,y){if(!C.banner)return y;var w=PW-2*M,h=up(enc(C.banner.head)),z=34,ls;
  for(;;){ls=wrap(h,'B',z,function(){return w;});if(ls.length<=2||z<=20)break;z-=1;}
  ls.forEach(function(t){y-=z*1.02;txt(op,'B',z,M+(w-tw(t,'B',z))/2,y+z*0.2,t);});
  var d=enc(C.banner.deck);if(d){var dz=11.5,dl=wrap(d,'I',dz,function(){return w*0.86;});y-=4;dl.forEach(function(t){y-=dz*1.25;txt(op,'I',dz,M+(w-tw(t,'I',dz))/2,y+dz*0.25,t);});}
  y-=6;hl(op,M+w*0.3,PW-M-w*0.3,y,0.6);return y-8;}

// ---------- flow the lines through the columns; the last page is balanced ----------
function need(L,i){var j=i,h=0;while(j<L.length&&L[j].kn){h+=L[j].h;j++;}for(var k=0;k<2&&j<L.length;k++,j++)h+=L[j].h;return h;}
function fill(L,s,top,bot,op){var col=0,y=top,i=s,low=[top,top,top],colH=top-bot;
  while(i<L.length){var x=L[i];
    if(y===top&&x.sp){i++;continue;}
    var nd=x.kn?Math.min(need(L,i),colH):x.h;
    if(y-nd<bot&&y<top){col++;if(col>=COLS)break;y=top;continue;}
    if(y-x.h<bot&&y===top&&x.h>colH){i++;continue;}
    if(op)x.d(op,M+col*(CW+GUT),y,CW);y-=x.h;low[col]=y;i++;}
  return {i:i,low:low,cols:Math.min(col+1,COLS)};}
function layout(C){var pages=[],L=C.lines,i=0,n=1;
  while(i<L.length&&n<40){var op=[];texture(op,n);var top=n===1?banner(op,C,masthead(op,C)):runhead(op,C),bot=FOOT;
    var r=fill(L,i,top,bot,null);
    if(r.i>=L.length){var lo=20,hi=top-bot;while(hi-lo>2){var mid=(lo+hi)/2;if(fill(L,i,top,top-mid,null).i>=L.length)hi=mid;else lo=mid;}bot=top-hi-0.5;}
    r=fill(L,i,top,bot,op);
    op.push('0.4 w');for(var c=1;c<r.cols;c++){var xr=M+c*(CW+GUT)-GUT/2;vl(op,xr,top+2,Math.min(r.low[c-1],r.low[c])-1,0.4);}
    footer(op,C,n);pages.push(op.join('\n'));i=r.i;n++;}
  return pages;}

// ---------- write the PDF (built-in Times fonts, nothing to download) ----------
function pdf(pages,title){var out='%PDF-1.4\n%\xe2\xe3\xcf\xd3\n',off=[],objs=[];
  function add(s){objs.push(s);return objs.length;}
  add('<< /Type /Catalog /Pages 2 0 R >>');add('PAGES');
  ['Times-Roman','Times-Bold','Times-Italic','Times-BoldItalic'].forEach(function(f){add('<< /Type /Font /Subtype /Type1 /BaseFont /'+f+' /Encoding /WinAnsiEncoding >>');});
  var kids=[];pages.forEach(function(c){var cid=add('<< /Length '+c.length+' >>\nstream\n'+c+'\nendstream');
    kids.push(add('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 '+PW+' '+PH+'] /Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R /F4 6 0 R >> >> /Contents '+cid+' 0 R >>'));});
  objs[1]='<< /Type /Pages /Kids ['+kids.map(function(k){return k+' 0 R';}).join(' ')+'] /Count '+kids.length+' >>';
  var info=add('<< /Title ('+pe(enc(title))+') /Creator (The Daily Fantasizer) >>');
  objs.forEach(function(s,k){off.push(out.length);out+=(k+1)+' 0 obj\n'+s+'\nendobj\n';});
  var xr=out.length;out+='xref\n0 '+(objs.length+1)+'\n0000000000 65535 f \n';
  off.forEach(function(o){out+=('0000000000'+o).slice(-10)+' 00000 n \n';});
  out+='trailer\n<< /Size '+(objs.length+1)+' /Root 1 0 R /Info '+info+' 0 R >>\nstartxref\n'+xr+'\n%%EOF\n';
  var b=new Uint8Array(out.length);for(var i=0;i<out.length;i++)b[i]=out.charCodeAt(i)&255;return b;}

function save(bytes,name){var blob=new Blob([bytes],{type:'application/pdf'});
  try{var file=new File([blob],name,{type:'application/pdf'});
    if(window.navigator.standalone&&navigator.canShare&&navigator.canShare({files:[file]})){navigator.share({files:[file],title:name}).catch(function(){});return;}}catch(e){}
  if(window.navigator.msSaveOrOpenBlob){window.navigator.msSaveOrOpenBlob(blob,name);return;}
  var url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.rel='noopener';a.style.display='none';
  document.body.appendChild(a);a.click();setTimeout(function(){URL.revokeObjectURL(url);a.remove();},10000);}

window.dfPrintPaper=function(){var C=collect();return pdf(layout(C),'The Daily Fantasizer · '+C.edition);};
btn.addEventListener('click',function(){var lab=btn.textContent;btn.disabled=true;btn.textContent='Printing…';
  setTimeout(function(){try{var C=collect();save(pdf(layout(C),'The Daily Fantasizer · '+C.edition),'daily-fantasizer-week'+(C.week||'')+'.pdf');}
    catch(e){if(window.console)console.error(e);alert('Sorry, the press jammed. Try again.');}
    btn.disabled=false;btn.textContent=lab;},30);});
})();
"""


def edition_date(season, week):
    sept1 = datetime.date(int(season), 9, 1)
    labor = sept1 + datetime.timedelta(days=(0 - sept1.weekday()) % 7)
    return labor + datetime.timedelta(days=8 + 7 * (int(week) - 1))


def block(season, week):
    d = edition_date(season, week)
    date = f"{d:%A}, {d:%B} {d.day}, {d.year}"
    js = JS.replace("/*WIDTHS*/", WIDTHS_JSON)
    return (f'<div class="print-ed">{CSS}<button type="button" class="print-btn" id="pe-btn" data-date="{date}" '
            f'title="Download this week\'s paper as an old-time newspaper PDF">Print</button>'
            f'<script>{js}</script></div>')


import json as _json
WIDTHS_JSON = _json.dumps(WIDTHS, separators=(",", ":"))

def inject(path):
    """Put the button into an already-built page (idempotent: an older copy is replaced)."""
    import re
    h = open(path, encoding="utf-8").read()
    h = re.sub(r'\n?<div class="print-ed">.*?</script></div>\n?', "\n", h, flags=re.S)
    wk = re.search(r"WEEK (\d+) EDITION", h)
    yr = re.search(r"(\d{4}) season", h)
    card = re.search(r'<a class="to-league"[^>]*>.*?</a>', h, flags=re.S)
    if not (wk and yr and card):
        print(f"{path}: no paper tab found, left alone")
        return
    h = h[:card.end()] + "\n\n" + block(yr.group(1), wk.group(1)) + "\n" + h[card.end():]
    open(path, "w", encoding="utf-8").write(h)
    print(f"{path}: Print button in (week {wk.group(1)}, {yr.group(1)})")


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        inject(p)
