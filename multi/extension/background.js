// Daily Fantasizer: ESPN link (works like FantasyPros' ESPN sync).
// 1. The Daily Fantasizer site (or the extension's own test page) asks to link ESPN → a fantasy.espn.com tab opens.
// 2. On that tab the extension shows a panel: sign in with ESPN's own Log In button, then tick the leagues to add.
// 3. "Add leagues":
//    - from the site: the ESPN session (espn_s2, SWID) and the chosen league IDs go straight to the Daily Fantasizer
//      server, which stores the session encrypted and reads the leagues with it. The site's page never sees the cookies.
//    - from the test page: nothing leaves the browser. The extension reads each league from ESPN itself and shows the
//      results (and a log of every request) on the test page.
// Pending state lives in chrome.storage.session so it survives the service worker sleeping while you sign in.
import { SITES, ESPN_START } from './config.js';

const ESPN_URL = 'https://fantasy.espn.com/';
const API = 'https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl';
const TIMEOUT_MS = 20 * 60 * 1000;
const VERSION = chrome.runtime.getManifest().version;
const TEST_PAGE = chrome.runtime.getURL('test.html');
let linking = null;   // one link call at a time, however many panel refreshes ask

const getPending = async () => {
  const p = (await chrome.storage.session.get('pending')).pending || null;
  return p && Date.now() - p.started < TIMEOUT_MS ? p : null;
};
const setPending = (p) => chrome.storage.session.set({ pending: p });
const clearPending = () => chrome.storage.session.remove('pending');

// ---------------- log (shown on the test page; never holds cookie values) ----------------
async function log(kind, text, extra = {}) {
  const { log: L = [] } = await chrome.storage.session.get('log');
  L.push({ t: new Date().toISOString(), kind, text, ...extra });
  await chrome.storage.session.set({ log: L.slice(-250) });
}

export const espnSeason = (d = new Date()) => d.getUTCFullYear() - (d.getUTCMonth() < 2 ? 1 : 0);
const norm = (s) => String(s || '').toUpperCase().replace(/[{}]/g, '');

async function espnCookies() {
  const [s2, swid] = await Promise.all([
    chrome.cookies.get({ url: ESPN_URL, name: 'espn_s2' }),
    chrome.cookies.get({ url: ESPN_URL, name: 'SWID' }),
  ]);
  return s2 && s2.value && swid && swid.value ? { espn_s2: decodeURIComponent(s2.value), swid: swid.value } : null;
}

// ---------------- reading ESPN directly (test mode) ----------------
async function espnGet(url, label) {
  const t0 = Date.now();
  try {
    const r = await fetch(url, { credentials: 'include', headers: { Accept: 'application/json' } });
    const type = r.headers.get('content-type') || '';
    const body = type.includes('json') ? await r.json().catch(() => null) : null;
    await log(r.ok && body ? 'ok' : 'err', `${label}: HTTP ${r.status}${body ? '' : ' (not JSON)'}`, { url: url.replace(/\?.*/, '?…'), ms: Date.now() - t0 });
    return { status: r.status, body };
  } catch (e) {
    await log('err', `${label}: ${e.message}`, { url: url.replace(/\?.*/, '?…') });
    return { status: 0, body: null };
  }
}

function leagueSummary(id, season, j, swid) {
  const me = (j.members || []).find((m) => norm(m.id) === norm(swid));
  const t = (j.teams || []).find((x) => (x.owners || []).some((o) => norm(o) === norm(swid)) || norm(x.primaryOwner) === norm(swid));
  return { id: String(id), season, name: j.settings?.name || `League ${id}`, teams: (j.teams || []).length, member: !!me,
    commissioner: !!(me && me.isLeagueManager), team: t ? (t.name || [t.location, t.nickname].filter(Boolean).join(' ')) : '' };
}

async function localLeague(id, season, swid) {
  const r = await espnGet(`${API}/seasons/${season}/segments/0/leagues/${id}?view=mSettings&view=mTeam`, `League ${id}`);
  if (r.status === 401 || r.status === 403) return { error: 'ESPN says this league is private to its members.' };
  if (r.status === 404) return { error: `No ESPN league ${id} in ${season}.` };
  if (!r.body) return { error: `ESPN didn’t answer (HTTP ${r.status}).` };
  return leagueSummary(id, season, r.body, swid);
}

