// The Daily Fantasizer panel on fantasy.espn.com. Shows only while a link started from The Daily Fantasizer is pending.
// Lives in a shadow root so ESPN's styles and ours never mix.
(() => {
  let host, root, busy = false, picked = null;

  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const send = (msg) => new Promise((res) => chrome.runtime.sendMessage(msg, (r) => res(chrome.runtime.lastError ? null : r)));

  const CSS = `
  :host{all:initial}
  .p{position:fixed;top:72px;right:16px;z-index:2147483647;width:min(380px,calc(100vw - 32px));max-height:calc(100vh - 96px);overflow:auto;
    background:#f4f5f0;color:#151a24;border:2px solid #151a24;box-shadow:6px 6px 0 #1c3fae;font:15px/1.45 Georgia,"Times New Roman",serif}
  .h{background:#151a24;color:#f4f5f0;padding:12px 14px;display:flex;justify-content:space-between;align-items:center;gap:10px}
  .h b{font:900 20px/1 Impact,"Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.02em}
  .x{background:none;border:0;color:#f4f5f0;font:20px/1 sans-serif;cursor:pointer;padding:4px 6px}
  .b{padding:14px}
  p{margin:0 0 10px}.m{color:#59606c;font-size:13px}
  .k{font:600 11px/1.2 ui-monospace,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;color:#59606c;margin:0 0 6px}
  ul{list-style:none;margin:0 0 12px;padding:0;display:grid;gap:8px}
  li label{display:grid;grid-template-columns:22px 1fr;gap:10px;align-items:start;border:2px solid #c9cdc3;padding:10px;cursor:pointer;background:#fff}
  li label:has(input:checked){border-color:#1c3fae}
  li input{width:18px;height:18px;margin:2px 0 0;accent-color:#1c3fae}
  .n{font-weight:700}.t{display:block;font-size:12.5px;color:#59606c}
  .tag{display:inline-block;font:600 10px/1 ui-monospace,monospace;letter-spacing:.06em;text-transform:uppercase;border:1px solid currentColor;padding:2px 4px;margin-left:6px;color:#1c3fae;vertical-align:1px}
  .tag.g{color:#59606c}
  .btn{display:block;width:100%;min-height:44px;border:2px solid #1c3fae;background:#1c3fae;color:#fff;font:700 13px/1 ui-monospace,Menlo,monospace;text-transform:uppercase;letter-spacing:.05em;cursor:pointer;margin-top:6px}
  .btn[disabled]{opacity:.5;cursor:default}.btn.g{background:transparent;color:#151a24;border-color:#c9cdc3}
  .row{display:flex;gap:8px}.row input{flex:1;min-width:0;border:2px solid #c9cdc3;padding:9px;font:14px ui-monospace,monospace;background:#fff;color:#151a24}
  .row .btn{width:auto;margin:0;padding:0 12px}
  .err{border-left:4px solid #b3261e;background:#fff;padding:8px 10px;margin:0 0 10px;font-size:13.5px}
  .ok{border-left:4px solid #1f7a4d;background:#fff;padding:8px 10px;margin:0 0 10px}
  details{margin:4px 0 10px}summary{cursor:pointer;font-size:13.5px;color:#1c3fae}
  .arrow{font-size:13px;color:#59606c;margin-top:8px}`;

  function mount() {
    if (host) return;
    host = document.createElement('div');
    host.id = 'daily-fantasizer-panel';
    root = host.attachShadow({ mode: 'closed' });
    document.documentElement.appendChild(host);
  }
  function unmount() { if (host) { host.remove(); host = root = null; } }

  function frame(body) {
    mount();
    root.innerHTML = `<style>${CSS}</style><section class="p" role="dialog" aria-label="The Daily Fantasizer"><div class="h"><b>The Daily Fantasizer</b>
      <button class="x" id="x" aria-label="Cancel">×</button></div><div class="b">${body}</div></section>`;
    root.getElementById('x').onclick = async () => { await send({ type: 'cancel' }); unmount(); };
  }

  function leagueItem(l) {
    const on = picked.has(l.id);
    const sub = [l.team ? `Your team: ${esc(l.team)}` : '', l.teams ? `${l.teams} teams` : '', l.season || ''].filter(Boolean).join(' · ');
    return `<li><label><input type="checkbox" data-id="${esc(l.id)}" ${on ? 'checked' : ''}>
      <span><span class="n">${esc(l.name)}</span>${l.commissioner ? '<span class="tag">Commish</span>' : ''}${l.linked ? '<span class="tag g">Has a paper</span>' : ''}
      <span class="t">${sub}</span></span></label></li>`;
  }

  async function render(note = '') {
    if (busy) return;
    const s = await send({ type: 'panel-state' });
    if (!s || !s.active) return unmount();
    const site = esc(String(s.site).replace(/^https?:\/\//, ''));
    if (!s.signedIn) {
      return frame(`<p><b>Sign in to ESPN</b> with the <b>Log In</b> button on this page.</p>
        <p class="m">Once you're in, your fantasy leagues show up here and you pick which ones get a paper. Your ESPN password goes only to ESPN.</p>
        <p class="arrow">Linking to ${site}</p>`);
    }
    if (s.error) {
      return frame(`<div class="err">${esc(s.error)}</div><button class="btn g" id="retry">Try again</button>`), (root.getElementById('retry').onclick = () => render());
    }
    const leagues = s.leagues || [];
    if (!picked) picked = new Set(leagues.filter((l) => !l.linked).map((l) => l.id));
    const list = leagues.length ? `<ul>${leagues.map(leagueItem).join('')}</ul>`
      : `<p class="m">${esc(s.listError || 'ESPN didn’t list any football leagues for this account this season.')} Add a league by its ID below.</p>`;
    frame(`${note}<p class="k">Your ESPN football leagues</p>${list}
      <details ${leagues.length ? '' : 'open'}><summary>A league is missing? Add it by ID</summary>
        <div class="row" style="margin-top:8px"><input id="lid" placeholder="League ID or league link" inputmode="url" autocomplete="off"><button class="btn" id="add">Add</button></div>
        <p class="m" style="margin-top:6px">The number after leagueId= in the league's address.</p></details>
      <button class="btn" id="go">Add leagues</button>
      <p class="m" style="margin-top:10px">The Daily Fantasizer gets read-only access to the leagues you tick. It can't change lineups, trades or settings. Signing out of ESPN everywhere ends the link.</p>`);
    const go = root.getElementById('go');
    const sync = () => { const n = picked.size; go.disabled = !n; go.textContent = n ? `Add ${n} league${n > 1 ? 's' : ''}` : 'Pick a league'; };
    root.querySelectorAll('input[type=checkbox]').forEach((c) => (c.onchange = () => { c.checked ? picked.add(c.dataset.id) : picked.delete(c.dataset.id); sync(); }));
    sync();
    root.getElementById('add').onclick = async () => {
      const v = root.getElementById('lid').value.trim();
      const m = v.match(/leagueId=(\d+)/) || v.match(/^(\d{3,12})$/);
      if (!m) return render('<div class="err">That doesn’t look like an ESPN league ID.</div>');
      const r = await send({ type: 'add-league-id', league: m[1] });
      if (r && r.ok) { picked.add(r.league.id); render(`<div class="ok">Added ${esc(r.league.name)}.</div>`); }
      else render(`<div class="err">${esc((r && r.error) || 'Couldn’t add that league.')}</div>`);
    };
    go.onclick = async () => {
      busy = true; go.disabled = true; go.textContent = 'Adding…';
      const r = await send({ type: 'sync', leagues: [...picked] });
      busy = false;
      if (r && r.ok) frame('<div class="ok"><b>Done.</b> Taking you back to The Daily Fantasizer…</div>');
      else render(`<div class="err">${esc((r && r.error) || 'Something went wrong. Try again.')}</div>`);
    };
  }

  chrome.runtime.onMessage.addListener((msg) => { if (msg && msg.type === 'refresh') render(); });
  render();
  // ESPN's site changes pages without full reloads; re-check now and then while the panel could matter.
  let last = location.href;
  setInterval(() => { if (location.href !== last) { last = location.href; render(); } }, 1500);
})();
