// Every page of the sign-up site, in the paper's own look (ink, newsprint, Big Shoulders + Literata).
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const CSS = `
:root{--paper:#e3e6de;--sheet:#f4f5f0;--ink:#151a24;--muted:#59606c;--line:#c9cdc3;--blue:#1c3fae;--acc:#33658a;--hi:#ffd23f;--red:#b3261e;--ok:#1f7a4d}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#0e1117;--sheet:#161b24;--ink:#e8eaee;--muted:#9aa3b0;--line:#2b3340;--blue:#6f8dff;--acc:#6aa5cf;--red:#ff7b72;--ok:#5bd394}}
:root[data-theme="dark"]{--paper:#0e1117;--sheet:#161b24;--ink:#e8eaee;--muted:#9aa3b0;--line:#2b3340;--blue:#6f8dff;--acc:#6aa5cf;--red:#ff7b72;--ok:#5bd394}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.55 Literata,Georgia,serif}
.sheet{max-width:880px;margin:0 auto;padding:28px 16px 48px}
@media(min-width:720px){.sheet{margin:24px auto;padding:36px 40px 56px;background:var(--sheet);box-shadow:0 1px 0 var(--line)}}
.kicker{font:600 .72rem/1.3 "IBM Plex Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
h1,h2,h3{font-family:"Big Shoulders Display",Impact,sans-serif;font-weight:900;text-transform:uppercase;letter-spacing:.01em;margin:0;line-height:.95}
h1{font-size:clamp(2.6rem,11vw,5.4rem)}h1 span{color:var(--blue);display:block}
h2{font-size:clamp(1.7rem,6vw,2.4rem);margin:34px 0 12px;padding-top:12px;border-top:6px solid var(--ink);position:relative}
h2::after{content:"";position:absolute;left:0;top:-6px;width:56px;height:6px;background:var(--acc)}
h3{font-size:1.5rem}
.mast{padding-bottom:16px;border-bottom:8px solid var(--ink);box-shadow:0 5px 0 var(--sheet),0 9px 0 var(--acc);margin-bottom:26px}
.lede{font-size:1.15rem;max-width:40em;margin:14px 0 0}
.grid{display:grid;gap:16px}@media(min-width:720px){.grid.two{grid-template-columns:1fr 1fr}}
.card{border:3px solid var(--ink);background:var(--sheet);padding:18px;display:grid;gap:10px;align-content:start;border-top-width:8px}
.card.y{border-top-color:#6001d2}.card.e{border-top-color:#d00}
.card p{margin:0}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:44px;padding:10px 18px;border:2px solid var(--ink);background:var(--ink);color:var(--sheet);font:700 .95rem/1 "IBM Plex Mono",ui-monospace,monospace;text-transform:uppercase;letter-spacing:.06em;text-decoration:none;cursor:pointer;border-radius:0}
.btn.alt{background:transparent;color:var(--ink)}.btn.y{background:#6001d2;border-color:#6001d2;color:#fff}.btn.danger{background:transparent;color:var(--red);border-color:var(--red)}
.btn:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid var(--hi);outline-offset:2px}
label{display:grid;gap:6px;margin:12px 0}
input[type=text],input[type=number],input[type=password]{width:100%;min-height:44px;padding:10px 12px;border:2px solid var(--ink);background:var(--paper);color:var(--ink);font:500 1rem/1.2 "IBM Plex Mono",ui-monospace,monospace;border-radius:0}
.hint{font-size:.9rem;color:var(--muted);margin:0}
details{border:2px solid var(--line);padding:12px 14px;margin:14px 0;background:var(--paper)}summary{cursor:pointer;font-weight:600}
ol.steps{counter-reset:s;list-style:none;padding:0;margin:0;display:grid;gap:12px}
ol.steps li{counter-increment:s;display:grid;grid-template-columns:44px 1fr;gap:12px;align-items:start}
ol.steps li::before{content:counter(s);font:900 1.6rem/44px "Big Shoulders Display",Impact,sans-serif;text-align:center;background:var(--acc);color:#fff}
.err{border-left:6px solid var(--red);padding:10px 14px;background:var(--paper);margin:12px 0}
.note{border-left:6px solid var(--acc);padding:10px 14px;background:var(--paper);margin:12px 0}
.row{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.lg-list{display:grid;gap:10px;margin:0;padding:0;list-style:none}
.lg-list li{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center;border:2px solid var(--ink);padding:12px 14px;background:var(--sheet)}
.badge{display:inline-block;font:600 .66rem/1 "IBM Plex Mono",monospace;letter-spacing:.1em;text-transform:uppercase;padding:4px 6px;border:1.5px solid currentColor;color:var(--acc);margin-left:6px;vertical-align:middle}
.toggle{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center;border:2px solid var(--ink);padding:14px;background:var(--sheet);margin:10px 0}
.toggle input{width:26px;height:26px;accent-color:var(--blue)}
.toggle p{margin:4px 0 0;color:var(--muted);font-size:.92rem}
.sw{display:flex;flex-wrap:wrap;gap:8px}.sw label{margin:0;display:block}.sw input{position:absolute;opacity:0}
.sw span{display:block;width:44px;height:44px;border:3px solid var(--sheet);outline:2px solid var(--line)}
.sw input:checked+span{outline:3px solid var(--ink)}.sw input:focus-visible+span{outline:3px solid var(--hi)}
.code{font:700 1.4rem/1 "IBM Plex Mono",monospace;letter-spacing:.08em;background:var(--paper);padding:12px 14px;border:2px dashed var(--ink);display:inline-block}
.share{display:grid;grid-template-columns:1fr auto;gap:8px}
footer{margin-top:44px;padding-top:12px;border-top:2px solid var(--ink);font:500 .78rem/1.5 "IBM Plex Mono",monospace;color:var(--muted)}
a{color:var(--blue)}
`;

