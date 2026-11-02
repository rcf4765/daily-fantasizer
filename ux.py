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
4. Bigger touch targets on phones and tablets for the tabbed-group switches, week/view buttons, team tabs and
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
