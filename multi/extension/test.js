const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const send = (msg) => new Promise((res) => chrome.runtime.sendMessage(msg, (r) => res(chrome.runtime.lastError ? null : r)));

async function status() {
  const s = await send({ type: 'test-status' });
  if (!s) return;
  $('ver').textContent = s.version; $('season').textContent = s.season;
  $('signed').innerHTML = s.signedIn ? `<span class="ok">Signed in</span> <small class="k">SWID ${esc(s.swid)}</small>` : '<span class="warn">Signed out</span>';
}

function leagueCard(r) {
  const passed = r.checks.filter((c) => c.pass).length;
  const d = r.data || {};
  const sett = d.settings ? Object.entries(d.settings).map(([k, v]) => `<tr><th>${esc(k)}</th><td>${esc(v ?? '—')}</td></tr>`).join('') : '';
  const stand = (d.standings || []).map((t, i) => `<tr><td>${i + 1}</td><td>${esc(t.name)}</td><td class="n">${t.w}-${t.l}</td><td class="n">${t.pf}</td></tr>`).join('');
  const games = (d.lastWeek || []).map((g) => `<tr><td>${esc(g.away)}</td><td class="n">${esc(g.awayPts)}</td><td>@</td><td>${esc(g.home)}</td><td class="n">${esc(g.homePts)}</td></tr>`).join('');
  return `<div class="card lg"><span class="k">League ${esc(r.id)} · ${passed} of ${r.checks.length} checks passed</span>
    <h3>${esc(r.name || 'League ' + r.id)}</h3>
    <p class="m">${r.team ? 'Your team: ' + esc(r.team) : ''}${r.commissioner ? ' · commissioner' : ''}</p>
    <ul class="ck">${r.checks.map((c) => `<li class="${c.pass ? '' : 'no'}"><i>${c.pass ? '✓' : '✕'}</i><span>${esc(c.name)}<small>${esc(c.detail || '')}</small></span></li>`).join('')}</ul>
    ${sett ? `<details><summary>League settings</summary><table>${sett}</table></details>` : ''}
    ${stand ? `<details><summary>Standings</summary><table><tr><th>#</th><th>Team</th><th class="n">W-L</th><th class="n">PF</th></tr>${stand}</table></details>` : ''}
    ${games ? `<details><summary>Week ${esc(d.settings.lastCompletedWeek)} scores</summary><table>${games}</table></details>` : ''}</div>`;
}

async function render() {
  const { testResults: T, log = [], pending } = await chrome.storage.session.get(['testResults', 'log', 'pending']);
  $('busy').textContent = pending && pending.test ? 'Waiting on the ESPN tab…' : '';
  if (T && T.results && T.results.length) {
    $('results').innerHTML = `<p class="k">Read ${esc(T.at.replace('T', ' ').slice(0, 19))} UTC</p>` + T.results.map(leagueCard).join('');
    const all = T.results.every((r) => r.checks.length && r.checks.every((c) => c.pass));
    $('last').innerHTML = all ? `<span class="ok">${T.results.length} league${T.results.length > 1 ? 's' : ''}, all checks passed</span>` : '<span class="err">Some checks failed</span>';
  }
  $('log').innerHTML = log.map((e) => `<span class="${e.kind}">${esc(e.t.slice(11, 19))} ${esc(e.kind.toUpperCase().padEnd(4))} ${esc(e.text)}${e.ms ? ` (${e.ms} ms)` : ''}</span>`).join('\n') || '<span class="empty">Empty.</span>';
  $('log').scrollTop = 1e9;
  status();
}

$('go').onclick = async () => { const r = await send({ type: 'espn-link' }); if (r && !r.ok) alert(r.error); render(); };
$('read').onclick = async () => {
  const v = $('lid').value.trim(), m = v.match(/leagueId=(\d+)/) || v.match(/^(\d{3,12})$/);
  if (!m) return alert('That doesn’t look like an ESPN league ID.');
  $('read').disabled = true; $('read').textContent = 'Reading…';
  await send({ type: 'test-read', league: m[1] });
  $('read').disabled = false; $('read').textContent = 'Read league';
  location.hash = 'results';
};
$('clear').onclick = async () => { await chrome.storage.session.remove(['log', 'testResults']); $('results').innerHTML = '<p class="empty">Nothing read yet.</p>'; $('last').textContent = 'none yet'; render(); };
$('copy').onclick = async () => {
  const { testResults: T, log = [] } = await chrome.storage.session.get(['testResults', 'log']);
  const s = await send({ type: 'test-status' });
  const text = [`Daily Fantasizer ESPN test · extension ${s.version} · season ${s.season} · ${navigator.userAgent}`,
    ...((T && T.results) || []).map((r) => `League ${r.id} ${r.name || ''}: ` + r.checks.map((c) => `${c.pass ? 'PASS' : 'FAIL'} ${c.name} (${c.detail})`).join('; ')),
    '', ...log.map((e) => `${e.t} ${e.kind} ${e.text}${e.url ? ' ' + e.url : ''}${e.ms ? ' ' + e.ms + 'ms' : ''}`)].join('\n');
  await navigator.clipboard.writeText(text); $('copy').textContent = 'Copied';
  setTimeout(() => ($('copy').textContent = 'Copy log for Claude'), 1500);
};
$('dl').onclick = async () => {
  const { testResults: T } = await chrome.storage.session.get('testResults');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(T || {}, null, 1)], { type: 'application/json' }));
  a.download = 'espn-test-data.json'; a.click();
};
chrome.storage.onChanged.addListener((ch, area) => { if (area === 'session') render(); });
render();