export function layout(title, body, { head = '' } = {}) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(title)}</title><meta name="color-scheme" content="light dark">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@800;900&family=IBM+Plex+Mono:wght@500;600;700&family=Literata:wght@400;600&display=swap">
<style>${CSS}</style>${head}</head><body><main class="sheet">${body}
<footer>The Daily Fantasizer · a weekly paper for your fantasy league · read-only: it never changes anything in your league</footer></main></body></html>`;
}

// The "Link ESPN Fantasy account" button: hands off to the browser extension when it's installed (it marks the page
// with data-fz-ext), otherwise shows how to get it. Any page can include it next to a [data-espn-link] button.
export const ESPN_LINK_UI = `<div class="note" id="fz-espn-status" role="status" hidden></div>
<dialog id="fz-ext-dlg" style="border:3px solid var(--ink);background:var(--sheet);color:var(--ink);max-width:min(560px,calc(100vw - 32px));padding:22px">
 <h3>Add the Chrome extension first</h3>
 <p>ESPN has no sign-in for other websites. Like FantasyPros, The Daily Fantasizer uses a small Chrome extension to read the leagues on your ESPN account after you sign in on ESPN's own page. It's read-only and only talks to this site.</p>
 <ol class="hint"><li>Use Chrome or Edge on a computer.</li><li><a href="/extension.zip">Download the extension</a> and unzip it.</li><li>Open <b>chrome://extensions</b>, turn on <b>Developer mode</b> (top right), click <b>Load unpacked</b> and pick the unzipped folder.</li><li>Come back to this page and press <b>Link ESPN Fantasy account</b> again.</li></ol>
 <p class="row"><button class="btn alt" type="button" onclick="this.closest('dialog').close()">Close</button><a class="btn alt" href="/espn">Enter a league ID instead</a></p>