const local = {
  async link(c) {
    const season = espnSeason();
    await log('info', `Signed in to ESPN (SWID …${norm(c.swid).slice(-4)}). Listing football leagues for ${season}.`);
    const fan = await espnGet(`https://fan.api.espn.com/apis/v2/fans/${encodeURIComponent('{' + norm(c.swid) + '}')}?displayHiddenPrefs=true&context=fantasy&useCookieAuth=true&source=fantasyapp-ios&featureFlags=challengeEntries`, 'ESPN fan profile');
    if (fan.status === 401 || fan.status === 403) return { ok: false, error: 'ESPN didn’t accept this sign-in. Sign out of ESPN, sign in again and retry.' };
    const ids = new Set(), seen = [];
    for (const p of (fan.body && fan.body.preferences) || []) {
      const e = p && p.metaData && p.metaData.entry;
      if (!e) continue;
      seen.push(`${e.abbrev || '?'}/${e.gameId ?? '?'}/${e.seasonId ?? '?'}:${(e.groups || []).map((g) => g.groupId).join(',')}`);
      const football = e.abbrev === 'FFL' || e.gameId === 1 || /football/i.test(String(e.name || e.entryURL || ''));
      if (!football || (e.seasonId && +e.seasonId !== +season)) continue;
      for (const g of e.groups || []) if (g && g.groupId) ids.add(String(g.groupId));
    }
    await log(ids.size ? 'ok' : 'warn', `Fan profile entries (sport/game/season:leagues): ${seen.join('  ') || 'none'} → ${ids.size} football league(s) this season`);
    const leagues = [];
    for (const id of ids) {
      const s = await localLeague(id, season, c.swid);
      if (s.error) await log('warn', `League ${id} skipped: ${s.error}`);
      else if (!s.member) await log('warn', `League ${id} (${s.name}) skipped: this account isn’t listed as a member`);
      else leagues.push(s);
    }
    return { ok: true, token: 'local', leagues, listError: ids.size ? '' : 'ESPN didn’t list any football leagues for this account this season.' };
  },
  async check(id) {
    const c = await espnCookies();
    const s = await localLeague(id, espnSeason(), c ? c.swid : '');
    if (s.error) return { ok: false, error: s.error };
    if (!s.member) return { ok: false, error: `This ESPN account isn’t in ${s.name}.` };
    return { ok: true, league: s };
  },
  // The deep read: everything the paper is printed from, per league.
  async sync(ids) {
    const season = espnSeason();
    const c = await espnCookies();
    const results = [];
    for (const id of ids) results.push(await deepRead(id, season, c ? c.swid : ''));
    await chrome.storage.session.set({ testResults: { at: new Date().toISOString(), season, results } });
    await log('info', `Test read finished for ${ids.length} league(s).`);
    return { ok: true, next: TEST_PAGE + '#results' };
  },
};

