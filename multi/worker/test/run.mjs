// Local test of the Worker without Cloudflare: D1 on Node's built-in SQLite, R2 in memory, Yahoo/ESPN/GitHub faked.
// node --no-warnings test/run.mjs
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import worker from '../src/index.js';

// ---- D1 shim ----
const sql = new DatabaseSync(':memory:');
sql.exec(readFileSync(new URL('../schema.sql', import.meta.url), 'utf8'));
const stmt = (q, args = []) => ({
  bind: (...a) => stmt(q, a),
  first: async () => sql.prepare(q).get(...args) ?? null,
  all: async () => ({ results: sql.prepare(q).all(...args) }),
  run: async () => { const r = sql.prepare(q).run(...args); return { meta: { changes: r.changes } }; },
});
const DB = { prepare: (q) => stmt(q), batch: async (list) => Promise.all(list.map((s) => s.run())) };
// ---- R2 shim ----
const store = new Map();
const PAPERS = {
  put: async (k, body) => { store.set(k, typeof body === 'string' ? body : await new Response(body).text()); },
  get: async (k) => store.has(k) ? { body: store.get(k), text: async () => store.get(k), json: async () => JSON.parse(store.get(k)) } : null,
  delete: async (k) => store.delete(k),
  list: async ({ prefix }) => ({ objects: [...store.keys()].filter((k) => k.startsWith(prefix)).map((key) => ({ key })) }),
};
const env = { DB, PAPERS, SITE_URL: 'https://fz.example', SESSION_SECRET: 's'.repeat(32), ENC_KEY: 'k'.repeat(32), BUILD_TOKEN: 'build-tok',
  GITHUB_TOKEN: 'gh', GITHUB_REPO: 'rcf4765/daily-fantasizer', YAHOO_CLIENT_ID: 'cid', YAHOO_CLIENT_SECRET: 'csec' };
const ctx = { waitUntil: () => {} };

