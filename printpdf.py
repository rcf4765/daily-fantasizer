"""The Daily Fantasizer: a Print button at the bottom of This Week's Paper (user, 2026-11-10).

Tapping it downloads the paper tab as an old-time newspaper PDF (daily-fantasizer-weekN.pdf): masthead with ears
and dateline, a banner headline (the first biggest-news story), three justified Times columns with column rules,
drop caps, agate-type box scores with dot leaders, section heads between rules, "-30-" at the end, and a
cream paper texture. The PDF is written in the browser from what is on the paper tab (no libraries, no network,
works offline and on the members-only site), so every edition and every league gets it automatically.
Pictures and charts (user, 2026-11-10: "add some visual flair and pictures, keep the graphs"): team crests become
halftone newspaper photos (canvas -> JPEG), red rubber stamps, engraved footballs, a trophy, mugshots, wanted posters,
and the paper's charts redrawn as print graphics: lineup strips, Scoreboard bars, Points by Position, sidebar bars,
forecast split bars, the Matchup radar and every team's Roster Radar (numbers read from the chart labels).

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
function up(s){return s.toUpperCase().replace(/\xDF/g,'SS');}
function T(el){return el?el.textContent.replace(/\s+/g,' ').trim():'';}
function q(r,s){return r?r.querySelector(s):null;}
function qa(r,s){return r?Array.prototype.slice.call(r.querySelectorAll(s)):[];}
function own(el){if(!el)return'';var t='';for(var i=0;i<el.childNodes.length;i++){var k=el.childNodes[i];if(k.nodeType===3)t+=k.textContent;}return t.replace(/\s+/g,' ').trim();}
function crest(el){var i=el&&(el.classList&&el.classList.contains('lg')?el:el.querySelector('.lg'));var m=i&&(i.getAttribute('class')||'').match(/\blg-(\d+)\b/);return m?m[1]:null;}
function nums(s){return (String(s||'').replace(/−/g,'-').match(/-?\d+(\.\d+)?/g)||[]).map(Number);}
function F(v){return (+v).toFixed(2);}

// ---------- page geometry: US Letter, three columns ----------
var PW=612,PH=792,M=36,COLS=3,GUT=15,CW=(PW-2*M-GUT*(COLS-1))/COLS,FOOT=M+18;
var INK='0.13 0.11 0.09',PAPER='0.957 0.925 0.851',RED='0.66 0.13 0.1';
var TONE=['0.13 0.11 0.09','0.42 0.38 0.33','0.7 0.66 0.58','0.86 0.82 0.73'];
var BODY={f:'R',z:8.8,l:10.7};
var IMGS={},IMGN=0;

function txt(o,f,z,x,y,s,cs,ws,col){o.push('BT '+(col||INK)+' rg '+FN[f]+' '+z+' Tf '+(cs||0).toFixed(2)+' Tc '+(ws||0).toFixed(3)+' Tw '+F(x)+' '+F(y)+' Td ('+pe(s)+') Tj ET');}
function ctxt(o,f,z,cx,y,s,cs,col){txt(o,f,z,cx-tw(s,f,z,cs)/2,y,s,cs,0,col);}
function hl(o,x1,x2,y,w){o.push(INK+' RG '+w.toFixed(2)+' w '+F(x1)+' '+F(y)+' m '+F(x2)+' '+F(y)+' l S');}
function vl(o,x,y1,y2,w){o.push(INK+' RG '+w.toFixed(2)+' w '+F(x)+' '+F(y1)+' m '+F(x)+' '+F(y2)+' l S');}
function dash(o,x1,y1,x2,y2,w){o.push(INK+' RG '+w+' w [1.6 1.4] 0 d '+F(x1)+' '+F(y1)+' m '+F(x2)+' '+F(y2)+' l S [] 0 d');}
function box(o,x,y,w,h,lw,col){o.push((col||INK)+' RG '+lw+' w '+F(x)+' '+F(y)+' '+F(w)+' '+F(h)+' re S');}
function rect(o,x,y,w,h,col){if(w>0&&h>0)o.push((col||INK)+' rg '+F(x)+' '+F(y)+' '+F(w)+' '+F(h)+' re f');}
function hatch(o,x,y,w,h,step,both){if(w<=0||h<=0)return;o.push('q '+F(x)+' '+F(y)+' '+F(w)+' '+F(h)+' re W n '+INK+' RG 0.45 w');
  for(var k=-h;k<w;k+=step){o.push(F(x+k)+' '+F(y)+' m '+F(x+k+h)+' '+F(y+h)+' l S');if(both)o.push(F(x+k+h)+' '+F(y)+' m '+F(x+k)+' '+F(y+h)+' l S');}o.push('Q');}
function swatch(o,x,y,w,h,k){if(w<=0)return;
  if(k===0)rect(o,x,y,w,h,TONE[0]);else if(k===1)hatch(o,x,y,w,h,2.2);else if(k===2)rect(o,x,y,w,h,TONE[1]);
  else if(k===3)hatch(o,x,y,w,h,2.4,true);else if(k===4)rect(o,x,y,w,h,TONE[2]);else if(k===5){rect(o,x,y,w,h,TONE[3]);hatch(o,x,y,w,h,3.2);}
  else rect(o,x,y,w,h,TONE[3]);box(o,x,y,w,h,0.4);}
function star(o,cx,cy,r,col){var p=[];for(var i=0;i<10;i++){var a=Math.PI/2+i*Math.PI/5,rr=i%2?r*0.42:r;p.push(F(cx+rr*Math.cos(a))+' '+F(cy+rr*Math.sin(a)));}
  o.push((col||INK)+' rg '+p[0]+' m '+p.slice(1).join(' l ')+' l h f');}
function base(top,z,l){return top-(l-z)/2-z*0.78;}
function fit(s,f,z,w,cs){if(tw(s,f,z,cs)<=w)return s;while(s.length>1&&tw(s+'...',f,z,cs)>w)s=s.slice(0,-1);return s.replace(/\s+$/,'')+'...';}
function image(o,id,x,y,s){var im=IMGS[id];if(!im)return false;o.push('q '+F(s)+' 0 0 '+F(s)+' '+F(x)+' '+F(y)+' cm '+im.name+' Do Q');return true;}

// ---------- engravings: football, trophy, silhouette, rubber stamp ----------
function football(o,cx,cy,L,col,lace){var h=L*0.31,k=0.55;col=col||INK;lace=lace||PAPER;
  o.push(col+' rg '+F(cx-L/2)+' '+F(cy)+' m '+F(cx-L/2+L*0.18)+' '+F(cy+h*1.25)+' '+F(cx+L/2-L*0.18)+' '+F(cy+h*1.25)+' '+F(cx+L/2)+' '+F(cy)+' c '+
    F(cx+L/2-L*0.18)+' '+F(cy-h*1.25)+' '+F(cx-L/2+L*0.18)+' '+F(cy-h*1.25)+' '+F(cx-L/2)+' '+F(cy)+' c f');
  o.push(lace+' RG '+(L*0.03).toFixed(2)+' w '+F(cx-L*0.18)+' '+F(cy+h*0.18)+' m '+F(cx+L*0.18)+' '+F(cy+h*0.18)+' l S');
  for(var i=-2;i<=2;i++)o.push(F(cx+i*L*0.075)+' '+F(cy+h*0.02)+' m '+F(cx+i*L*0.075)+' '+F(cy+h*0.36)+' l S');
  o.push(F(cx-L*0.36)+' '+F(cy+h*0.6)+' m '+F(cx-L*0.33)+' '+F(cy-h*0.6)+' l S '+F(cx+L*0.36)+' '+F(cy+h*0.6)+' m '+F(cx+L*0.33)+' '+F(cy-h*0.6)+' l S');}
function trophy(o,cx,y,s){var w=s*0.62,top=y+s;
  o.push(INK+' rg '+F(cx-w/2)+' '+F(top)+' m '+F(cx+w/2)+' '+F(top)+' l '+F(cx+w/2)+' '+F(top-s*0.25)+' '+F(cx+w*0.2)+' '+F(top-s*0.55)+' '+F(cx+w*0.08)+' '+F(top-s*0.6)+' c '+
    F(cx+w*0.08)+' '+F(y+s*0.2)+' l '+F(cx+w*0.3)+' '+F(y+s*0.2)+' l '+F(cx+w*0.3)+' '+F(y)+' l '+F(cx-w*0.3)+' '+F(y)+' l '+F(cx-w*0.3)+' '+F(y+s*0.2)+' l '+
    F(cx-w*0.08)+' '+F(y+s*0.2)+' l '+F(cx-w*0.08)+' '+F(top-s*0.6)+' l '+F(cx-w*0.2)+' '+F(top-s*0.55)+' '+F(cx-w/2)+' '+F(top-s*0.25)+' '+F(cx-w/2)+' '+F(top)+' c f');
  o.push(INK+' RG '+(s*0.05).toFixed(2)+' w '+F(cx-w/2)+' '+F(top-s*0.06)+' m '+F(cx-w*0.9)+' '+F(top-s*0.06)+' '+F(cx-w*0.8)+' '+F(top-s*0.42)+' '+F(cx-w*0.32)+' '+F(top-s*0.45)+' c S');
  o.push(F(cx+w/2)+' '+F(top-s*0.06)+' m '+F(cx+w*0.9)+' '+F(top-s*0.06)+' '+F(cx+w*0.8)+' '+F(top-s*0.42)+' '+F(cx+w*0.32)+' '+F(top-s*0.45)+' c S');
  star(o,cx,top-s*0.24,s*0.11,PAPER);}
function silhouette(o,cx,y,s){var r=s*0.2;o.push(TONE[1]+' rg '+F(cx-s*0.42)+' '+F(y)+' m '+F(cx-s*0.42)+' '+F(y+s*0.38)+' '+F(cx-s*0.2)+' '+F(y+s*0.5)+' '+F(cx)+' '+F(y+s*0.5)+' c '+
    F(cx+s*0.2)+' '+F(y+s*0.5)+' '+F(cx+s*0.42)+' '+F(y+s*0.38)+' '+F(cx+s*0.42)+' '+F(y)+' c f');
  var cy=y+s*0.7,kk=r*0.552;o.push(F(cx+r)+' '+F(cy)+' m '+F(cx+r)+' '+F(cy+kk)+' '+F(cx+kk)+' '+F(cy+r)+' '+F(cx)+' '+F(cy+r)+' c '+F(cx-kk)+' '+F(cy+r)+' '+F(cx-r)+' '+F(cy+kk)+' '+F(cx-r)+' '+F(cy)+' c '+
    F(cx-r)+' '+F(cy-kk)+' '+F(cx-kk)+' '+F(cy-r)+' '+F(cx)+' '+F(cy-r)+' c '+F(cx+kk)+' '+F(cy-r)+' '+F(cx+r)+' '+F(cy-kk)+' '+F(cx+r)+' '+F(cy)+' c f');
  ctxt(o,'B',s*0.3,cx,cy-s*0.1,'?',0,PAPER);}
function stamp(o,cx,cy,s,ang,z){s=up(enc(s));z=z||8;var w=tw(s,'B',z,1)+10,h=z+7,a=ang*Math.PI/180,c=Math.cos(a),sn=Math.sin(a);
  o.push('q '+c.toFixed(4)+' '+sn.toFixed(4)+' '+(-sn).toFixed(4)+' '+c.toFixed(4)+' '+F(cx)+' '+F(cy)+' cm');
  rect(o,-w/2,-h/2,w,h,PAPER);box(o,-w/2,-h/2,w,h,1.3,RED);box(o,-w/2+2,-h/2+2,w-4,h-4,0.4,RED);txt(o,'B',z,-w/2+5.5,-z*0.35,s,1,0,RED);o.push('Q');}

// ---------- line builders (every block becomes lines that flow down the columns) ----------
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
      if(dc&&i===0){txt(op,'B',dz,x,base(top,z,l)-2*l,dc);}
      var gaps=(t.match(/ /g)||[]).length;
      if(al==='j'&&!last&&gaps){ws=(ww-nat)/gaps;if(ws>z*0.7)ws=0;}
      var xx=al==='c'?x+(w-nat)/2:al==='r'?x+w-nat:x+off;
      txt(op,f,z,xx,b,t,0,ws);}});});
  return L;}
function center(raw,f,z,l,o){o=o||{};var s=enc(raw);if(o.caps)s=up(s);var cs=o.cs||0;if(!s)return[];
  var ls=wrap(s,f,z,function(){return CW-4;},cs);
  return ls.map(function(t){return {h:l,kn:o.kn!==false,d:function(op,x,top,w){ctxt(op,f,z,x+w/2,base(top,z,l),t,cs,o.col);}};});}
function rule(kind,h){return {h:h||6,sp:true,d:function(op,x,top,w){var y=top-(h||6)/2;
  if(kind==='thin')hl(op,x,x+w,y,0.5);else if(kind==='thick')hl(op,x,x+w,y,1.6);
  else if(kind==='double'){hl(op,x,x+w,y+1.3,1.4);hl(op,x,x+w,y-1.2,0.4);}
  else if(kind==='short'){hl(op,x+w*0.36,x+w*0.64,y,0.6);}
  else if(kind==='orn'){hl(op,x+w*0.22,x+w*0.42,y,0.5);hl(op,x+w*0.58,x+w*0.78,y,0.5);football(op,x+w/2,y,13);}}};}
function gap(h){return {h:h,sp:true,d:function(){}};}
function agate(left,right,o){o=o||{};var f=o.f||'R',fr=o.fr||f,z=o.z||8,l=o.l||9.8,a=enc(left),b=enc(right);
  return {h:l,kn:!!o.kn,d:function(op,x,top,w){var y=base(top,z,l),wb=tw(b,fr,z),aa=fit(a,f,z,w-wb-8),wa=tw(aa,f,z);
    txt(op,f,z,x,y,aa);txt(op,fr,z,x+w-wb,y,b);
    var dots='',dw=tw('.','R',z)+1.2,n=Math.floor((w-wa-wb-6)/dw);if(n>1){for(var i=0;i<n;i++)dots+='.';txt(op,'R',z,x+w-wb-3-n*dw,y,dots,1.2);}}};}
function row3(a,m,b,o){o=o||{};var z=o.z||7.6,l=o.l||9.4;a=enc(a);m=enc(m);b=enc(b);
  return {h:l,d:function(op,x,top,w){var y=base(top,z,l),mw=26,side=(w-mw)/2-2;
    var fa=o.aw?'B':'R',fb=o.bw?'B':'R',aa=fit(a,fa,z,side),bb=fit(b,fb,z,side);
    txt(op,fa,z,x,y,aa);ctxt(op,'X',z,x+w/2,y,m);txt(op,fb,z,x+w-tw(bb,fb,z),y,bb);}};}
function head(raw,z){z=z||12.5;return center(raw,'B',z,z*1.08);}
function kick(raw){return center(raw,'R',6.6,8.6,{caps:true,cs:0.45});}
function deck(raw,z){z=z||8.6;return center(raw,'I',z,z*1.2);}
function secHead(title,sub){var L=[rule('thick',5),gap(2)].concat(center(title,'B',11,12.5,{caps:true,cs:0.9}));
  if(sub)L=L.concat(center(sub,'I',7.4,9));L.push(rule('thin',6));L.push(gap(2));
  L.forEach(function(x){x.kn=true;});return L;}
function endStory(){return [gap(3),rule('short',7),gap(3)];}
function bullets(arr){var L=[];arr.forEach(function(s){L=L.concat(para('• '+s,{f:'I',z:7.8,l:9.4,ind:0,al:'l'}));});return L;}
function caption(raw){return para(raw,{f:'I',z:7,l:8.4,ind:0,al:'c'}).map(function(x){x.kn=true;return x;});}

// photos: one or two halftone crests in frames, with captions and an optional red stamp
function photoPair(a,b,s,stampTxt,vs){var cap=17,h=s+cap+4;
  return {h:h,kn:true,d:function(op,x,top,w){var y=top-s-2,mid=x+w/2;
    function one(t,cx,dim){box(op,cx-s/2-2.5,y-2.5,s+5,s+5,0.9);box(op,cx-s/2-0.8,y-0.8,s+1.6,s+1.6,0.3);
      if(!image(op,t.id,cx-s/2,y,s))silhouette(op,cx,y+2,s-4);
      var n=fit(enc(t.name),'B',7,s+12),c=fit(enc(t.sub||''),'I',6.6,s+14);ctxt(op,'B',7,cx,y-11,n);ctxt(op,'I',6.6,cx,y-19,c);}
    if(b){var off=s/2+15;one(a,mid-off);one(b,mid+off);ctxt(op,'X',9,mid,y+s/2-3,enc(vs||'def.'));}else one(a,mid);
    if(stampTxt)stamp(op,b?mid:mid+s*0.3,y+s*0.82,stampTxt,-11,7.6);}};}

// ---------- charts ----------
function stripChart(rows){var bh=12,l=bh+12,L=[];
  rows.forEach(function(r,ri){L.push({h:l,kn:true,d:function(op,x,top,w){var y=top-l+2,lab=fit(enc(r.name),'B',6.8,w-40);
    txt(op,'B',6.8,x,top-7,lab);txt(op,'B',6.8,x+w-tw(enc(r.total),'B',6.8),top-7,enc(r.total));
    var tot=r.segs.reduce(function(a,s){return a+s.v;},0)||1,xx=x,sc=w*(r.total*1/r.max);
    r.segs.forEach(function(sg,i){var sw=sc*sg.v/tot;var dark=i%2===0;rect(op,xx,y,sw,bh,dark?TONE[0]:TONE[2]);
      var t=enc(sg.n),tz=5.6;if(tw(t,'R',tz)+3<sw)txt(op,'R',tz,xx+1.6,y+bh/2-2,t,0,0,dark?PAPER:INK);xx+=sw;});
    box(op,x,y,sc,bh,0.5);}});});
  return L;}
function laneChart(lanes,max,avg){var bh=8,l=12.5;
  return lanes.map(function(r,ri){return {h:l,kn:true,d:function(op,x,top,w){var nw=56,vw=26,bx=x+nw,bw=w-nw-vw,y=top-l+2.5,s=bw/max;
    txt(op,ri===0?'B':'R',6.9,x,y+1.5,fit(enc(r.name),ri===0?'B':'R',6.9,nw-3));
    if(ri===0)rect(op,bx,y,r.got*s,bh,TONE[0]);else{rect(op,bx,y,r.got*s,bh,TONE[3]);hatch(op,bx,y,r.got*s,bh,2);box(op,bx,y,r.got*s,bh,0.5);}
    if(r.poss>r.got){box(op,bx+r.got*s,y,(r.poss-r.got)*s,bh,0.5);hatch(op,bx+r.got*s,y,(r.poss-r.got)*s,bh,4.5);}
    if(avg)dash(op,bx+avg*s,y-2.5,bx+avg*s,y+bh+2.5,0.7);
    var v=enc(r.val);txt(op,ri===0?'B':'R',7,x+w-tw(v,ri===0?'B':'R',7),y+1.5,v);}};});}
function laneKey(avg){return {h:11,kn:true,d:function(op,x,top,w){var y=top-8.5,z=6;
  rect(op,x,y,8,5,TONE[0]);txt(op,'R',z,x+10,y,'Won');rect(op,x+28,y,8,5,TONE[3]);hatch(op,x+28,y,8,5,2);box(op,x+28,y,8,5,0.4);txt(op,'R',z,x+38,y,'Lost');
  box(op,x+56,y,8,5,0.4);hatch(op,x+56,y,8,5,4.5);txt(op,'R',z,x+66,y,'Left on bench');
  if(avg){dash(op,x+114,y-1,x+114,y+6,0.7);txt(op,'R',z,x+117,y,enc('Lg. avg '+avg));}}};}
function posChart(rows,labels){var bh=9,l=13,L=[];
  L.push({h:12,kn:true,d:function(op,x,top,w){var xx=x,y=top-8.5;labels.forEach(function(lb,i){var t=enc(lb);swatch(op,xx,y,7,5,i);txt(op,'R',5.8,xx+8.5,y,t);xx+=tw(t,'R',5.8)+14;});}});
  var max=Math.max.apply(null,rows.map(function(r){return r.total;}))||1;
  rows.forEach(function(r){L.push({h:l,d:function(op,x,top,w){var nw=52,vw=22,bx=x+nw,bw=w-nw-vw,y=top-l+2.5,xx=bx;
    txt(op,'R',6.8,x,y+1,fit(enc(r.name),'R',6.8,nw-3));
    r.segs.forEach(function(sg){var sw=bw*sg.v/max;swatch(op,xx,y,sw,bh,sg.k);if(sg.king)star(op,xx+sw/2,y+bh+1.6,2.6,RED);xx+=sw;});
    var v=enc(r.v);txt(op,'B',7,x+w-tw(v,'B',7),y+1,v);}});});
  L.push({h:10,d:function(op,x,top,w){star(op,x+3,top-5,2.6,RED);txt(op,'I',6.4,x+8,top-7,'Best in the league at the position');}});
  return L;}
function barRows(rows,max){return rows.map(function(r,i){return {h:12,kn:true,d:function(op,x,top,w){var nw=62,vw=26,bw=w-nw-vw,y=top-9.5;
  txt(op,'R',6.8,x,y+0.8,fit(enc(r.name),'R',6.8,nw-3));var bwid=bw*r.v/max;
  if(r.alt){rect(op,x+nw,y,bwid,7,TONE[3]);hatch(op,x+nw,y,bwid,7,2);box(op,x+nw,y,bwid,7,0.4);}else rect(op,x+nw,y,bwid,7,TONE[0]);
  var v=enc(r.val);txt(op,'B',7,x+w-tw(v,'B',7),y+0.8,v);}};});}
function splitBar(fav,dog,a,b){return {h:12,kn:true,d:function(op,x,top,w){var y=top-10,t=a+b||1,wa=w*a/t;
  rect(op,x,y,wa,8,TONE[0]);rect(op,x+wa,y,w-wa,8,TONE[3]);hatch(op,x+wa,y,w-wa,8,2.4);box(op,x,y,w,8,0.5);
  txt(op,'B',6.2,x+2,y+2,enc(fav+' '+a),0,0,PAPER);var r=enc(b+' '+dog),rw=tw(r,'B',6.2);rect(op,x+w-4-rw,y+1,rw+3,6,PAPER);txt(op,'B',6.2,x+w-2.5-rw,y+2,r);}};}
var SLOTS=['QB','RB1','RB2','WR1','WR2','TE','FLEX','D/ST','K'];
function radar(op,cx,cy,r,series,lab){var n=SLOTS.length;function pt(i,v){var a=Math.PI/2-i*2*Math.PI/n;return [cx+r*v/100*Math.cos(a),cy+r*v/100*Math.sin(a)];}
  function poly(vals){return vals.map(function(v,i){var p=pt(i,Math.max(v,2));return F(p[0])+' '+F(p[1]);});}
  series.forEach(function(s,si){if(!s||!s.vals)return;var p=poly(s.vals);
    if(s.fill)o2(op,p,s.fill,'f');});
  [25,75,100].forEach(function(v){var p=poly(SLOTS.map(function(){return v;}));o2(op,p,null,'s',0.3);});
  var pa=poly(SLOTS.map(function(){return 50;}));op.push('[1.2 1.2] 0 d');o2(op,pa,null,'s',0.5);op.push('[] 0 d');
  for(var i=0;i<n;i++){var e=pt(i,100);op.push(INK+' RG 0.25 w '+F(cx)+' '+F(cy)+' m '+F(e[0])+' '+F(e[1])+' l S');
    if(lab){var lp=pt(i,100+(lab>5?16:20)),t=SLOTS[i];ctxt(op,'R',lab,lp[0],lp[1]-lab*0.35,t);}}
  series.forEach(function(s){if(!s||!s.vals)return;var p=poly(s.vals);if(s.dash)op.push('[2 1.3] 0 d');o2(op,p,null,'s',s.lw||0.9);if(s.dash)op.push('[] 0 d');
    s.vals.forEach(function(v,i){var q2=pt(i,Math.max(v,2));rect(op,q2[0]-1,q2[1]-1,2,2,INK);});});}
function o2(op,p,fill,mode,lw){op.push((fill?fill+' rg ':'')+INK+' RG '+(lw||0.5)+' w '+p[0]+' m '+p.slice(1).join(' l ')+' h '+(mode==='f'?'f':'s'));}
function radarPair(cards,season){var h=CW/2+20;
  return {h:h,kn:false,d:function(op,x,top,w){cards.forEach(function(c,i){var cw=w/2,cx=x+cw*i+cw/2,r=cw*0.3;
    var nm=fit(enc(c.name),'B',7.2,cw-16);if(c.id&&IMGS[c.id]){var nw=tw(nm,'B',7.2)+11;image(op,c.id,cx-nw/2,top-10,9);txt(op,'B',7.2,cx-nw/2+11,top-8,nm);}else ctxt(op,'B',7.2,cx,top-8,nm);
    if(c.sum)ctxt(op,'I',5.8,cx,top-15.5,fit(enc(c.sum),'I',5.8,cw-6));
    radar(op,cx,top-19-r-9,r,[{vals:c.season,fill:TONE[2],lw:0.8},{vals:c.ros,dash:true,lw:0.7}],4.6);});
    if(cards.length===2)vl(op,x+w/2,top-4,top-h+6,0.3);}};}
function radarKey(sLab){return {h:12,kn:true,d:function(op,x,top,w){var y=top-8.5;rect(op,x,y,9,5,TONE[2]);box(op,x,y,9,5,0.4);txt(op,'R',6,x+11,y,enc(sLab));
  var x2=x+tw(enc(sLab),'R',6)+20;op.push('[2 1.3] 0 d');hl(op,x2,x2+10,y+2.5,0.7);op.push('[] 0 d');txt(op,'R',6,x2+12,y,'Rest of season');
  var x3=x2+70;op.push('[1.2 1.2] 0 d');hl(op,x3,x3+10,y+2.5,0.5);op.push('[] 0 d');txt(op,'R',6,x3+12,y,'Lg. avg (50)');}};}
function bigRadar(a,b){var r=CW*0.33,h=2*r+38;return {h:h,kn:true,d:function(op,x,top,w){
  radar(op,x+w/2,top-r-14,r,[{vals:a.vals,fill:TONE[2],lw:1},{vals:b.vals,dash:true,lw:1}],6);
  var y=top-h+8,t1=enc(a.name),t2=enc(b.name),tot=tw(t1,'R',6.4)+tw(t2,'R',6.4)+42,xx=x+(w-tot)/2;
  rect(op,xx,y,9,5,TONE[2]);box(op,xx,y,9,5,0.4);txt(op,'R',6.4,xx+11,y,t1);xx+=tw(t1,'R',6.4)+24;op.push('[2 1.3] 0 d');hl(op,xx,xx+9,y+2.5,1);op.push('[] 0 d');txt(op,'R',6.4,xx+11,y,t2);}};}
function mugshot(id,no,team){var s=46,h=s+22;return {h:h,kn:true,d:function(op,x,top,w){var cx=x+w/2,y=top-s-3,bx=cx-s/2-10,bw=s+20;
  rect(op,bx,y-2,bw,s+5,TONE[3]);for(var k=1;k<6;k++){hl(op,bx,bx+bw,y-2+k*(s+5)/6,0.25);txt(op,'R',3.6,bx+1,y-1+k*(s+5)/6,String(7-k)+"'");}
  if(!image(op,id,cx-s/2,y,s))silhouette(op,cx,y,s);box(op,bx,y-2,bw,s+5,0.7);
  var plate=enc('NO. '+no),pw=tw(plate,'B',7,0.6)+12;rect(op,cx-pw/2,y-16,pw,11,TONE[0]);txt(op,'B',7,cx-pw/2+6,y-12.8,plate,0.6,0,PAPER);}};}
function wanted(name,id,proj,found){var s=38;return {h:s+30,kn:true,d:function(op,x,top,w){var cx=x+w/2,bw=s+44,y=top-s-10;
  box(op,cx-bw/2,y-14,bw,s+22,1.1);box(op,cx-bw/2+2.2,y-11.8,bw-4.4,s+17.6,0.35);
  silhouette(op,cx,y,s);if(id)image(op,id,cx+s/2-2,y+2,13);
  var mx=Math.max(proj,found,1),bx=cx-bw/2+6,bwid=bw-36;
  hatch(op,bx,y-6,bwid*proj/mx,3.4,1.8);box(op,bx,y-6,bwid*proj/mx,3.4,0.35);rect(op,bx,y-11,bwid*found/mx,3.4,TONE[0]);
  txt(op,'R',4.8,bx+bwid+3,y-5.6,'PROJ');txt(op,'R',4.8,bx+bwid+3,y-10.6,'FOUND');}};}

// ---------- crests -> halftone newspaper photos (drawn on a canvas, saved as JPEG) ----------
function loadCrest(id){return new Promise(function(res){var el=document.querySelector('.lg-'+id);if(!el)return res(null);
  var m=(getComputedStyle(el).backgroundImage||'').match(/url\(["']?(.*?)["']?\)$/);if(!m)return res(null);
  var im=new Image();im.onload=function(){try{var N=46,S=230,t=document.createElement('canvas');t.width=t.height=N;var tg=t.getContext('2d');
    tg.fillStyle='#f4ecd9';tg.fillRect(0,0,N,N);tg.drawImage(im,0,0,N,N);var d=tg.getImageData(0,0,N,N).data;
    var c=document.createElement('canvas');c.width=c.height=S;var g=c.getContext('2d'),cell=S/N;g.fillStyle='#f4ecd9';g.fillRect(0,0,S,S);g.fillStyle='#231d17';
    for(var yy=0;yy<N;yy++)for(var xx=0;xx<N;xx++){var p=(yy*N+xx)*4,lum=(0.3*d[p]+0.59*d[p+1]+0.11*d[p+2])/255,dk=Math.min(1,Math.max(0,(1-lum-0.11)*1.45));
      var r=cell*0.74*Math.sqrt(dk);if(r>0.25){g.beginPath();g.arc(xx*cell+cell/2+(yy%2?cell/2:0)*0,yy*cell+cell/2,r,0,6.2832);g.fill();}}
    var u=c.toDataURL('image/jpeg',0.86),b=atob(u.split(',')[1]);IMGN++;IMGS[id]={name:'/Im'+IMGN,data:b,w:S,h:S};}catch(e){}res(null);};
  im.onerror=function(){res(null);};im.src=m[1];});}
function loadCrests(){var ids={};qa(document.getElementById('paper'),'.lg').forEach(function(e){var c=crest(e);if(c)ids[c]=1;});
  return Promise.all(Object.keys(ids).map(loadCrest));}

// ---------- read the paper tab ----------
function collect(){
  var P=document.getElementById('paper'),mast=document.querySelector('.mast'),C={};
  var mk=qa(mast,'.mast-top > .kicker').map(T),ms=qa(mast,'.mast-sub span').map(T);
  C.official=mk[0]||'';C.vol=(mk[1]||'').split('·').slice(0,2).join('·').trim();
  C.edition=ms[0]||'';C.format=ms[1]||'';C.price=ms[2]||'';
  C.week=(C.edition.match(/\d+/)||[''])[0];C.date=btn.getAttribute('data-date')||'';
  C.tiles=qa(P,'.tiles .tile').map(function(t){return {k:T(q(t,'.tile-k')),v:T(q(t,'b')),s:T(q(t,'.tile-s'))};});
  // Roster Radar numbers (from each chart's label), by crest
  var RD={};qa(P,'#roster-radar .rd-card').forEach(function(c){var id=crest(q(c,'.rd-h')),lab=(q(c,'svg')||{getAttribute:function(){return'';}}).getAttribute('aria-label')||'';
    var parts=lab.split(';').map(function(s){return SLOTS.map(function(sl){var m=s.match(new RegExp('(?:^|[ :,])'+sl.replace('/','\\/')+' (\\d+)'));return m?+m[1]:0;});});
    var sm=qa(c,'.rd-sum span');RD[id||T(q(c,'h3'))]={id:id,name:T(q(c,'h3')),season:parts[0],next:parts[1],ros:parts[2],sum:T(sm[0])};});
  var L=[],banner=null;
  // the biggest news: first card is the banner
  qa(P,'.ups-card').forEach(function(c,i){
    var stamps=qa(c,'.stamp').map(T),k=T(q(c,'.ups-top .kicker')),h=T(q(c,'.ups-h'));
    var W=q(c,'.ups-w'),Lo=q(c,'.ups-l'),body=[];
    if(i===0){banner={head:h,deck:k};body=body.concat(kick(stamps.join(' · ')||'Page one'));}
    else{body=body.concat(kick(k)).concat(head(h,11.5));}
    body.push(gap(4));
    if(W&&Lo){body.push(photoPair({id:crest(W),name:T(q(W,'.ups-n')),sub:T(q(W,'b'))+' · '+T(q(W,'small'))},{id:crest(Lo),name:T(q(Lo,'.ups-n')),sub:T(q(Lo,'b'))+' · '+T(q(Lo,'small'))},i===0?66:52,stamps[0]));
      body.push(gap(2));body=body.concat(caption('Margin of victory: '+T(q(c,'.ups-m b')).replace(/^\+/,'')+' points.'));body.push(gap(4));}
    qa(c,'p').forEach(function(p,j){body=body.concat(para(T(p),{drop:j===0}));});
    var salt=qa(c,'.ups-salt span').map(T);if(salt.length){body.push(gap(2));body=body.concat(bullets(salt));}
    body=body.concat(endStory());L=L.concat(body);});
  var an=q(P,'.announce');
  if(an){L.push(rule('orn',14));L=L.concat(kick(T(q(an,'.kicker'))||'Announcements')).concat(head(T(q(an,'h3')),11.5));var aid=crest(an);if(aid&&IMGS[aid])L.push(photoPair({id:aid,name:'',sub:''},null,50));
    qa(an,'p').forEach(function(p){L=L.concat(para(T(p)));});L=L.concat(endStory());}
  // page one: lead story with the lineup strips
  var lead=q(P,'article.lead'),hero=q(P,'section.hero');
  if(lead){var lh=T(q(lead,'h2'));
    if(!banner)banner={head:lh,deck:T(q(lead,'.deck'))};
    else{L=L.concat(kick(T(q(lead,'.kicker'))||'Page one')).concat(head(lh,13)).concat(deck(T(q(lead,'.deck'))));}
    L.push(gap(4));
    if(hero){var sd=qa(hero,'.hero-top .side');
      if(sd.length===2){L.push(photoPair({id:crest(sd[0]),name:T(q(sd[0],'.tname')),sub:T(q(sd[0],'.score'))},{id:crest(sd[1]),name:T(q(sd[1],'.tname')),sub:T(q(sd[1],'.score'))},50,/margin/i.test(T(q(hero,'.mid span')))?'By '+T(q(hero,'.mid b')):null));L.push(gap(3));}
      var strips=qa(hero,'.strip');if(strips.length){var mx=Math.max.apply(null,strips.map(function(s){return nums(T(q(s,'.strip-n')))[0]||0;}));
        L=L.concat(kick(T(q(hero,'.strips > .kicker'))||'Where the points came from'));
        L=L.concat(stripChart(strips.map(function(s,i){return {name:sd[i]?T(q(sd[i],'.tname')):'',total:T(q(s,'.strip-n')),max:mx,
          segs:qa(s,'.seg').map(function(g){var t=g.getAttribute('title')||'',m=t.match(/^(.*?)\s+(-?[\d.]+)$/);return {n:m?(T(g)||m[1].split(' ').slice(-1)[0]):'',v:m?+m[2]:0};}).filter(function(g){return g.v>0;})};})));
        L.push(gap(4));}}
    qa(lead,'p:not(.deck)').forEach(function(p,j){L=L.concat(para(T(p),{drop:j===0}));});L=L.concat(endStory());}
  // sidebar boxes with their bars
  qa(P,'.side-col .box').forEach(function(b){L.push(rule('double',6));L=L.concat(kick(T(q(b,'.kicker')))).concat(head(T(q(b,'h3')),11));L.push(gap(3));
    var rows=qa(b,'.minibars > div').map(function(r){var v=T(r.querySelector('.num'));return {name:T(r.querySelector('span')),val:v,v:nums(v)[0]||0,alt:!!q(r,'.alt')};});
    if(rows.length){L=L.concat(barRows(rows,Math.max.apply(null,rows.map(function(r){return r.v;}))||1));L.push(gap(3));}
    qa(b,'p').forEach(function(p){L=L.concat(para(T(p)));});L.push(gap(2));L.push(rule('double',6));L.push(gap(6));});
  // the scoreboard, with bars
  var g=document.getElementById('games');
  if(g){var games=qa(g,'article.game'),avg=(T(q(g,'.gl-key'))||'').match(/average\s+([\d.]+)/i);avg=avg?+avg[1]:0;
    var lanes=games.map(function(a){return qa(a,'.gl-lane').map(function(ln){var tt=nums(ln.getAttribute('title')).slice(-2),v=q(ln,'.br-val');
      return {name:T(q(ln,'.br-name')),got:tt[0]||nums(own(v))[0]||0,poss:tt[1]||0,val:own(v)};});});
    var mx=Math.max.apply(null,[avg].concat([].concat.apply([],lanes).map(function(r){return Math.max(r.got,r.poss);})))||1;
    L=L.concat(secHead(T(q(g,'.sec-head h2')),T(q(g,'.sec-head .kicker'))));L.push(laneKey(avg));L.push(gap(3));
    games.forEach(function(a,i){if(i)L.push(rule('short',8));
      L=L.concat(kick(T(q(a,'.g-head .kicker'))+' · by '+T(q(a,'.margin')).replace(/^\+/,'')));
      L=L.concat(head(T(q(a,'h3')),10.5));L=L.concat(laneChart(lanes[i],mx,avg));
      var fl=T(q(a,'.flag'));if(fl)L=L.concat(para(fl,{f:'X',z:7.4,l:9.2,ind:0,al:'c'}));
      qa(a,'p').forEach(function(p){L=L.concat(para(T(p)));});});
    L=L.concat(endStory());}
  // points by position: stacked bars
  var po=document.getElementById('positions');
  var prs=qa(po,'.pr').filter(function(r){return T(q(r,'.pr-v'));});
  if(po&&prs.length){var labs=[],rows=prs.map(function(r){return {name:T(q(r,'.br-name')),v:T(q(r,'.pr-v')),total:nums(T(q(r,'.pr-v')))[0]||0,
      segs:qa(r,'.ps').map(function(s,k){var t=(s.getAttribute('data-tip')||'').split('·');if(!labs[k])labs[k]=t[0].trim();return {k:k,v:nums(t[1])[0]||0,king:s.classList.contains('king')};})};});
    L=L.concat(secHead(T(q(po,'.sec-head h2')),'Starters only, stacked by position'));L=L.concat(posChart(rows,labs));L=L.concat(endStory());}
  // manager of the week
  var ho=q(P,'.honor');
  if(ho){L=L.concat(secHead(T(q(ho,'.kicker'))||'Manager of the week'));
    L.push({h:26,kn:true,d:function(op,x,top,w){trophy(op,x+w/2,top-24,22);star(op,x+w/2-30,top-14,3.2);star(op,x+w/2+30,top-14,3.2);}});
    L=L.concat(head(T(q(ho,'h3')),12.5));var hid=crest(ho);if(hid)L.push(photoPair({id:hid,name:'',sub:''},null,62));
    var bg=q(ho,'.big');L=L.concat(center(own(bg),'B',20,22));L=L.concat(deck(T(q(bg,'small')),8));L.push(gap(3));
    qa(ho,'p').forEach(function(p){L=L.concat(para(T(p)));});L=L.concat(endStory());}
  // police blotter (mugshots) + missing persons (posters)
  var bl=document.getElementById('blotter');
  if(bl){var secs=qa(bl,'.sec');
    var b1=secs[0];if(b1&&qa(b1,'.case').length){L=L.concat(secHead(T(q(b1,'h2')),T(q(b1,'.sec-head .kicker'))));
      qa(b1,'.case').forEach(function(c,i){if(i)L.push(rule('short',8));L.push(mugshot(crest(c),T(q(c,'.mug-no')),T(q(c,'.kicker'))));
        L=L.concat(kick(T(q(c,'.kicker'))));L=L.concat(head(T(q(c,'h3')),10.5));qa(c,'p').forEach(function(p){L=L.concat(para(T(p)));});});
      L=L.concat(endStory());}
    var b2=q(bl,'.crime-side .sec');if(b2&&qa(b2,'.poster').length){L=L.concat(secHead(T(q(b2,'h2')),T(q(b2,'.sec-head .kicker'))));
      qa(b2,'.poster').forEach(function(c,i){if(i)L.push(rule('short',8));var nn=qa(c,'.pa .num').map(function(e){return nums(T(e))[0]||0;});
        L=L.concat(center(T(q(c,'.poster-top .kicker'))||'Missing','B',8,10,{caps:true,cs:2.2,col:RED}));
        L=L.concat(center(T(q(c,'h3')),'B',11,12.5,{caps:true,cs:0.6}));
        if(nn.length>1)L.push(wanted(T(q(c,'h3')),crest(c),nn[0],nn[1]));
        if(nn.length>1)L=L.concat(deck('Projected '+nn[0]+' · Found '+nn[1],7.6));qa(c,'p').forEach(function(p){L=L.concat(para(T(p),{al:'c',ind:0}));});});
      L=L.concat(endStory());}}
  // forecast: split bars
  var fc=document.getElementById('forecast');
  if(fc&&qa(fc,'.fc').length){L=L.concat(secHead(T(q(fc,'.sec-head h2')),T(q(fc,'.sec-head .kicker'))));
    qa(fc,'.fc').forEach(function(c){var t=qa(c,'.fc-vs b').map(T),sp=qa(c,'.fc-split .num').map(function(e){return nums(T(e))[0]||0;}),od=T(q(c,'.odds span'));
      L.push(agate((t[0]||'')+' '+T(q(c,'.fc-vs em'))+' vs. '+(t[1]||''),od,{f:'B',fr:'I',kn:true}));
      if(sp.length>1)L.push(splitBar(t[0]||'',t[1]||'',sp[0],sp[1]));
      var p=T(q(c,'p'));if(p)L=L.concat(para(p,{f:'I',z:7.4,l:8.8,ind:0,al:'l'}));L.push(gap(4));});
    L=L.concat(endStory());}
  // matchup of the week: crests, radar, slot table
  var mw=document.getElementById('matchup');
  if(mw&&q(mw,'.mw-head')){L=L.concat(secHead(T(q(mw,'.sec-head h2')),T(q(mw,'.sec-head .kicker'))));
    var A=q(mw,'.mw-ta'),B=q(mw,'.mw-tb'),ia=crest(A),ib=crest(B);
    L.push(photoPair({id:ia,name:T(q(A,'b')),sub:T(q(A,'small'))},{id:ib,name:T(q(B,'b')),sub:T(q(B,'small'))},48,null,'vs.'));
    L=L.concat(deck('Projected spread: '+T(q(mw,'.mw-mid b'))+' · '+T(q(mw,'.mw-mid small')),8));L.push(gap(3));
    var ra=RD[ia],rb=RD[ib];
    if(ra&&rb&&ra.ros&&rb.ros){L=L.concat(kick('Roster Radar · rest of season'));L.push(bigRadar({name:T(q(A,'b')),vals:ra.ros},{name:T(q(B,'b')),vals:rb.ros}));L.push(gap(3));}
    var rows=qa(mw,'.mw-row');if(rows.length){L=L.concat(kick(T(q(mw,'.mw-list > .kicker'))||'Projected points, slot by slot'));L.push(row3(T(q(A,'b')),'',T(q(B,'b')),{aw:1,bw:1}));L.push(rule('thin',4));}
    rows.forEach(function(r){var a=q(r,'.mw-a'),b=q(r,'.mw-b');
      var sa=(T(q(a,'em'))+' '+T(q(a,'b'))).trim(),sb=(T(q(b,'b'))+' '+T(q(b,'em'))).trim();
      if(r.classList.contains('mw-tot'))L.push(rule('thin',4));
      L.push(row3(sa,T(q(r,'.mw-s')),sb,{aw:a&&a.classList.contains('win'),bw:b&&b.classList.contains('win')}));});
    var nt=T(q(mw,'.note-s'));if(nt){L.push(gap(3));L=L.concat(para(nt,{f:'I',z:7.2,l:8.6,ind:0}));}
    L=L.concat(endStory());}
  // roster radar: every team's chart, two by two
  var rr=document.getElementById('roster-radar'),cards=Object.keys(RD).map(function(k){return RD[k];}).filter(function(c){return c.season;});
  if(rr&&cards.length){var sl=T(q(rr,'.pt[data-m="season"]'))||'Season';L=L.concat(secHead(T(q(rr,'.sec-head h2')),T(q(rr,'.sec-head .kicker'))));L.push(radarKey(sl));L.push(gap(2));
    for(var i=0;i<cards.length;i+=2)L.push(radarPair(cards.slice(i,i+2)));L=L.concat(endStory());}
  L=L.concat([gap(4),rule('orn',16)]).concat(center('— 30 —','B',9,12,{kn:false}));
  C.banner=banner;C.lines=L;return C;}

// ---------- paper texture, masthead, banner, running heads ----------
function rnd(seed){var s=seed>>>0;return function(){s=(s*1664525+1013904223)>>>0;return s/4294967296;};}
function texture(op,pg){var r=rnd(9001+pg*77);op.push(PAPER+' rg 0 0 '+PW+' '+PH+' re f');
  for(var i=0;i<26;i++){var g=(0.86+r()*0.07).toFixed(3);op.push(g+' '+(g*0.97).toFixed(3)+' '+(g*0.9).toFixed(3)+' rg '+(r()*PW).toFixed(1)+' '+(r()*PH).toFixed(1)+' '+(6+r()*30).toFixed(1)+' '+(0.4+r()*1.4).toFixed(1)+' re f');}
  for(var j=0;j<420;j++){var k=r(),c=(0.5+r()*0.35).toFixed(2),s=(0.25+k*0.6).toFixed(2);op.push(c+' '+c+' '+(c*0.92).toFixed(2)+' rg '+(r()*PW).toFixed(1)+' '+(r()*PH).toFixed(1)+' '+s+' '+s+' re f');}
  // a frame of rules around the page
  box(op,M-12,M-12,PW-2*M+24,PH-2*M+24,0.9);box(op,M-9,M-9,PW-2*M+18,PH-2*M+18,0.3);
  [[M-12,M-12],[PW-M+12,M-12],[M-12,PH-M+12],[PW-M+12,PH-M+12]].forEach(function(p){star(op,p[0],p[1],3.2);});}
function tri(op,y,z,l,a,b,c,fb){var w=PW-2*M,f='R',cs=0.6;a=up(enc(a));b=up(enc(b));c=up(enc(c));
  while(z>5&&tw(a,f,z,cs)+tw(b,fb||f,z,cs)+tw(c,f,z,cs)>w-24)z-=0.2;var yb=base(y,z,l);
  txt(op,f,z,M,yb,a,cs);txt(op,fb||f,z,M+(w-tw(b,fb||f,z,cs))/2,yb,b,cs);txt(op,f,z,PW-M-tw(c,f,z,cs),yb,c,cs);return y-l;}
function masthead(op,C){var y=PH-M,w=PW-2*M;
  y=tri(op,y,6.8,10,C.vol,C.official,C.edition);hl(op,M,PW-M,y-1,0.5);y-=4;
  var ear=104,eh=58,et=y-3;
  [[M,['“All the Scores','That Fit, We Print.”'],'I'],[PW-M-ear,['LATE CITY EDITION','Week '+C.week+' · Final scores'],'R']].forEach(function(e,ei){
    box(op,e[0],et-eh,ear,eh,0.9);box(op,e[0]+2.5,et-eh+2.5,ear-5,eh-5,0.3);football(op,e[0]+ear/2,et-15,30);
    e[1].forEach(function(s,i){s=enc(s);var f=(e[2]==='R'&&i===0)?'B':e[2],z=i===0?7.6:7;ctxt(op,f,z,e[0]+ear/2,et-36-i*10,s);});});
  var title=enc('The Daily Fantasizer'),tz=Math.min(56,(w-2*ear-24)*1000/tw(title,'B',1000));
  ctxt(op,'B',tz,M+w/2,et-eh/2-tz*0.25,title);
  var sub=enc('★  Est. '+(C.vol||'').replace(/\s*·.*$/,'')+'  ★  '+up(enc(C.price))+'  ★');
  y=et-eh-6;hl(op,M,PW-M,y,2);hl(op,M,PW-M,y-3,0.5);y-=5;
  y=tri(op,y,7,12,C.format,C.date,'Weather: 100% chance of excuses','B');hl(op,M,PW-M,y-1,0.5);hl(op,M,PW-M,y-4,1.6);return y-10;}
function runhead(op,C){var y=tri(op,PH-M,6.8,10,'The Daily Fantasizer',C.date,C.edition);hl(op,M,PW-M,y-1,0.5);hl(op,M,PW-M,y-3.5,1.4);
  football(op,PW/2,y-9,13);hl(op,M,PW/2-14,y-9,0.3);hl(op,PW/2+14,PW-M,y-9,0.3);return y-18;}
function footer(op,C,n){hl(op,M,PW-M,FOOT-6,0.5);var s=enc('— '+n+' —'),z=7.5,y=FOOT-15;
  txt(op,'R',z,M,y,up(enc(C.official)),0.5);ctxt(op,'B',z,PW/2,y,s);var r=up(enc(C.price));txt(op,'R',z,PW-M-tw(r,'R',z,0.5),y,r,0.5);}
function banner(op,C,y){var w=PW-2*M;if(C.banner){var h=up(enc(C.banner.head)),z=36,ls;
  // "EXTRA!" flag
  stamp(op,M+40,y-9,'Extra!',-6,10);y-=16;
  for(;;){ls=wrap(h,'B',z,function(){return w-20;});if(ls.length<=2||z<=20)break;z-=1;}
  ls.forEach(function(t){y-=z*1.02;ctxt(op,'B',z,M+w/2,y+z*0.2,t);});
  var d=enc(C.banner.deck);if(d){var dz=11.5,dl=wrap(d,'I',dz,function(){return w*0.8;});y-=4;dl.forEach(function(t){y-=dz*1.25;ctxt(op,'I',dz,M+w/2,y+dz*0.25,t);});}
  y-=7;}
  // by the numbers: a boxed strip of the stat tiles
  if(C.tiles.length){var n=C.tiles.length,cw=w/n,h=40;hl(op,M,PW-M,y,1.4);hl(op,M,PW-M,y-2.5,0.4);y-=4;
    C.tiles.forEach(function(t,i){var cx=M+cw*i+cw/2;if(i)vl(op,M+cw*i,y-2,y-h+2,0.4);
      ctxt(op,'R',5.8,cx,y-8,fit(up(enc(t.k)),'R',5.8,cw-6,0.5),0.5);ctxt(op,'B',17,cx,y-25,enc(t.v));ctxt(op,'I',6.4,cx,y-35,fit(enc(t.s),'I',6.4,cw-6));});
    y-=h;hl(op,M,PW-M,y,0.4);hl(op,M,PW-M,y-2.5,1.4);y-=12;}
  return y;}

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
    for(var c=1;c<r.cols;c++){var xr=M+c*(CW+GUT)-GUT/2;vl(op,xr,top+2,Math.min(r.low[c-1],r.low[c])-1,0.4);}
    footer(op,C,n);pages.push(op.join('\n'));i=r.i;n++;}
  return pages;}

// ---------- write the PDF (built-in Times fonts + JPEG photos; nothing to download) ----------
function pdf(pages,title){var out='%PDF-1.4\n%\xe2\xe3\xcf\xd3\n',off=[],objs=[];
  function add(s){objs.push(s);return objs.length;}
  add('<< /Type /Catalog /Pages 2 0 R >>');add('PAGES');
  ['Times-Roman','Times-Bold','Times-Italic','Times-BoldItalic'].forEach(function(f){add('<< /Type /Font /Subtype /Type1 /BaseFont /'+f+' /Encoding /WinAnsiEncoding >>');});
  var xo=Object.keys(IMGS).map(function(k){var im=IMGS[k];var id=add('<< /Type /XObject /Subtype /Image /Width '+im.w+' /Height '+im.h+' /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length '+im.data.length+' >>\nstream\n'+im.data+'\nendstream');return im.name+' '+id+' 0 R';}).join(' ');
  var kids=[];pages.forEach(function(c){var cid=add('<< /Length '+c.length+' >>\nstream\n'+c+'\nendstream');
    kids.push(add('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 '+PW+' '+PH+'] /Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R /F4 6 0 R >> /XObject << '+xo+' >> >> /Contents '+cid+' 0 R >>'));});
  objs[1]='<< /Type /Pages /Kids ['+kids.map(function(k){return k+' 0 R';}).join(' ')+'] /Count '+kids.length+' >>';
  var info=add('<< /Title ('+pe(enc(title))+') /Creator (The Daily Fantasizer) >>');
  objs.forEach(function(s,k){off.push(out.length);out+=(k+1)+' 0 obj\n'+s+'\nendobj\n';});
  var xr=out.length;out+='xref\n0 '+(objs.length+1)+'\n0000000000 65535 f \n';
  off.forEach(function(o){out+=('0000000000'+o).slice(-10)+' 00000 n \n';});
  out+='trailer\n<< /Size '+(objs.length+1)+' /Root 1 0 R /Info '+info+' 0 R >>\nstartxref\n'+xr+'\n%%EOF\n';
  var b=new Uint8Array(out.length);for(var i=0;i<out.length;i++)b[i]=out.charCodeAt(i)&255;return b;}

function save(bytes,name){var blob=new Blob([bytes],{type:'application/pdf'});
  function anchor(){var url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.rel='noopener';a.style.display='none';
    document.body.appendChild(a);a.click();setTimeout(function(){URL.revokeObjectURL(url);a.remove();},10000);}
  try{var file=new File([blob],name,{type:'application/pdf'});
    if(window.navigator.standalone&&navigator.canShare&&navigator.canShare({files:[file]})){navigator.share({files:[file],title:name}).catch(function(e){if(!e||e.name!=='AbortError')anchor();});return;}}catch(e){}
  anchor();}

function make(){return loadCrests().then(function(){var C=collect();return {C:C,bytes:pdf(layout(C),'The Daily Fantasizer · '+C.edition)};});}
window.dfPrintPaper=make;
btn.addEventListener('click',function(){var lab=btn.textContent;btn.disabled=true;btn.textContent='Stop the presses…';
  make().then(function(r){save(r.bytes,'daily-fantasizer-week'+(r.C.week||'')+'.pdf');})
    .catch(function(e){if(window.console)console.error(e);alert('Sorry, the press jammed. Try again.');})
    .then(function(){btn.disabled=false;btn.textContent=lab;});});
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
