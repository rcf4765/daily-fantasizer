#!/usr/bin/env python3
"""The sign-in gate on the league website's homepage (docs/index.html), added by publish_site.py.

While ESPN / Yahoo sign-in is being built, the homepage opens with the league's sections blurred and three buttons
under the masthead:
  Link ESPN Fantasy account   → the sign-up site's "Log in with ESPN" page (SIGNUP below)
  Link Yahoo Fantasy account  → grayed out ("Soon")
  Continue to Men Fantasizing league → un-blurs the paper and unlocks Rule Changes and Betting
Continue is remembered in that browser (localStorage), so league members tap it once. The edition itself is not
changed: everything lives between <!--gate--> and <!--/gate--> markers (three blocks), so it can be removed or
re-applied without touching the design. Only docs/index.html gets it; docs/weekN.html stay plain.

Usage: python3 gate.py FILE...   (idempotent)   ·   python3 gate.py --remove FILE...
"""
import pathlib
import re
import sys

SIGNUP = "https://fantasizer.m5njj556g4.workers.dev"   # the any-league site (multi/worker); its login page is /login

CSS = r"""<!--gate--><script>try{if(localStorage.getItem('fz-continue')!=='1')document.documentElement.classList.add('fz-gated')}catch(e){document.documentElement.classList.add('fz-gated')}</script>
<style id="fz-gate-css">
.fz-cb{display:none;margin:18px 0 6px}
html.fz-gated .fz-cb{display:block}
.fz-cb-in{background:var(--sheet);border:2px solid var(--rule);display:flex;flex-wrap:wrap;align-items:center;gap:14px 22px;padding:16px}
.fz-cb-t{flex:1 1 260px;min-width:0}
.fz-cb-t b{display:block;font-family:var(--display);font-size:28px;line-height:1;text-transform:uppercase;letter-spacing:.01em;margin-bottom:6px}
.fz-cb-t span{font-family:var(--body);font-size:14px;color:var(--muted)}
.fz-cb-b{display:flex;flex-direction:column;gap:10px;flex:0 1 330px;min-width:0}
.fz-btn{font:600 14px/1.15 var(--mono);text-transform:uppercase;letter-spacing:.03em;padding:12px 16px;min-height:46px;border:2px solid var(--rule);background:var(--blue);color:var(--blue-ink);cursor:pointer;display:flex;align-items:center;justify-content:center;gap:8px;text-align:center;width:100%}
.fz-btn:hover{background:var(--honolulu)}
.fz-btn[disabled]{background:transparent;color:var(--muted);border-color:var(--line);cursor:not-allowed}
.fz-btn small{font-size:10px;letter-spacing:.06em;border:1px solid currentColor;padding:2px 5px}
.fz-btn.fz-go{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.fz-btn.fz-go:hover{background:var(--honolulu);border-color:var(--honolulu);color:#fff}
@media (max-width:560px){.fz-cb-b{flex-basis:100%}}
html.fz-gated #paper > :not(.to-league):not(style):not(script),
html.fz-gated #league > section{position:relative;cursor:pointer}
html.fz-gated #paper > :not(.to-league):not(style):not(script) > *,
html.fz-gated #league > section > *{filter:blur(7px);pointer-events:none;user-select:none;-webkit-user-select:none}
html.fz-gated #paper > section::after,html.fz-gated #paper > .tiles::after,html.fz-gated #league > section::after{content:"Link your league to see this";position:absolute;left:50%;top:clamp(24px,50%,180px);transform:translate(-50%,-50%);
  background:var(--ink);color:var(--paper);font:600 12px/1.2 var(--mono);text-transform:uppercase;letter-spacing:.05em;padding:10px 14px;white-space:nowrap;z-index:3;pointer-events:none;box-shadow:4px 4px 0 var(--blue)}
html.fz-gated .mast .crests{filter:blur(4px)}
html.fz-gated #tab-props,html.fz-gated #tab-bets{opacity:.42;cursor:not-allowed;filter:grayscale(1)}
html.fz-gated a.to-league[data-tab="proposals"],html.fz-gated a.to-league[data-tab="betting"]{opacity:.45;filter:grayscale(1);cursor:not-allowed}
.fz-dlg{border:2px solid var(--rule);background:var(--sheet);color:var(--ink);padding:22px;width:min(520px,calc(100vw - 32px))}
.fz-dlg::backdrop{background:rgba(14,17,23,.55)}
.fz-dlg h3{font-family:var(--display);font-size:30px;line-height:1;margin:0 0 10px;text-transform:uppercase}
.fz-dlg p{font-family:var(--body);font-size:15px;line-height:1.5;margin:0 0 14px;color:var(--muted)}
.fz-dlg .fz-row{display:flex;flex-wrap:wrap;gap:10px}
.fz-dlg .fz-row .fz-btn{width:auto;flex:1 1 180px}
</style><!--/gate-->"""

