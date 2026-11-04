#!/usr/bin/env python3
"""Connect-your-league preview of The Daily Fantasizer.

Turns the published paper (docs/index.html) into a sample page for other commissioners:
  * every league name, manager name, crest, league ID and the Rule Changes API URL is replaced,
    so the page source carries nothing that identifies the Men Fantasizing league;
  * league-specific sections (This Week's Paper, League & Teams, the masthead crests) are blurred
    behind a "Link your league" overlay; Player Stats (NFL-wide data) stays readable;
  * Optimal Lineup (owner-only) and the home-screen app tags are removed;
  * Rule Changes and Betting tabs are grayed out and can't be opened;
  * a bar under the masthead offers "Link ESPN Fantasy account" (opens the setup sheet, test mode:
    nothing is sent anywhere) and "Link Yahoo Fantasy account" (disabled, coming soon).

Never touches docs/. Usage: python3 demo/demo.py [SRC] [OUT]
"""
import json, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "index.html"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "demo" / "connect-preview.html"
# --signin: the public front page of thedailyfantasizer.com (sync-paper.yml): same blur, but the box asks you to log in
SIGNIN = "--signin" in sys.argv

league = json.loads((ROOT / "league.json").read_text())
latest = json.loads((ROOT / "data" / "latest.json").read_text()) if (ROOT / "data" / "latest.json").exists() else {}

h = SRC.read_text()

# ---------- 1. strip things that must never leave the owner's site ----------
h = re.sub(r"<!--app-->.*?<!--/app-->", "", h, flags=re.S)          # home-screen app / service worker
h = re.sub(r"<!--LU-->.*?<!--/LU-->", "", h, flags=re.S)            # Optimal Lineup (owner only)
if league.get("proposals_api"):
    h = h.replace(league["proposals_api"], "")
h = h.replace(league["espn_url"], "#")
h = h.replace(str(league["league_id"]), "0")

# ---------- 2. crests -> one neutral shield ----------
shield = ("data:image/svg+xml;base64,"
          "PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCA0MCA0MCc+PHBhdGggZD0nTTIwIDMgMzUgOHYxMWMwIDktNiAxNS0xNSAxOEM1IDM0IDUgMjggNSAxOVY4eicgZmlsbD0nIzlhYTBhOCcvPjwvc3ZnPg==")
h = re.sub(r"data:image/(?:webp|png|jpe?g|gif);base64,[A-Za-z0-9+/=]+", shield, h)

# ---------- 3. names ----------
teams = {}  # id -> (full, abbr, owner)
raw = ROOT / "data" / f"week{latest.get('week', 8)}_raw.txt"
if not raw.exists():
    raw = sorted((ROOT / "data").glob("week*_raw.txt"), key=lambda p: int(re.findall(r"\d+", p.name)[0]))[-1]
lines = raw.read_text().splitlines()
i = lines.index("TEAMS") + 1
while i < len(lines) and re.match(r"^\d+\|", lines[i]):
    tid, full, abbr, owner = lines[i].split("|")[:4]
    teams[int(tid)] = (full, abbr, owner)
    i += 1

safe = {}    # replaced everywhere (long, distinctive strings)
risky = {}   # short tokens: only in page text and as exact quoted strings in scripts
for tid, (full, abbr, owner) in teams.items():
    short = league["short_names"].get(str(tid), full)
    for s, rep in ((full, f"Team {tid}"), (short, f"Team {tid}"), (owner, f"Manager {tid}")):
        (safe if len(s) >= 5 and not s.isupper() else risky)[s] = rep
    risky[abbr] = f"T{tid}"
    for part in owner.split():
        if len(part) >= 5 and part not in ("Adams", "Williams", "Michael", "Travis", "Samuel", "Nathan", "Aaron", "Tyler"):
            safe.setdefault(part, f"Manager {tid}")
safe[league["league_name"]] = "Your League"

def alt(keys):
    return "|".join(re.escape(k) for k in sorted(keys, key=len, reverse=True))

def apostrophe_variants(d):
    out = dict(d)
    for k, v in d.items():
        for a, b in (("’", "'"), ("'", "’"), ("'", "&#x27;"), ("'", "&#39;"), ("’", "&rsquo;")):
            if a in k:
                out.setdefault(k.replace(a, b), v)
        if "&" not in k and ("<" in k or ">" in k):
            pass
    return out

safe = apostrophe_variants(safe)
risky = apostrophe_variants(risky)

safe_re = re.compile(r"(?<![\w])(" + alt(safe) + r")(?![\w])")
h = safe_re.sub(lambda m: safe[m.group(1)], h)

risky_text_re = re.compile(r"(?<![\w#-])(" + alt(risky) + r")(?![\w-])")
risky_q_re = re.compile(r"""(["'])(""" + alt(risky) + r""")\1""")