</dialog>
<script>(function(){
 var st=document.getElementById('fz-espn-status');
 function say(t){st.textContent=t;st.hidden=!t}
 document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('[data-espn-link]');if(!b)return;
  if(!document.documentElement.dataset.fzExt){var d=document.getElementById('fz-ext-dlg');d.showModal?d.showModal():location.assign('/espn');return}
  say('An ESPN tab is open. Sign in there, tick your leagues and press Add leagues.');
  window.postMessage({fz:'espn-link'},location.origin)});
 window.addEventListener('message',function(e){if(e.source!==window||!e.data||e.data.fz!=='espn-link-result')return;
  var r=e.data;if(r.pending)return;if(r.ok&&r.next){say('Linked. Opening your leagues…');location.assign(r.next)}else say(r.error||'That didn’t work. Try again.')});
})();</script>`;

const mast = (kicker) => `<header class="mast"><span class="kicker">${esc(kicker)}</span><h1>The Daily<span>Fantasizer</span></h1></header>`;

export function home(env, signedIn) {
  return layout('The Daily Fantasizer: a newspaper for your fantasy league', `${mast('A newspaper for your fantasy football league')}
<p class="lede">Every Tuesday, a fresh edition built from your league's real games: upsets, bench blunders, power rankings, playoff odds, a player desk and next week's lines. Share one link with your league.</p>
<h2>Start here</h2>
<div class="grid two">
 <section class="card y"><span class="kicker">Yahoo leagues</span><h3>Sign in with Yahoo</h3>
  <p>Yahoo asks you to approve read-only access to your fantasy leagues. Then pick the league.</p>
  <p><a class="btn y" href="/auth/yahoo">Sign in with Yahoo</a></p></section>
 <section class="card e"><span class="kicker">ESPN leagues</span><h3>Link your ESPN account</h3>
  <p>Sign in on ESPN and tick the leagues you want: every league on your account can get its own paper. Needs our free Chrome extension, once, on a computer.</p>
  <p class="row"><button class="btn" type="button" data-espn-link>Link ESPN Fantasy account</button></p>
  <p class="hint">No computer handy? <a href="/espn">Enter a league ID instead</a>.</p></section>
</div>
<h2>How it works</h2>
<ol class="steps">
 <li><div><b>Connect your league.</b> Anyone in the league can set it up; only the commissioner can change its settings.</div></li>
 <li><div><b>Get your link.</b> The first paper prints in a few minutes. Share the link in your group chat.</div></li>
 <li><div><b>A new edition every Tuesday</b> after Monday Night Football, with last week's archive kept.</div></li>
</ol>
${ESPN_LINK_UI}
${signedIn ? '<p class="row" style="margin-top:22px"><a class="btn alt" href="/mine">My leagues</a><a class="btn alt" href="/signout">Sign out</a></p>' : ''}`);
}

export function espnForm({ error = '', leagueId = '', season = '' } = {}) {
  const yr = season || new Date().getUTCFullYear() - (new Date().getUTCMonth() < 6 ? 1 : 0);
  return layout('Set up an ESPN league · The Daily Fantasizer', `${mast('ESPN league setup')}
${error ? `<div class="err" role="alert">${esc(error)}</div>` : ''}
<form method="post" action="/espn">
 <label><span class="kicker">League ID or league link</span>
  <input type="text" name="league" required value="${esc(leagueId)}" placeholder="e.g. 1234567 or https://fantasy.espn.com/football/league?leagueId=1234567" autocomplete="off" inputmode="url"></label>
 <p class="hint">Open your league on fantasy.espn.com; the number after <b>leagueId=</b> in the address bar is the ID.</p>
 <label><span class="kicker">Season</span><input type="number" name="season" value="${esc(yr)}" min="2018" max="2100"></label>
 <details ${error.includes('private') || error.includes('cookies') ? 'open' : ''}><summary>Private league, or you're the commissioner? Add your ESPN cookies</summary>
  <p class="hint" style="margin-top:10px">Needed for private leagues, and to prove you're the commissioner (only the commissioner can turn on Rule Changes and Betting). They're stored encrypted, used only to read your league, and never shown again. They work like a password for your ESPN account; signing out of ESPN everywhere cancels them.</p>
  <ol class="hint"><li>On a computer, sign in at fantasy.espn.com.</li><li>Open developer tools (F12, or right-click › Inspect) › <b>Application</b> (Chrome/Edge) or <b>Storage</b> (Firefox) › Cookies › https://fantasy.espn.com.</li><li>Copy the values of <b>espn_s2</b> and <b>SWID</b> (SWID includes the curly braces).</li></ol>
  <label><span class="kicker">espn_s2</span><input type="password" name="espn_s2" autocomplete="off" spellcheck="false"></label>
  <label><span class="kicker">SWID</span><input type="password" name="swid" autocomplete="off" spellcheck="false" placeholder="{XXXXXXXX-XXXX-…}"></label>
 </details>
 <p><button class="btn" type="submit">Make the paper</button></p>
