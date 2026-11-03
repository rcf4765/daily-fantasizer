// Daily Fantasizer: ESPN link (works like FantasyPros' ESPN sync).
// 1. The Daily Fantasizer site asks to link ESPN → a fantasy.espn.com tab opens.
// 2. On that tab the extension shows a panel: sign in with ESPN's own Log In button, then tick the leagues to add.
// 3. "Add leagues" sends the two ESPN session cookies (espn_s2, SWID) and the chosen league IDs straight to the
//    Daily Fantasizer server, which stores the cookies encrypted and only reads the leagues with them. The site's
//    web page never sees the cookies. Then you're taken back to the site, where every chosen league has its paper.
// Pending state lives in chrome.storage.session so it survives the service worker sleeping while you sign in.
import { SITES, ESPN_START } from './config.js';

const ESPN_URL = 'https://fantasy.espn.com/';
const TIMEOUT_MS = 20 * 60 * 1000;
const VERSION = chrome.runtime.getManifest().version;
let linking = null;   // one /api/espn/link call at a time, however many panel refreshes ask

const getPending = async () => {
  const p = (await chrome.storage.session.get('pending')).pending || null;
  return p && Date.now() - p.started < TIMEOUT_MS ? p : null;
};
const setPending = (p) => chrome.storage.session.set({ pending: p });
const clearPending = () => chrome.storage.session.remove('pending');

async function espnCookies() {
  const [s2, swid] = await Promise.all([
    chrome.cookies.get({ url: ESPN_URL, name: 'espn_s2' }),
    chrome.cookies.get({ url: ESPN_URL, name: 'SWID' }),
  ]);
  return s2 && s2.value && swid && swid.value ? { espn_s2: decodeURIComponent(s2.value), swid: swid.value } : null;
}

async function api(p, path, body) {
  try {
    const r = await fetch(`${p.origin}${path}`, { method: 'POST', credentials: 'omit',
      headers: { 'Content-Type': 'application/json', 'X-Fantasizer-Extension': VERSION }, body: JSON.stringify(body) });
    const j = await r.json().catch(() => ({}));
    return r.ok && j.ok ? j : { ok: false, error: j.error || `The Daily Fantasizer answered ${r.status}.` };
  } catch (e) {
    return { ok: false, error: 'Couldn’t reach The Daily Fantasizer. Check your connection and try again.' };
  }
}

const tellSite = (p, result) => chrome.tabs.sendMessage(p.siteTab, { type: 'espn-link-result', result }).catch(() => {});
const tellPanel = (p) => p.espnTab != null && chrome.tabs.sendMessage(p.espnTab, { type: 'refresh' }).catch(() => {});

chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  (async () => {
    // ---- from the Daily Fantasizer site ----
    if (msg.type === 'espn-link') {
      const origin = sender.origin || (sender.url && new URL(sender.url).origin);
      if (!sender.tab || !SITES.includes(origin)) return reply({ ok: false, error: 'This extension only links ESPN leagues to The Daily Fantasizer.' });
      const old = await getPending();
      if (old && old.espnTab != null) chrome.tabs.remove(old.espnTab).catch(() => {});
      const tab = await chrome.tabs.create({ url: ESPN_START, index: sender.tab.index + 1, openerTabId: sender.tab.id, active: true });
      await setPending({ origin, siteTab: sender.tab.id, espnTab: tab.id, started: Date.now() });
      return reply({ ok: true, pending: true });
    }
    // ---- from the panel on fantasy.espn.com ----
    const p = await getPending();
    if (msg.type === 'panel-state') {
      if (!p || sender.tab.id !== p.espnTab) return reply({ active: false });
      const c = await espnCookies();
      if (!c) return reply({ active: true, site: p.origin, signedIn: false });
      // Signed in: hand the cookies to the server once, get back the account's leagues and a one-time link token.
      if (!p.token || p.swid !== c.swid || p.s2 !== c.espn_s2.slice(-12)) {
        linking = linking || (async () => {
          const j = await api(p, '/api/espn/link', c);
          if (j.ok) await setPending({ ...p, token: j.token, leagues: j.leagues, listError: j.listError || '', swid: c.swid, s2: c.espn_s2.slice(-12) });
          return j;
        })().finally(() => setTimeout(() => (linking = null), 0));
        const j = await linking;
        if (!j.ok) return reply({ active: true, site: p.origin, signedIn: true, error: j.error });
      }
      const q = await getPending();
      return reply({ active: true, site: p.origin, signedIn: true, leagues: q.leagues, listError: q.listError });
    }
    if (msg.type === 'add-league-id') {   // a league the list missed
      if (!p || !p.token) return reply({ ok: false, error: 'Start again from The Daily Fantasizer.' });
      const j = await api(p, '/api/espn/check', { token: p.token, league: msg.league });
      if (j.ok && !p.leagues.some((l) => l.id === j.league.id)) { p.leagues.push(j.league); await setPending(p); }
      return reply(j);
    }
    if (msg.type === 'sync') {
      if (!p || !p.token) return reply({ ok: false, error: 'Start again from The Daily Fantasizer.' });
      const j = await api(p, '/api/espn/sync', { token: p.token, leagues: msg.leagues });
      reply(j);
      if (j.ok) {
        await clearPending();
        const next = p.origin + j.next;   // the server answers with a path on its own site
        await chrome.tabs.update(p.siteTab, { url: next, active: true }).catch(() => chrome.tabs.create({ url: next }));
        setTimeout(() => chrome.tabs.remove(p.espnTab).catch(() => {}), 1200);
      }
      return;
    }
    if (msg.type === 'cancel') {
      if (p) { await clearPending(); await tellSite(p, { ok: false, cancelled: true, error: 'Cancelled. Nothing was added.' });
        chrome.tabs.update(p.siteTab, { active: true }).catch(() => {}); chrome.tabs.remove(p.espnTab).catch(() => {}); }
      return reply({ ok: true });
    }
    reply({ ok: false });
  })();
  return true;  // reply asynchronously
});

// ESPN sets espn_s2 when a sign-in completes (or a different account signs in): refresh the panel.
chrome.cookies.onChanged.addListener(async ({ cookie, removed }) => {
  if (removed || cookie.name !== 'espn_s2' || !/(^|\.)espn\.com$/.test(cookie.domain.replace(/^\./, ''))) return;
  const p = await getPending();
  if (p) setTimeout(() => tellPanel(p), 800);   // let ESPN finish setting SWID too
});

// The ESPN tab was closed before adding leagues.
chrome.tabs.onRemoved.addListener(async (id) => {
  const p = await getPending();
  if (p && p.espnTab === id) { await clearPending(); tellSite(p, { ok: false, cancelled: true, error: 'The ESPN tab was closed. Nothing was added.' }); }
});
