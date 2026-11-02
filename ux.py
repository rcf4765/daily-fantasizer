"""The Daily Fantasizer: usability pass (user, 2026-11-01: "look through the entire web page, make it as user friendly as possible").

BLOCK sits near the end of template.html (between <!--ux--> and <!--/ux-->, right before <!--gloss-->), so every new
edition has it. `python3 ux.py FILE...` puts the same block into already-built pages (idempotent: an older copy is
replaced). Nothing is added, removed or reordered: layout_check.py still sees the same tabs and sections.

1. Tab bar stays on screen. It sticks to the top while you scroll (subtitles fold away once it's stuck), so you
   can switch tabs from anywhere instead of scrolling back past 9,000+ px of page. It always fits on one row:
   full names on wide screens, short names (Paper, League, Players, Rules, Bets) below 1000px; no more
   "RULE CHANGE S" on phones or Betting wrapping to a second row on laptops.
2. Each tab remembers where you were. Switching away and back returns you to the same spot; a tab you haven't
   read yet opens at its top, right under the bar. The link cards at the end of each tab open the next tab at
   its top. Linked sections land below the sticky bar instead of under it.
3. Phone Top button only shows while you scroll up (it used to sit on top of numbers the whole way down) and
   takes you to the top of the tab you're on; tap again there for the masthead.
4. ⓘ explanations (user, 2026-11-01): each how-it-works note (p.note-s, the Rule Changes intro and steps, the
   Betting rules line) is hidden and its heading gets an ⓘ; tapping it opens the note in a panel under the heading.
   Status lines (data timestamps, "Loading…", sign-in prompts) and notes already inside a fold stay as they were.
   Notes drawn later (the Player Data card) are picked up by a MutationObserver.
5. Bigger touch targets on phones and tablets for the tabbed-group switches, week/view buttons, team tabs and
   player chips in Player Data (most were 26-31 px tall; now 38-42 px), with slightly larger switch labels.
"""
import sys