def fix_text(chunk):
    # only between tags, never inside attribute values that are CSS/ids
    return re.sub(r">([^<]+)<", lambda m: ">" + risky_text_re.sub(lambda n: risky[n.group(1)], m.group(1)) + "<", chunk)

parts = re.split(r"(<script\b.*?</script>|<style\b.*?</style>)", h, flags=re.S)
for k, p in enumerate(parts):
    if p.startswith("<script") and 'type="application/json"' in p[:80]:
        parts[k] = risky_text_re.sub(lambda m: risky[m.group(1)], p)   # data only, no code
    elif p.startswith("<script"):
        parts[k] = risky_q_re.sub(lambda m: m.group(1) + risky[m.group(2)] + m.group(1), p)
    elif not p.startswith("<style"):
        parts[k] = fix_text(p)
        # aria-label / title attributes carry team names too
        parts[k] = re.sub(r'((?:aria-label|title|alt|data-name)=")([^"]*)(")',
                          lambda m: m.group(1) + risky_text_re.sub(lambda n: risky[n.group(1)], m.group(2)) + m.group(3), parts[k])
h = "".join(parts)

# masthead kicker
h = h.replace("Official paper of the Your League league", "Official paper of your league")

# ---------- 4. preview UI ----------
CSS = r"""
<style id="fz-demo-css">
.fz-cb{margin:18px 0 6px}
.fz-cb-in{background:var(--sheet);border:2px solid var(--rule);display:flex;flex-wrap:wrap;align-items:center;gap:12px 18px;padding:14px 16px}
.fz-cb-t{flex:1 1 260px;min-width:0}
.fz-cb-t b{display:block;font-family:var(--display);font-size:26px;line-height:1;text-transform:uppercase;letter-spacing:.01em}
.fz-cb-t span{font-family:var(--body);font-size:14px;color:var(--muted)}
.fz-cb-b{display:flex;flex-wrap:wrap;gap:10px}
.fz-btn{font:600 14px/1 var(--mono);text-transform:uppercase;letter-spacing:.03em;padding:13px 16px;min-height:44px;border:2px solid var(--rule);background:var(--blue);color:var(--blue-ink);cursor:pointer;display:inline-flex;align-items:center;gap:8px}
.fz-btn:hover{background:var(--honolulu)}
.fz-btn[disabled]{background:transparent;color:var(--muted);border-color:var(--line);cursor:not-allowed}
.fz-btn small{font-size:10px;letter-spacing:.06em;border:1px solid currentColor;padding:2px 5px}
@media (max-width:560px){.fz-cb-b{width:100%}.fz-btn{flex:1 1 100%;justify-content:center}}

/* blurred, league-specific content */
.fz-veil{position:relative!important;cursor:pointer}
.fz-veil>*{filter:blur(7px);pointer-events:none;user-select:none;-webkit-user-select:none}
.fz-veil::after{content:"Link your league to see this";position:absolute;left:50%;top:clamp(24px,50%,180px);transform:translate(-50%,-50%);
  background:var(--ink);color:var(--paper);font:600 12px/1.2 var(--mono);text-transform:uppercase;letter-spacing:.05em;padding:10px 14px;white-space:nowrap;z-index:3;pointer-events:none;box-shadow:4px 4px 0 var(--blue)}
.fz-veil.fz-sm::after{content:"Your league";padding:6px 10px;font-size:11px}
.mast .crests{filter:blur(4px)}

/* tabs that open after linking */
.tab.fz-off{opacity:.42;cursor:not-allowed;filter:grayscale(1)}
.to-league.fz-off{opacity:.45;filter:grayscale(1);cursor:not-allowed}
.to-league.fz-off em::after{content:" (after linking)"}

/* ESPN setup sheet */
.fz-dlg{border:2px solid var(--rule);background:var(--sheet);color:var(--ink);padding:0;width:min(560px,calc(100vw - 32px));max-height:calc(100vh - 32px)}
.fz-dlg::backdrop{background:rgba(14,17,23,.55)}
.fz-dlg form{padding:20px}
.fz-dlg h3{font-family:var(--display);font-size:30px;line-height:1;margin:0 0 6px;text-transform:uppercase}
.fz-dlg p{font-family:var(--body);font-size:14px;line-height:1.45;margin:0 0 14px;color:var(--muted)}
.fz-dlg label{display:block;font:600 12px/1.2 var(--mono);text-transform:uppercase;letter-spacing:.04em;margin:14px 0 6px}
.fz-dlg input[type=text]{width:100%;font:15px/1.3 var(--mono);padding:11px 12px;border:2px solid var(--line);background:var(--paper);color:var(--ink)}
.fz-dlg input[type=text]:focus{outline:none;border-color:var(--blue)}
.fz-dlg details{margin-top:14px;border-top:1px solid var(--line);padding-top:12px}
.fz-dlg summary{cursor:pointer;font:600 13px/1.3 var(--mono);text-transform:uppercase;letter-spacing:.03em}
.fz-dlg ol{font-family:var(--body);font-size:13px;line-height:1.5;color:var(--muted);padding-left:20px;margin:10px 0 0}
.fz-dlg .fz-row{display:flex;gap:10px;justify-content:flex-end;margin-top:18px;flex-wrap:wrap}
.fz-steps{font-family:var(--body);font-size:14px;line-height:1.5;padding-left:22px;margin:0 0 12px}.fz-steps li{margin:0 0 8px}.fz-steps b{color:var(--ink)}
.fz-small{font-size:12.5px!important}
.fz-dlg .fz-ghost{background:transparent;color:var(--ink)}
.fz-msg{font:13px/1.4 var(--mono);margin-top:12px;padding:10px 12px;border-left:4px solid var(--blue);background:var(--paper);display:none}
.fz-msg.err{border-color:var(--red)}
.fz-test{display:inline-block;font:600 10px/1 var(--mono);letter-spacing:.06em;text-transform:uppercase;background:var(--hi);color:var(--hi-ink);padding:4px 6px;margin-bottom:10px}
</style>
"""