async function deepRead(id, season, swid) {
  const base = `${API}/seasons/${season}/segments/0/leagues/${id}`;
  const out = { id, checks: [], data: {} };
  const check = (name, pass, detail) => out.checks.push({ name, pass, detail });
  const A = await espnGet(`${base}?view=mTeam&view=mSettings&view=mStatus&view=mMatchupScore`, `League ${id} settings/teams/schedule`);
  if (!A.body) { check('League settings, teams and schedule', false, `HTTP ${A.status}`); return out; }
  const j = A.body, s = leagueSummary(id, season, j, swid);
  Object.assign(out, s);
  const st = j.status || {}, set = j.settings || {};
  const week = (st.latestScoringPeriod || j.scoringPeriodId || 1);
  const done = Math.max(0, (st.currentMatchupPeriod || week) - 1);
  const rec = (set.scoringSettings?.scoringItems || []).find((x) => x.statId === 53);
  const slots = Object.entries(set.rosterSettings?.lineupSlotCounts || {}).filter(([k, n]) => n > 0 && !['20', '21'].includes(k)).length;
  out.data.settings = { teams: s.teams, scoring: rec ? `${rec.points} per catch` : 'no points per catch', regularSeasonWeeks: set.scheduleSettings?.matchupPeriodCount,
    playoffTeams: set.scheduleSettings?.playoffTeamCount, currentWeek: st.currentMatchupPeriod, lastCompletedWeek: done, lineupSlotTypes: slots };
  check('League settings, teams and schedule', true, `${s.teams} teams · ${out.data.settings.scoring} · week ${st.currentMatchupPeriod || '?'} in progress`);
  check('This ESPN account is a member', s.member, s.member ? `your team: ${s.team || '?'}${s.commissioner ? ' · commissioner' : ''}` : 'not found in the member list');
  const teams = (j.teams || []).map((t) => ({ id: t.id, name: t.name || [t.location, t.nickname].filter(Boolean).join(' '), abbrev: t.abbrev,
    w: t.record?.overall?.wins ?? 0, l: t.record?.overall?.losses ?? 0, pf: Math.round((t.record?.overall?.pointsFor ?? t.points ?? 0) * 10) / 10 }));
  teams.sort((a, b) => b.w - a.w || b.pf - a.pf);
  out.data.standings = teams;
  check('Standings', teams.length > 0, teams.length ? `leader: ${teams[0].name} (${teams[0].w}-${teams[0].l})` : 'no teams');
  const sched = j.schedule || [];
  check('Full-season schedule', sched.length > 0, `${sched.length} matchups`);
  if (done >= 1) {
    const B = await espnGet(`${base}?view=mMatchupScore&view=mBoxscore&scoringPeriodId=${done}`, `League ${id} week ${done} box scores`);
    const games = ((B.body && B.body.schedule) || []).filter((m) => m.matchupPeriodId === done);
    let starters = 0, withPoints = 0;
    const byId = Object.fromEntries(teams.map((t) => [t.id, t.name]));
    out.data.lastWeek = games.map((m) => {
      for (const side of [m.home, m.away]) for (const e of (side?.rosterForCurrentScoringPeriod?.entries || [])) {
        if (![20, 21].includes(e.lineupSlotId)) { starters++; if ((e.playerPoolEntry?.appliedStatTotal ?? null) !== null) withPoints++; }
      }
      return { home: byId[m.home?.teamId], homePts: m.home?.totalPoints, away: byId[m.away?.teamId], awayPts: m.away?.totalPoints };
    });
    check(`Week ${done} scores`, games.length > 0, `${games.length} games`);
    check(`Week ${done} lineups with player points`, starters > 0 && withPoints === starters, `${withPoints} of ${starters} starters have points`);
    const X = await espnGet(`${base}?view=mTransactions2&scoringPeriodId=${done}`, `League ${id} week ${done} transactions`);
    check(`Week ${done} transactions`, !!X.body, X.body ? `${(X.body.transactions || []).length} moves` : `HTTP ${X.status}`);
  } else {
    check('Last completed week', false, 'no week has finished yet this season');
  }
  return out;
}

// ---------------- the Daily Fantasizer server (site mode) ----------------
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
const backend = (p) => p.test ? {
  link: (c) => local.link(c), check: (id) => local.check(id), sync: (ids) => local.sync(ids),
} : {
  link: (c) => api(p, '/api/espn/link', c),
  check: (id) => api(p, '/api/espn/check', { token: p.token, league: id }),
  sync: async (ids) => { const j = await api(p, '/api/espn/sync', { token: p.token, leagues: ids }); if (j.ok) j.next = p.origin + j.next; return j; },
};

const tellStarter = (p, result) => chrome.tabs.sendMessage(p.siteTab, { type: 'espn-link-result', result }).catch(() => {});
const tellPanel = (p) => p.espnTab != null && chrome.tabs.sendMessage(p.espnTab, { type: 'refresh' }).catch(() => {});

chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  (async () => {
    // ---- start: from the Daily Fantasizer site, or from the extension's test page ----
    if (msg.type === 'espn-link') {
      const test = !!(sender.url && sender.url.startsWith(TEST_PAGE));
      const origin = test ? 'test' : (sender.origin || (sender.url && new URL(sender.url).origin));
      if (!sender.tab || (!test && !SITES.includes(origin))) return reply({ ok: false, error: 'This extension only links ESPN leagues to The Daily Fantasizer.' });
      const old = await getPending();
      if (old && old.espnTab != null) chrome.tabs.remove(old.espnTab).catch(() => {});
      const tab = await chrome.tabs.create({ url: ESPN_START, index: sender.tab.index + 1, openerTabId: sender.tab.id, active: true });
      await setPending({ origin, test, siteTab: sender.tab.id, espnTab: tab.id, started: Date.now() });
      await log('info', `Started ${test ? 'a test' : 'a link for ' + origin}; opened ESPN.`);
      return reply({ ok: true, pending: true });
    }
    // ---- from the panel on fantasy.espn.com ----
    const p = await getPending();
    if (msg.type === 'panel-state') {
      if (!p || sender.tab.id !== p.espnTab) return reply({ active: false });
      const site = p.test ? 'the test page (nothing leaves this browser)' : p.origin;
      const c = await espnCookies();
      if (!c) return reply({ active: true, site, signedIn: false });
      if (!p.token || p.swid !== c.swid || p.s2 !== c.espn_s2.slice(-12)) {
        linking = linking || (async () => {
          const j = await backend(p).link(c);
          if (j.ok) await setPending({ ...p, token: j.token, leagues: j.leagues, listError: j.listError || '', swid: c.swid, s2: c.espn_s2.slice(-12) });
          else await log('err', `Link failed: ${j.error}`);
          return j;
        })().finally(() => setTimeout(() => (linking = null), 0));
        const j = await linking;
        if (!j.ok) return reply({ active: true, site, signedIn: true, error: j.error });
      }
      const q = await getPending();
      return reply({ active: true, site, signedIn: true, leagues: q.leagues, listError: q.listError });
    }
    if (msg.type === 'add-league-id') {
      if (!p || !p.token) return reply({ ok: false, error: 'Start again from The Daily Fantasizer.' });
      const j = await backend(p).check(msg.league);
      if (j.ok && !p.leagues.some((l) => l.id === j.league.id)) { p.leagues.push(j.league); await setPending(p); }
      return reply(j);
    }
    if (msg.type === 'sync') {
      if (!p || !p.token) return reply({ ok: false, error: 'Start again from The Daily Fantasizer.' });
      const j = await backend(p).sync(msg.leagues);
      reply(j);
      if (j.ok) {
        await clearPending();
        await chrome.tabs.update(p.siteTab, { url: j.next, active: true }).catch(() => chrome.tabs.create({ url: j.next }));
        setTimeout(() => chrome.tabs.remove(p.espnTab).catch(() => {}), 1200);
      } else await log('err', `Add leagues failed: ${j.error}`);
      return;
    }
    if (msg.type === 'cancel') {
      if (p) { await clearPending(); await tellStarter(p, { ok: false, cancelled: true, error: 'Cancelled. Nothing was added.' });
        chrome.tabs.update(p.siteTab, { active: true }).catch(() => {}); chrome.tabs.remove(p.espnTab).catch(() => {}); }
      return reply({ ok: true });
    }
    // ---- test page tools ----
    if (msg.type === 'test-status') {
      const c = await espnCookies();
      return reply({ version: VERSION, season: espnSeason(), signedIn: !!c, swid: c ? '…' + norm(c.swid).slice(-4) : '', sites: SITES });
    }
    if (msg.type === 'test-read') {   // read one league by ID without the ESPN tab
      const c = await espnCookies();
      const r = await deepRead(String(msg.league), espnSeason(), c ? c.swid : '');
      const { testResults } = await chrome.storage.session.get('testResults');
      const results = ((testResults && testResults.results) || []).filter((x) => x.id !== r.id).concat(r);
      await chrome.storage.session.set({ testResults: { at: new Date().toISOString(), season: espnSeason(), results } });
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
  if (p) { await log('info', 'ESPN sign-in detected.'); setTimeout(() => tellPanel(p), 800); }   // let ESPN finish setting SWID too
});

// The ESPN tab was closed before adding leagues.
chrome.tabs.onRemoved.addListener(async (id) => {
  const p = await getPending();
  if (p && p.espnTab === id) { await clearPending(); await log('warn', 'ESPN tab closed before adding leagues.'); tellStarter(p, { ok: false, cancelled: true, error: 'The ESPN tab was closed. Nothing was added.' }); }
});

// Toolbar button → the test page.
chrome.action.onClicked.addListener(() => chrome.tabs.create({ url: TEST_PAGE }));