BLOCK = r"""<!--ux-->
<style>
/* tab bar: one row, stays on screen (usability pass, user 2026-11-01) */
.tabs{position:sticky;top:0;z-index:40;background:var(--sheet);flex-wrap:nowrap}
.tabs .tab{flex:1 1 auto;min-width:0;padding-left:clamp(8px,1.4vw,18px);padding-right:clamp(8px,1.4vw,18px)}
.tabs .tab-t{white-space:nowrap;font-size:clamp(.95rem,1.75vw,1.35rem)}
.tabs .tab-m{display:none}
.tabs .tab-s{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
.tabs.stuck{box-shadow:0 9px 10px -9px rgba(0,0,0,.4)}
.tabs.stuck .tab-s{display:none}
.tabs.stuck .tab,.tabs.stuck .tab[aria-selected="true"]{padding-top:9px;padding-bottom:8px}
@media (max-width:1000px){
  .tabs .tab-t{display:none}
  .tabs .tab-m{display:block;font-family:var(--display);font-weight:900;text-transform:uppercase;letter-spacing:.03em;line-height:1;font-size:1.1rem;white-space:nowrap;order:-1}
}
@media (max-width:760px){
  .tabs{display:grid;grid-template-columns:repeat(5,minmax(0,1fr))}
  .tabs .tab,.tabs .tab[aria-selected="true"],.tabs.stuck .tab{justify-items:center;align-content:center;min-height:42px;padding:8px 2px 7px}
  .tabs .tab-m{font-size:.8rem;letter-spacing:.01em}
}
@media (max-width:360px){.tabs .tab-m{font-size:.66rem;letter-spacing:0}}
/* linked sections land below the sticky bar */
section[id],div.sec[id],.tab-pane [id]{scroll-margin-top:64px}
/* bigger touch targets */
@media (pointer:coarse),(max-width:760px){
  .tab-pane .cmb-sw button{min-height:42px;font-size:.68rem}
  .tab-pane button.pt{min-height:38px}
  #ps-lookup .lk-tt .lk-tb{min-height:40px}
  #ps-lookup button:not(.lk-w):not(.lk-tb):not(.pt){min-height:36px}
  #betting .bk-mt{min-height:42px}
  .tab-pane details>summary{padding-top:9px;padding-bottom:9px}
}
/* ⓘ explanations (user, 2026-11-01): how-it-works notes hide behind an ⓘ on their heading */
.ux-tuck{display:none!important}
.ux-i{appearance:none;display:inline-grid;place-items:center;vertical-align:middle;width:1.5em;height:1.5em;min-width:30px;min-height:30px;margin:-6px 0 -6px 4px;padding:0;border:0;background:none;color:var(--honolulu,#0076b6);font:400 1.15rem/1 system-ui,-apple-system,sans-serif;cursor:pointer;-webkit-tap-highlight-color:transparent;letter-spacing:0;text-transform:none}
.ux-i:hover,.ux-i[aria-expanded="true"]{color:var(--blue)}
.ux-i:focus-visible{outline:3px solid var(--hi);outline-offset:1px;border-radius:50%}
h2 .ux-i{font-size:1.25rem}
.ux-info{border-left:4px solid var(--honolulu,#0076b6);background:var(--paper);color:var(--ink);padding:10px 12px;margin:4px 0 8px;font-size:.88rem;line-height:1.45;display:grid;gap:8px;text-transform:none;letter-spacing:normal;font-family:var(--body);font-weight:400}
.ux-info[hidden]{display:none}
.ux-info>*{margin:0!important;display:block!important;max-width:none!important;font-size:inherit!important;color:inherit!important;font-family:var(--body)!important;letter-spacing:normal!important;text-transform:none!important;line-height:1.45!important}
.ux-info ol,.ux-info ul{display:grid!important}
</style>
<script>
(function(){
  var nav=document.querySelector('.tabs');if(!nav)return;
  var tabs=[].slice.call(nav.querySelectorAll('.tab'));
  // short names for narrow screens
  var SHORT={paper:'Paper',league:'League','player-stats':'Players',proposals:'Rules',betting:'Bets'};
  tabs.forEach(function(t){var id=t.getAttribute('aria-controls');if(!SHORT[id]||t.querySelector('.tab-m'))return;
    var m=document.createElement('span');m.className='tab-m';m.setAttribute('aria-hidden','true');m.textContent=SHORT[id];t.appendChild(m)});
  // a marker where the bar sits when it isn't stuck
  var pin=document.createElement('div');pin.style.height='0';pin.setAttribute('aria-hidden','true');nav.parentNode.insertBefore(pin,nav);
  function y0(){return Math.max(0,pin.getBoundingClientRect().top+scrollY)}
  if('IntersectionObserver' in window)new IntersectionObserver(function(es){es.forEach(function(e){nav.classList.toggle('stuck',!e.isIntersecting&&e.boundingClientRect.top<0)})}).observe(pin);
  else addEventListener('scroll',function(){nav.classList.toggle('stuck',scrollY>y0())},{passive:true});
  // each tab remembers where you were
  function cur(){var s=nav.querySelector('.tab[aria-selected="true"]');return s?s.getAttribute('aria-controls'):'paper'}
  var saved={},prevY=0,fresh=false,from='';
  nav.addEventListener('click',function(e){if(!e.target.closest('.tab'))return;from=cur();prevY=scrollY;saved[from]=prevY},true);
  document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a[data-tab]');if(a){fresh=true;from=cur();prevY=scrollY;saved[from]=prevY}},true);
  tabs.forEach(function(t){t.addEventListener('click',function(){
    var id=t.getAttribute('aria-controls'),b=y0(),y;
    if(id===from&&!fresh){y=prevY}
    else if(!fresh&&saved[id]!=null&&saved[id]>b)y=saved[id];
    else y=Math.min(prevY,b);
    fresh=false;
    scrollTo(0,y);requestAnimationFrame(function(){scrollTo(0,y)});
  })});
  // ---- ⓘ explanations (user, 2026-11-01) ----
  var NOTE='p.note-s:not(.lu-upd), #proposals .rc-hero > p, #proposals .rc-steps, #betting .bk-hero > p:first-of-type';
  function head(n){
    var c=n.closest('.cmb-p, .lk-blk, section')||n.closest('.tab-pane');if(!c)return null;
    if(c.classList.contains('cmb-p')){var cp=c.querySelector('.cmb-cap');if(cp)return cp}
    return c.querySelector('.sec-head h2')||c.querySelector('h2')||c.querySelector('h3, h4');
  }
  function shown(n){var p=n.parentElement;return !p||p.getClientRects().length>0}
  function tuck(){
    document.querySelectorAll(NOTE).forEach(function(n){
      if(n.dataset.ux||n.closest('details,.ux-info'))return;
      var h=head(n);if(!h)return;
      n.dataset.ux='1';n.classList.add('ux-tuck');
      var b=h.querySelector(':scope > .ux-i');
      if(!b){
        b=document.createElement('button');b.type='button';b.className='ux-i';b.textContent='ⓘ';
        b.setAttribute('aria-label','How this works');b.setAttribute('aria-expanded','false');b._notes=[];
        var pn=document.createElement('div');pn.className='ux-info';pn.hidden=true;pn.setAttribute('role','note');b._panel=pn;
        h.appendChild(b);var at=h.closest('.sec-head')||h;at.parentNode.insertBefore(pn,at.nextSibling);
      }
      b._notes.push(n);
    });
  }
  document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('.ux-i');if(!b||!b._panel)return;
    e.preventDefault();e.stopPropagation();
    var open=b.getAttribute('aria-expanded')!=='true',pn=b._panel;
    if(open){var vis=b._notes.filter(function(n){return n.isConnected&&shown(n)});if(!vis.length)vis=b._notes.filter(function(n){return n.isConnected});
      pn.innerHTML='';vis.forEach(function(n){var c=n.cloneNode(true);c.classList.remove('ux-tuck');c.removeAttribute('data-ux');pn.appendChild(c)})}
    pn.hidden=!open;b.setAttribute('aria-expanded',String(open));
  },true);
  tuck();
  var tq=0;new MutationObserver(function(){if(!tq)tq=setTimeout(function(){tq=0;tuck()},80)}).observe(document.body,{childList:true,subtree:true});
  // phone Top button: only while scrolling up; goes to the top of this tab, then the masthead
  var top=document.querySelector('.m-top');
  if(top){
    var last=scrollY;
    addEventListener('scroll',function(){var y=scrollY;
      if(y<last-3)top.classList.toggle('show',y>innerHeight*1.5);else if(y>last+3)top.classList.remove('show');
      last=y},{passive:true});
    top.addEventListener('click',function(e){e.stopImmediatePropagation();var b=y0();
      scrollTo({top:scrollY>b+4?b:0,behavior:'smooth'})},true);
  }
})();
</script>
<!--/ux-->"""


def inject(html):
    a, b = html.find("<!--ux-->"), html.find("<!--/ux-->")
    if a >= 0 and b > a:
        return html[:a] + BLOCK + html[b + len("<!--/ux-->"):]
    g = html.find("<!--gloss-->")
    i = g if g >= 0 else html.rfind("</body>")
    return html[:i] + BLOCK + "\n" + html[i:] if i >= 0 else html + "\n" + BLOCK + "\n"


if __name__ == "__main__":
    for f in sys.argv[1:]:
        s = open(f, encoding="utf-8").read()
        open(f, "w", encoding="utf-8").write(inject(s))
        print("ux in", f)