// ---- fake outside world ----
const dispatched = [];
const YX = (inner) => `<?xml version="1.0"?><fantasy_content xmlns="http://fantasysports.yahooapis.com/fantasy/v2/base.rng">${inner}</fantasy_content>`;
globalThis.fetch = async (url, init = {}) => {
  url = String(url);
  if (url.includes('api.github.com')) { dispatched.push(JSON.parse(init.body).inputs.slug); return new Response(null, { status: 204 }); }
  if (url.includes('get_token')) {
    const b = new URLSearchParams(init.body);
    assert.equal(init.headers.Authorization, 'Basic ' + btoa('cid:csec'));
    return Response.json({ access_token: 'AT-' + b.get('grant_type'), refresh_token: 'RT1', expires_in: 3600, xoauth_yahoo_guid: 'GUID9' });
  }
  if (url.includes('games;game_keys=nfl/leagues')) return new Response(YX('<users><user><games><game><leagues><league><league_key>461.l.555</league_key><name>Sunday Funday</name><num_teams>10</num_teams><season>2026</season></league><league><league_key>461.l.556</league_key><name>Work League</name><num_teams>12</num_teams><season>2026</season></league></leagues></game></games></user></users>'));
  if (url.includes('games;game_keys=nfl/teams')) return new Response(YX('<users><user><games><game><teams><team><team_key>461.l.555.t.3</team_key><name>Taco Tuesday</name><managers><manager><is_commissioner>1</is_commissioner><is_current_login>1</is_current_login></manager></managers></team><team><team_key>461.l.556.t.7</team_key><name>Spreadsheet Kings</name><managers><manager><is_current_login>1</is_current_login></manager></managers></team></teams></game></games></user></users>'));
  if (url.includes('fan.api.espn.com')) {
    if (!(init.headers?.Cookie || '').includes('espn_s2=GOOD')) return new Response('no', { status: 401 });
    return Response.json({ preferences: [
      { metaData: { entry: { abbrev: 'FFL', gameId: 1, seasonId: 2026, groups: [{ groupId: 4001 }] } } },
      { metaData: { entry: { abbrev: 'FFL', gameId: 1, seasonId: 2026, groups: [{ groupId: 4002 }] } } },
      { metaData: { entry: { abbrev: 'FFL', gameId: 1, seasonId: 2025, groups: [{ groupId: 3999 }] } } },   // last season: skipped
      { metaData: { entry: { abbrev: 'FBA', gameId: 3, seasonId: 2026, groups: [{ groupId: 5001 }] } } },   // basketball: skipped
      { type: { code: 'team' } } ] });
  }
  if (url.includes('lm-api-reads.fantasy.espn.com') && /leagues\/(400[1-3]|4777)/.test(url)) {
    const id = url.match(/leagues\/(\d+)/)[1], me = '{CCCCCCCC-1111-2222-3333-444444444444}';
    const mine = id !== '4777';
    return Response.json({ settings: { name: { 4001: 'Office League', 4002: 'Family League', 4003: 'Old College League', 4777: 'Strangers' }[id] },
      teams: Array.from({ length: 10 }, (_, i) => ({ id: i + 1, name: i === 2 ? 'My Squad ' + id : 'T' + i, owners: i === 2 && mine ? [me] : ['{X}'] })),
      members: mine ? [{ id: me, isLeagueManager: id === '4001' }, { id: '{X}' }] : [{ id: '{X}' }] });
  }
  if (url.includes('lm-api-reads.fantasy.espn.com')) {
    const ck = init.headers?.Cookie || '';
    if (url.includes('/leagues/999')) return new Response('nope', { status: 401 });
    if (url.includes('/leagues/777') && !ck) return new Response('nope', { status: 401 });
    return Response.json({ settings: { name: url.includes('777') ? 'Private Pals' : 'Open League' }, teams: Array.from({ length: 12 }, (_, i) => ({ id: i + 1 })),
      members: [{ id: '{AAAA-1111}', isLeagueManager: true }, { id: '{BBBB-2222}', isLeagueManager: false }] });
  }
  throw new Error('unexpected fetch ' + url);
};

// ---- helpers ----
let jar = {};
async function call(method, path, { form, body, headers = {}, keepCookies = true } = {}) {
  const h = new Headers(headers);
  const ck = Object.entries(jar).map(([k, v]) => `${k}=${v}`).join('; ');
  if (ck && keepCookies) h.set('Cookie', ck);
  let b = body;
  if (form) { b = new URLSearchParams(form); h.set('Content-Type', 'application/x-www-form-urlencoded'); h.set('Origin', 'https://fz.example'); }
  const res = await worker.fetch(new Request('https://fz.example' + path, { method, headers: h, body: b }), env, ctx);
  for (const sc of res.headers.getSetCookie?.() || []) { const [kv] = sc.split(';'); const [k, v] = kv.split('='); if (v) jar[k] = v; else delete jar[k]; }
  return res;
}
const text = async (r) => r.text();
const ok = (name) => console.log('  ✓', name);

// ---- tests ----
console.log('pages');
let r = await call('GET', '/'); assert.equal(r.status, 200); assert.match(await text(r), /Sign in with Yahoo/); ok('home');
r = await call('GET', '/espn'); assert.match(await text(r), /League ID/); ok('ESPN form');

console.log('ESPN');
r = await call('POST', '/espn', { form: { league: 'abc', season: '2026' } }); assert.equal(r.status, 400); ok('bad id rejected');
r = await call('POST', '/espn', { form: { league: '999', season: '2026' } }); assert.match(await text(r), /private/); ok('private league asks for cookies');
r = await call('POST', '/espn', { form: { league: 'https://fantasy.espn.com/football/league?leagueId=123456&seasonId=2026', season: '2026' } });
assert.equal(r.status, 303); const pubSlug = r.headers.get('Location').split('/')[2]; ok(`public league created → /l/${pubSlug}/`);
assert.deepEqual(dispatched.pop(), pubSlug); ok('first print dispatched');
r = await call('GET', `/l/${pubSlug}/settings`); assert.equal(r.status, 403); ok('no cookies = not commissioner, settings locked');
r = await call('GET', `/l/${pubSlug}/`); assert.match(await text(r), /queued at the printer/); ok('status page before first print');