BAR = r"""<!--gate--><div class="fz-cb" id="fz-connect" contenteditable="false"><div class="fz-cb-in">
  <div class="fz-cb-t"><b>Print this paper for your league</b><span>Link your fantasy account and every section fills in with your own league, in exactly this layout. In Men Fantasizing? Continue to your paper.</span></div>
  <div class="fz-cb-b">
    <a class="fz-btn" id="fz-espn" href="SIGNUP_URL/login" style="text-decoration:none">Link ESPN Fantasy account</a>
    <button type="button" class="fz-btn" disabled title="Yahoo is coming soon">Link Yahoo Fantasy account <small>Soon</small></button>
    <button type="button" class="fz-btn fz-go" id="fz-continue">Continue to Men Fantasizing league</button>
  </div>
</div></div>
<dialog class="fz-dlg" id="fz-espn-dlg" contenteditable="false" aria-labelledby="fz-espn-h">
  <h3 id="fz-espn-h">ESPN sign-in is almost ready</h3>
  <p>Soon you'll log in with your ESPN account here and get this paper, every Tuesday, for every league you're in. We're testing the sign-in now.</p>
  <div class="fz-row"><button type="button" class="fz-btn fz-go" id="fz-dlg-go">Continue to Men Fantasizing league</button><button type="button" class="fz-btn" id="fz-dlg-close" style="background:transparent;color:var(--ink)">Close</button></div>
</dialog><!--/gate-->"""

JS = r"""<!--gate--><script id="fz-gate-js">
(function(){
  var R=document.documentElement, LOCK=['tab-props','tab-bets'], LOCKP=['proposals','betting'];
  function gated(){return R.classList.contains('fz-gated')}
  function $(id){return document.getElementById(id)}
  var dlg=$('fz-espn-dlg');
  function espn(){ location.href=SIGNUP_JS+'/login' }
  function go(){ try{localStorage.setItem('fz-continue','1')}catch(e){} R.classList.remove('fz-gated'); if(dlg&&dlg.open) dlg.close(); window.scrollTo(0,0) }
  $('fz-continue')&&$('fz-continue').addEventListener('click',go);
  $('fz-dlg-go')&&$('fz-dlg-go').addEventListener('click',go);
  $('fz-dlg-close')&&$('fz-dlg-close').addEventListener('click',function(){dlg.close()});
  // while gated: blurred sections open the ESPN note; Rule Changes and Betting stay shut
  document.addEventListener('click',function(e){ if(!gated()) return;
    var t=e.target;
    if(t.closest&&t.closest('#tab-props,#tab-bets,a.to-league[data-tab="proposals"],a.to-league[data-tab="betting"]')){e.preventDefault();e.stopImmediatePropagation();return}
    if(t.closest&&t.closest('#paper > :not(.to-league), #league > section')&&!t.closest('#fz-connect')){e.preventDefault();e.stopImmediatePropagation();espn()}
  },true);
  function guard(){ if(!gated()) return; LOCKP.forEach(function(p){var el=$(p); if(el&&!el.hidden){var t=$('tab-paper'); t&&t.click()}}) }
  new MutationObserver(guard).observe(document.body,{subtree:true,attributes:true,attributeFilter:['hidden']});
  guard();
})();
</script><!--/gate-->"""


def remove(html):
    return re.sub(r"\n?<!--gate-->.*?<!--/gate-->", "", html, flags=re.S)


def add(html):
    html = remove(html)
    bar, js = BAR.replace("SIGNUP_URL", SIGNUP), JS.replace("SIGNUP_JS", repr(SIGNUP))
    i = html.find("</title>")
    j = html.find("</header>")
    if i < 0 or j < 0:
        sys.exit("page has no <title> or masthead </header>; can't add the sign-in gate")
    i += len("</title>")
    html = html[:i] + "\n" + CSS + html[i:]
    j = html.find("</header>") + len("</header>")
    html = html[:j] + "\n" + bar + html[j:]
    return html.rstrip() + "\n" + js + "\n"


if __name__ == "__main__":
    args = sys.argv[1:]
    rm = args and args[0] == "--remove"
    for f in (args[1:] if rm else args):
        p = pathlib.Path(f)
        p.write_text((remove if rm else add)(p.read_text(encoding="utf-8")), encoding="utf-8")
        print(("removed gate from " if rm else "gate on ") + p.name)