BAR = r"""
<div class="fz-cb" id="fz-connect" contenteditable="false"><div class="fz-cb-in">
  <div class="fz-cb-t"><b>Print this paper for your league</b><span>This is a sample edition with the league's details blurred. Link your fantasy account and every section fills in with your league, in exactly this layout.</span></div>
  <div class="fz-cb-b">
    <button type="button" class="fz-btn" id="fz-espn">Link ESPN Fantasy account</button>
    <button type="button" class="fz-btn" id="fz-yahoo" disabled title="Yahoo is coming soon">Link Yahoo Fantasy account <small>Soon</small></button>
  </div>
</div></div>
<dialog class="fz-dlg" id="fz-espn-dlg" contenteditable="false" aria-labelledby="fz-espn-h"><form method="dialog" id="fz-espn-form" novalidate>
  <span class="fz-test">Preview · linking isn't live yet</span>
  <h3 id="fz-espn-h">Link your ESPN leagues</h3>
  <p>Works like FantasyPros' ESPN sync. ESPN has no sign-in for other websites, so a small Chrome extension does the hand-off.</p>
  <ol class="fz-steps">
    <li><b>Add the Daily Fantasizer extension</b> to Chrome or Edge on a computer (once).</li>
    <li><b>Press Link ESPN Fantasy account.</b> ESPN opens in a new tab; sign in with ESPN's own Log In button. Your password only goes to ESPN.</li>
    <li><b>Tick your leagues</b> in the Daily Fantasizer panel on the ESPN page. One account in several leagues? Each one gets its own paper.</li>
    <li><b>Press Add leagues.</b> You're back here with every league's paper printing. Share each link with that league; members just read it on their phones.</li>
  </ol>
  <p class="fz-small">Read-only: it never changes lineups, trades or settings. Signing out of ESPN everywhere ends the link.</p>
  <div class="fz-msg" id="fz-msg" role="status"></div>
  <div class="fz-row"><button type="button" class="fz-btn fz-ghost" id="fz-cancel">Close</button><button type="submit" class="fz-btn" id="fz-go">Link ESPN Fantasy account</button></div>
</form></dialog>
"""