jar = {};
r = await call('POST', '/espn', { form: { league: '777', season: '2026', espn_s2: 'S2SECRET', swid: '{BBBB-2222}' } });
const privSlug = r.headers.get('Location').split('/')[2];
r = await call('GET', `/l/${privSlug}/settings`); assert.equal(r.status, 403); ok('league member (not manager) cannot open settings');
jar = {};
r = await call('POST', '/espn', { form: { league: '777', season: '2026', espn_s2: 'S2BOSS', swid: '{aaaa-1111}' } });
assert.equal(r.headers.get('Location').split('/')[2], privSlug); ok('same league → same paper, no duplicate');
r = await call('GET', `/l/${privSlug}/settings`); assert.equal(r.status, 200); assert.match(await text(r), /Optional tabs/); ok('ESPN manager opens settings');
const row = sql.prepare('SELECT espn_s2, swid, feat_rules, feat_bets FROM leagues WHERE slug=?').get(privSlug);
assert.ok(!row.espn_s2.includes('S2BOSS')); assert.equal(row.feat_rules, 0); assert.equal(row.feat_bets, 0); ok('cookies stored sealed; both tabs default off');

r = await call('POST', `/l/${privSlug}/settings`, { form: { rules: 'on', bets: 'on', accent: '#2d6a4f' } });
const page = await text(r); const code = page.match(/class="code">([A-Z0-9-]+)</)[1]; ok(`turned on Rule Changes + Betting; commissioner code shown once (${code})`);
assert.equal(dispatched.pop(), privSlug); ok('reprint dispatched after settings change');

console.log('build API');
r = await call('GET', '/api/build/leagues', { keepCookies: false }); assert.equal(r.status, 401); ok('build API needs the token');
r = await call('GET', '/api/build/leagues', { headers: { Authorization: 'Bearer build-tok' } });
let L = (await r.json()).leagues; const priv = L.find((x) => x.slug === privSlug);
assert.equal(priv.espn_s2, 'S2BOSS'); assert.equal(priv.swid, '{aaaa-1111}'); assert.deepEqual(priv.features, { rules: true, bets: true }); assert.equal(priv.accent, '#2d6a4f');
ok('printer gets decrypted cookies, features, accent, office URL');
r = await call('PUT', `/api/build/${privSlug}/file?path=../../etc`, { headers: { Authorization: 'Bearer build-tok' }, body: 'x' }); assert.equal(r.status, 400); ok('upload paths are whitelisted');
await call('PUT', `/api/build/${privSlug}/file?path=index.html`, { headers: { Authorization: 'Bearer build-tok' }, body: '<title>The Daily Fantasizer</title><p>paper</p>' });
await call('PUT', `/api/build/${privSlug}/file?path=week8.html`, { headers: { Authorization: 'Bearer build-tok' }, body: '<p>w8</p>' });
const lineFile = { week: 9, nfl: [{ id: 'N:G1', title: 'CAR @ GB', lock: '2099-01-01T00:00:00Z', markets: [{ m: 'ml', label: 'Moneyline', sel: [{ id: 'N:G1:ml:a', name: 'CAR', odds: 150 }, { id: 'N:G1:ml:h', name: 'GB', odds: -170 }] }] },
  { id: 'N:G2', title: 'NYJ @ BUF', lock: '2000-01-01T00:00:00Z', markets: [{ m: 'ml', label: 'Moneyline', sel: [{ id: 'N:G2:ml:a', name: 'NYJ', odds: 300 }] }] }] };