</form>
<p class="hint"><a href="/">← Back</a></p>`);
}

export function pickYahoo(leagues, existing) {
  const items = leagues.length ? leagues.map((l) => `<li><div><b>${esc(l.name)}</b>${l.commissioner ? '<span class="badge">Commissioner</span>' : ''}<br><span class="hint">${l.teams} teams · ${l.season} · your team: ${esc(l.team || '—')}</span></div>
<form method="post" action="/yahoo/league"><input type="hidden" name="key" value="${esc(l.key)}"><button class="btn" type="submit">${existing[l.key] ? 'Open paper' : 'Make the paper'}</button></form></li>`).join('')
    : '<li><div>No Yahoo football leagues found for this season on that account.</div></li>';
  return layout('Pick your league · The Daily Fantasizer', `${mast('Your Yahoo leagues')}<ul class="lg-list">${items}</ul><p class="hint" style="margin-top:16px"><a href="/">← Back</a></p>`);
}

export function status(L, meta, isComm) {
  const st = L.status || 'queued';
  const msg = { queued: 'Your first paper is queued at the printer. This usually takes 3 to 10 minutes.', building: 'The presses are running. Check back in a few minutes.',
    waiting: 'No week has finished yet this season. The first paper prints the Tuesday after week 1.', error: `The last print run failed: ${L.status_msg || 'unknown error'}.` }[st] || '';
  return layout(`${L.name} · The Daily Fantasizer`, `${mast(L.name)}
<div class="${st === 'error' ? 'err' : 'note'}" role="status">${esc(msg)}</div>
<script>setTimeout(function(){location.reload()},45000)</script>
${isComm ? `<p class="row"><a class="btn" href="/l/${esc(L.slug)}/settings">Settings</a></p>` : ''}`);
}

const ACCENTS = [['#33658a', 'Steel'], ['#0076b6', 'Honolulu'], ['#2d6a4f', 'Forest'], ['#8a3b12', 'Rust'], ['#6b2fa3', 'Grape'], ['#b3261e', 'Brick'], ['#c47f00', 'Gold'], ['#3d3d3d', 'Graphite']];

export function settings(env, L, { code = '', saved = false, verifyMsg = '' } = {}) {
  const link = `${env.SITE_URL}/l/${L.slug}/`;
  return layout(`Settings · ${L.name}`, `${mast(`${L.name} · commissioner settings`)}