JS = r"""
<script id="fz-demo-js">
(function(){
  var OFF=['tab-props','tab-bets'], OFFP=['proposals','betting'];
  function $(s,r){return (r||document).querySelector(s)}
  function $$(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s))}
  var dlg=$('#fz-espn-dlg');
  function openEspn(){ if(dlg&&dlg.showModal){ if(!dlg.open) dlg.showModal(); setTimeout(function(){var i=$('#fz-lg');i&&i.focus()},30) } }

  // gray out Rule Changes and Betting
  OFF.forEach(function(id){var t=document.getElementById(id); if(!t) return;
    t.classList.add('fz-off'); var ts=t.querySelector('.tab-s'); if(ts) ts.textContent='After linking'; t.setAttribute('aria-disabled','true'); t.setAttribute('tabindex','-1'); t.title='Opens after you link your league'});
  $$('a.to-league').forEach(function(a){var k=a.getAttribute('data-tab')||(a.getAttribute('href')||'').slice(1); if(OFFP.indexOf(k)>=0){a.classList.add('fz-off');a.setAttribute('aria-disabled','true')}});
  function blocked(el){return el&&el.closest&&el.closest('.tab.fz-off, a.to-league.fz-off')}
  ['click','keydown','pointerdown','touchstart'].forEach(function(ev){
    document.addEventListener(ev,function(e){ if(ev==='keydown'&&e.key!=='Enter'&&e.key!==' ') return;
      if(blocked(e.target)){e.preventDefault();e.stopImmediatePropagation();}},true)});
  // keep arrow-key tab navigation and stale links from landing on a locked tab
  function guard(){ OFFP.forEach(function(p){var el=document.getElementById(p);
    if(el&&!el.hidden){var t=document.getElementById('tab-paper'); t&&t.click()}}) }
  if(OFFP.indexOf(location.hash.slice(1))>=0){ history.replaceState(null,'',location.pathname) }
  new MutationObserver(guard).observe(document.body,{subtree:true,attributes:true,attributeFilter:['hidden']});
  guard();

  // blur league-specific sections
  var VEIL=['#paper > *:not(.to-league)', '#league > section'];
  VEIL.forEach(function(sel){ $$(sel).forEach(function(el){ if(el.tagName==='STYLE'||el.tagName==='SCRIPT') return;
    el.classList.add('fz-veil'); if(el.getBoundingClientRect().height<140) el.classList.add('fz-sm');
    el.addEventListener('click',openEspn); }) });

  // connect buttons
  var b=$('#fz-espn'); b&&b.addEventListener('click',openEspn);
  $('#fz-cancel').addEventListener('click',function(){dlg.close()});
  var msg=$('#fz-msg');
  function say(t,err){msg.textContent=t;msg.className='fz-msg'+(err?' err':'');msg.style.display='block'}
  // Same hand-off as the live site: the extension marks the page and answers a postMessage.
  window.addEventListener('message',function(e){ if(e.source!==window||!e.data||e.data.fz!=='espn-link-result') return;
    var r=e.data; if(r.pending) return say('An ESPN tab is open. Sign in there, tick your leagues and press Add leagues.');
    if(r.ok&&r.next) location.assign(r.next); else say(r.error||'That didn\u2019t work. Try again.',true) });
  $('#fz-espn-form').addEventListener('submit',function(e){
    e.preventDefault();
    if(document.documentElement.dataset.fzExt){ window.postMessage({fz:'espn-link'},location.origin); return }
    say('This is the preview, so the button can\u2019t link yet. On the live site it opens ESPN in a new tab, as described above.');
  });
})();
</script>
"""

if SIGNIN:
    BAR = r"""
<div class="fz-cb" id="fz-connect" contenteditable="false"><div class="fz-cb-in">
  <div class="fz-cb-t"><b>Log in to read the paper</b><span>The Daily Fantasizer is for league members. Log in with the ESPN account that's in your league and every section opens with your league, every Tuesday.</span></div>
  <div class="fz-cb-b">
    <a class="fz-btn" id="fz-espn" href="/login?next=/" style="text-decoration:none">Log in with ESPN</a>
    <button type="button" class="fz-btn" disabled title="Yahoo is coming soon">Log in with Yahoo <small>Soon</small></button>
  </div>
</div></div>
"""
    JS = JS.replace("""  var dlg=$('#fz-espn-dlg');
  function openEspn(){ if(dlg&&dlg.showModal){ if(!dlg.open) dlg.showModal(); setTimeout(function(){var i=$('#fz-lg');i&&i.focus()},30) } }""",
                    """  function openEspn(){ location.href='/login?next=/' }""")
    JS = JS[:JS.index("  // connect buttons")] + "})();\n</script>\n"
    JS = JS.replace("'After linking'", "'After you log in'").replace("'Opens after you link your league'", "'Opens after you log in'")
    CSS = CSS.replace('.tab.fz-off .tab-s::after{content:" · after linking"}', '')
    CSS = CSS.replace('content:"Link your league to see this"', 'content:"Log in to see this"')
    h = h.replace("<title>The Daily Fantasizer</title>", "<title>The Daily Fantasizer</title>", 1)

h = h.replace("</header>", "</header>" + BAR, 1)
h = re.sub(r"(</title>)", lambda m: m.group(1) + CSS, h, count=1)
h = h.rstrip() + "\n" + JS

OUT.write_text(h)

# ---------- 5. leak check ----------
leaks = []
for tid, (full, abbr, owner) in teams.items():
    for s in (full, owner, league["short_names"].get(str(tid), "")):
        if len(s) >= 5 and s in h:
            leaks.append(s)
for s in (league["league_name"], str(league["league_id"]), "script.google.com"):
    if s in h:
        leaks.append(s)
print(f"wrote {OUT} ({len(h)//1024} KB); leaks: {sorted(set(leaks)) or 'none'}")