await call('PUT', `/api/build/${privSlug}/file?path=bets/lines9.json`, { headers: { Authorization: 'Bearer build-tok' }, body: JSON.stringify(lineFile) });
await call('POST', `/api/build/${privSlug}/status`, { headers: { Authorization: 'Bearer build-tok' }, body: JSON.stringify({ status: 'ok', week: 8 }) });
r = await call('GET', `/l/${privSlug}/`); let t = await text(r); assert.match(t, /<p>paper<\/p>/); assert.match(t, /\/settings"/); ok('paper served, commissioner sees a Settings button');
jar = {}; r = await call('GET', `/l/${privSlug}/`); t = await text(r); assert.doesNotMatch(t, /\/settings"/); ok('everyone else sees only the paper');
r = await call('GET', `/l/${privSlug}/archive`); assert.match(await text(r), /Week 8/); ok('archive lists editions');

console.log('league office');
const API = `/api/office/${privSlug}`;
const post = async (b) => (await call('POST', API, { body: JSON.stringify(b), headers: { 'Content-Type': 'text/plain;charset=utf-8' } })).json();
let s = await (await call('GET', API)).json(); assert.equal(s.rules.teams, 12); assert.equal(s.rules.pass, 7); ok('state: 12 teams, 7 to pass');
const k1 = (await post({ action: 'claim', team: 1 })).key; assert.ok(k1);
assert.equal((await post({ action: 'claim', team: 1 })).ok, false); ok('one claim per team');
const keys = { 1: k1 };
for (let tm = 2; tm <= 8; tm++) keys[tm] = (await post({ action: 'claim', team: tm })).key;
let res = await post({ action: 'propose', team: 1, key: k1, preset: 'half-ppr' }); assert.ok(res.ok); const pid = res.id; ok('preset proposal');
assert.equal((await post({ action: 'vote', team: 2, key: k1, proposal: pid, choice: 'yes' })).ok, false); ok('wrong key cannot vote');
for (let tm = 1; tm <= 6; tm++) await post({ action: 'vote', team: tm, key: keys[tm], proposal: pid, choice: 'yes' });
await post({ action: 'vote', team: 6, key: keys[6], proposal: pid, choice: 'yes' });
s = await (await call('GET', API)).json(); assert.equal(s.proposals[0].votes.length, 6); assert.equal(s.proposals[0].status, 'open'); ok('re-vote replaces, 6 yes still open');
res = await post({ action: 'vote', team: 7, key: keys[7], proposal: pid, choice: 'yes' }); assert.equal(res.state.proposals[0].status, 'passed'); ok('7th yes passes it');
res = await post({ action: 'bet', team: 1, key: k1, week: 9, stake: 2, legs: ['N:G1:ml:a'] }); assert.ok(res.ok, res.error); assert.equal(res.state.bets[0].win, 3); ok('bet placed, +150 pays 3 on 2');
res = await post({ action: 'bet', team: 1, key: k1, week: 9, stake: 4, legs: ['N:G1:ml:h'] }); assert.match(res.error, /over your 5 points/); ok('5-point weekly cap');
res = await post({ action: 'bet', team: 2, key: keys[2], week: 9, stake: 1, legs: ['N:G2:ml:a'] }); assert.match(res.error, /locked/); ok('started games are locked');
res = await post({ action: 'admin', code: 'WRONG', op: 'reset', team: 3 }); assert.equal(res.ok, false);
res = await post({ action: 'admin', code: code.toLowerCase(), op: 'reset', team: 3 }); assert.ok(res.ok); ok('commissioner code resets a claim');

// turn betting off: office refuses bets, page still works for votes
jar = {}; await call('POST', '/espn', { form: { league: '777', season: '2026', espn_s2: 'S2BOSS', swid: '{AAAA-1111}' } });
await call('POST', `/l/${privSlug}/settings`, { form: { rules: 'on', accent: '#2d6a4f' } });
res = await post({ action: 'bet', team: 1, key: k1, week: 9, stake: 1, legs: ['N:G1:ml:h'] }); assert.match(res.error, /turned off/); ok('betting off → bets refused');
await call('POST', `/l/${pubSlug}/settings`, { form: { rules: 'on' } });
r = await call('GET', `/api/office/${pubSlug}`); assert.match((await r.json()).error, /hasn’t turned/); ok('another league’s office stays closed (not its commissioner)');

console.log('Yahoo');
jar = {};
r = await call('GET', '/auth/yahoo'); const loc = new URL(r.headers.get('Location'));
assert.equal(loc.origin + loc.pathname, 'https://api.login.yahoo.com/oauth2/request_auth'); assert.equal(loc.searchParams.get('redirect_uri'), 'https://fz.example/auth/yahoo/callback'); ok('redirect to Yahoo');
r = await call('GET', `/auth/yahoo/callback?code=C1&state=WRONG`); assert.equal(r.status, 400); ok('state mismatch rejected');
r = await call('GET', `/auth/yahoo/callback?code=C1&state=${loc.searchParams.get('state')}`); assert.equal(r.headers.get('Location'), '/yahoo'); ok('signed in');
r = await call('GET', '/yahoo'); t = await text(r); assert.match(t, /Sunday Funday[\s\S]*Commissioner/); assert.match(t, /Work League/); ok('league picker marks where you are commissioner');
r = await call('POST', '/yahoo/league', { form: { key: '461.l.556' } }); const workSlug = r.headers.get('Location').split('/')[2];
r = await call('GET', `/l/${workSlug}/settings`); assert.equal(r.status, 403); ok('not commissioner of Work League → settings locked');
r = await call('POST', '/yahoo/league', { form: { key: '461.l.555' } }); const ySlug = r.headers.get('Location').split('/')[2];
r = await call('GET', `/l/${ySlug}/settings`); assert.equal(r.status, 200); ok('Yahoo commissioner opens settings');
r = await call('POST', '/yahoo/league', { form: { key: '461.l.999' } }); assert.equal(r.status, 403); ok('cannot add a league you are not in');
r = await call('GET', `/api/build/leagues?slug=${ySlug}`, { headers: { Authorization: 'Bearer build-tok' } });
assert.equal((await r.json()).leagues[0].yahoo_token, 'AT-refresh_token'); ok('printer gets a fresh Yahoo access token');
r = await call('GET', '/mine'); t = await text(r); assert.match(t, /Sunday Funday/); assert.match(t, /Work League/); ok('My leagues');

console.log('ESPN extension sync (one account, several leagues)');
{
  const savedJar = { ...jar };
  const ext = { 'X-Fantasizer-Extension': '0.1.0', 'Content-Type': 'application/json' };
  const post = (path, b) => call('POST', path, { body: JSON.stringify(b), headers: ext, keepCookies: false });
  const SW = '{CCCCCCCC-1111-2222-3333-444444444444}', GOOD = 'GOOD' + 'x'.repeat(60);
  r = await call('POST', '/api/espn/link', { body: JSON.stringify({ espn_s2: GOOD, swid: SW }), headers: { 'Content-Type': 'application/json' } });
  assert.equal(r.status, 400); ok('only the extension may call it');
  r = await post('/api/espn/link', { espn_s2: 'BAD' + 'x'.repeat(60), swid: SW }); assert.equal(r.status, 401); ok('a bad ESPN sign-in is refused');
  r = await post('/api/espn/link', { espn_s2: GOOD, swid: 'nope' }); assert.equal(r.status, 400); ok('malformed SWID refused');
  r = await post('/api/espn/link', { espn_s2: GOOD, swid: SW }); let j = await r.json();
  assert.equal(j.ok, true); assert.deepEqual(j.leagues.map((l) => l.id), ['4001', '4002']);
  assert.equal(j.leagues[0].commissioner, true); assert.equal(j.leagues[1].team, 'My Squad 4002'); ok('lists both football leagues on the account, this season only');
  const u = sql.prepare("SELECT espn_s2, swid FROM users WHERE id='espn:CCCCCCCC-1111-2222-3333-444444444444'").get();
  assert.ok(u && !u.espn_s2.includes('GOOD') && !u.swid.includes('CCCC')); ok('ESPN session stored encrypted on the account');
  const token = j.token;
  r = await post('/api/espn/check', { token, league: '4777' }); assert.equal(r.status, 403); ok('a league the account is not in is refused');
  r = await post('/api/espn/check', { token, league: '4003' }); j = await r.json(); assert.equal(j.league.name, 'Old College League'); ok('a league the list missed can be added by ID');
  r = await post('/api/espn/sync', { token, leagues: ['4777'] }); assert.equal(r.status, 400); ok('cannot sync a league that was never offered');
  const before = dispatched.length;
  r = await post('/api/espn/sync', { token, leagues: ['4001', '4002', '4003'] }); j = await r.json();
  assert.equal(j.ok, true); assert.equal(j.results.filter((x) => x.slug).length, 3); assert.equal(dispatched.length - before, 3); ok('three leagues added, three first prints queued');
  r = await post('/api/espn/sync', { token, leagues: ['4001'] }); assert.equal(r.status, 401); ok('token is single-use');
  jar = {};
  r = await call('GET', j.next); assert.equal(r.status, 303); assert.match(r.headers.get('Location'), /added=3/); ok('back on the site, signed in');
  r = await call('GET', j.next); assert.equal(r.status, 400); ok('return link is single-use');
  r = await call('GET', '/mine?added=3'); const page = await text(r);
  for (const n of ['Office League', 'Family League', 'Old College League']) assert.ok(page.includes(n));
  assert.match(page, /Added 3 leagues/); ok('My leagues shows all three');
  const off = sql.prepare("SELECT slug FROM leagues WHERE league_id='4001'").get().slug;
  r = await call('GET', `/l/${off}/settings`); assert.equal(r.status, 200); ok('commissioner of Office League gets Settings');
  const fam = sql.prepare("SELECT slug FROM leagues WHERE league_id='4002'").get().slug;
  r = await call('GET', `/l/${fam}/settings`); assert.equal(r.status, 403); ok('not commissioner of Family League → Settings locked');
  r = await call('GET', '/api/build/leagues?slug=' + fam, { headers: { Authorization: 'Bearer build-tok' } }); j = await r.json();
  assert.equal(j.leagues[0].espn_s2, GOOD); ok('printer gets the ESPN session for each league');
  r = await call('POST', '/api/espn/link', { body: JSON.stringify({ espn_s2: GOOD, swid: SW }), headers: ext, keepCookies: false }); j = await r.json();
  assert.ok(j.leagues.every((l) => l.linked)); ok('linking again marks leagues that already have a paper');
  r = await call('GET', '/'); assert.match(await text(r), /Link ESPN Fantasy account/); ok('home page has the Link ESPN button');
  r = await call('GET', '/extension.zip'); assert.equal(r.headers.get('Content-Type'), 'application/zip'); assert.ok((await r.arrayBuffer()).byteLength > 2000); ok('extension download');
  jar = savedJar;
}

console.log('cleanup');
await call('POST', `/l/${ySlug}/delete`, { form: {} });
assert.equal(sql.prepare('SELECT COUNT(*) n FROM leagues WHERE slug=?').get(ySlug).n, 0); ok('commissioner can remove a league');
r = await worker.fetch(new Request('https://fz.example/l/' + privSlug + '/settings', { method: 'POST', headers: { Origin: 'https://evil.example', Cookie: '' }, body: 'rules=on' }), env, ctx);
assert.equal(r.status, 403); ok('cross-site form posts refused');
console.log('\nall passed');