${saved ? '<div class="note" role="status">Saved. The paper is being reprinted with your changes; that takes a few minutes.</div>' : ''}
${verifyMsg ? `<div class="note">${esc(verifyMsg)}</div>` : ''}
<h2>Share</h2>
<div class="share"><input type="text" readonly value="${esc(link)}" id="lnk" aria-label="Link to your league's paper"><button class="btn" type="button" onclick="navigator.clipboard&&navigator.clipboard.writeText(document.getElementById('lnk').value);this.textContent='Copied'">Copy</button></div>
<p class="hint">Anyone with the link can read the paper. Last printed: ${L.last_built_at ? esc(L.last_built_at.slice(0, 16).replace('T', ' ')) + ' UTC, week ' + esc(L.last_week) : 'not yet'}.</p>
<form method="post" action="/l/${esc(L.slug)}/settings">
<h2>Optional tabs</h2>
<label class="toggle"><span><b>Rule Changes</b><p>Teams propose scoring, rule and settings changes and vote; a majority of ${L.teams} teams passes one. You set passed changes in ${L.platform === 'yahoo' ? 'Yahoo' : 'ESPN'} yourself.</p></span><input type="checkbox" name="rules" ${L.feat_rules ? 'checked' : ''}></label>
<label class="toggle"><span><b>Betting</b><p>A side game: each team bets up to 5 of its own points a week on player props, league matchups and NFL games. Real league scores never change.</p></span><input type="checkbox" name="bets" ${L.feat_bets ? 'checked' : ''}></label>
<h2>Color</h2>
<div class="sw" role="radiogroup" aria-label="Accent color">${ACCENTS.map(([c, n]) => `<label title="${n}"><input type="radio" name="accent" value="${c}" ${L.accent === c ? 'checked' : ''} aria-label="${n}"><span style="background:${c}"></span></label>`).join('')}</div>
<p style="margin-top:22px"><button class="btn" type="submit">Save and reprint</button></p>
</form>
${(L.feat_rules || L.feat_bets) ? `<h2>Commissioner code</h2>
<p>The paper's Commissioner panel (bottom of ${L.feat_rules ? 'Rule Changes' : 'Your Team'}) asks for this code to reset a team's sign-in or withdraw a proposal.</p>
${code ? `<p class="code">${esc(code)}</p><p class="hint">Write it down: it won't be shown again. Making a new one replaces it.</p>` : ''}
<form method="post" action="/l/${esc(L.slug)}/code"><button class="btn alt" type="submit">${L.comm_code_hash ? 'Make a new code' : 'Make a code'}</button></form>` : ''}
<h2>Printing</h2>
<form method="post" action="/l/${esc(L.slug)}/rebuild" class="row"><button class="btn alt" type="submit">Reprint now</button><span class="hint">New editions print automatically every Tuesday.</span></form>
<details><summary>Remove this league</summary><p class="hint">Deletes every paper, sign-in, vote and bet for this league from the site. Nothing changes in ${L.platform === 'yahoo' ? 'Yahoo' : 'ESPN'}.</p>
<form method="post" action="/l/${esc(L.slug)}/delete" onsubmit="return confirm('Remove ${esc(L.name).replace(/'/g, '')} and all its papers?')"><button class="btn danger" type="submit">Remove league</button></form></details>
<p class="hint" style="margin-top:22px"><a href="/l/${esc(L.slug)}/">Open the paper</a> · <a href="/mine">My leagues</a></p>`);
}

export function mine(rows, { added = 0, failed = [] } = {}) {
  const flash = (added ? `<div class="note" role="status">Added ${added} league${added > 1 ? 's' : ''}. Each first paper prints in a few minutes; share each league's link from its Settings.</div>` : '')
    + failed.map((f) => `<div class="err">${esc(f)}</div>`).join('');
  return layout('My leagues · The Daily Fantasizer', `${mast('My leagues')}${flash}<ul class="lg-list">${rows.length ? rows.map((L) => `<li><div><b>${esc(L.name)}</b>${L.is_comm ? '<span class="badge">Commissioner</span>' : ''}<br><span class="hint">${L.platform === 'yahoo' ? 'Yahoo' : 'ESPN'} · ${L.teams} teams</span></div><div class="row"><a class="btn alt" href="/l/${esc(L.slug)}/">Paper</a>${L.is_comm ? `<a class="btn alt" href="/l/${esc(L.slug)}/settings">Settings</a>` : ''}</div></li>`).join('') : '<li><div>No leagues yet.</div></li>'}</ul>
<p class="row" style="margin-top:16px"><a class="btn" href="/">Add a league</a><button class="btn alt" type="button" data-espn-link>Add more ESPN leagues</button><a class="btn alt" href="/signout">Sign out</a></p>${ESPN_LINK_UI}`);
}

export function message(title, text, back = '/') {
  return layout(`${title} · The Daily Fantasizer`, `${mast(title)}<p class="lede">${esc(text)}</p><p style="margin-top:20px"><a class="btn alt" href="${esc(back)}">Back</a></p>`);
}

export function archive(L, weeks) {
  return layout(`${L.name} · every edition`, `${mast(`${L.name} · every edition`)}<ul class="lg-list">${weeks.map((w) => `<li><div><b>Week ${w}</b></div><a class="btn alt" href="/l/${esc(L.slug)}/week${w}.html">Read</a></li>`).join('') || '<li><div>No editions yet.</div></li>'}</ul><p class="hint" style="margin-top:16px"><a href="/l/${esc(L.slug)}/">← Latest edition</a></p>`);
}
