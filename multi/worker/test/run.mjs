// Local test of the Worker without Cloudflare: D1 on Node's built-in SQLite, R2 in memory, Yahoo/ESPN/GitHub faked.
// node --no-warnings test/run.mjs
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import worker from '../src/index.js';

import { fakeGitHub } from './fake_github.mjs';
// ---- the data repo on GitHub (faked) ----
const gh = fakeGitHub('me/data');
const env = { DATA_REPO: 'me/data', SITE_URL: 'https://fz.example', SESSION_SECRET: 's'.repeat(32), ENC_KEY: 'k'.repeat(32), BUILD_TOKEN: 'build-tok',
  GITHUB_TOKEN: 'gh', YAHOO_CLIENT_ID: 'cid', YAHOO_CLIENT_SECRET: 'csec' };
const ctx = { waitUntil: () => {} };

// ---- fake outside world ----
const dispatched = [];
const YX = (inner) => `<?xml version="1.0"?><fantasy_content xmlns="http://fantasysports.yahooapis.com/fantasy/v2/base.rng">${inner}</fantasy_content>`;
globalThis.fetch = async (url, init = {}) => {
  url = String(url);
  if (url.includes('api.github.com')) {
    const r = await gh.handle(url, init);
    if (url.includes('print.yml/dispatches')) dispatched.push(gh.starts.at(-1).inputs.slug);
    return r;
  }
  if (url.includes('get_token')) {
    const b = new URLSearchParams(init.body);
    assert.equal(init.headers.Authorization, 'Basic ' + btoa('cid:csec'));
    return Response.json({ access_token: 'AT-' + b.get('grant_type'), refresh_token: 'RT1', expires_in: 3600, xoauth_yahoo_guid: 'GUID9' });
  }
  if (url.includes('games;game_keys=nfl/leagues')) return new Response(YX('<users><user><games><game><leagues><league><league_key>461.l.555</league_key><name>Sunday Funday</name><num_teams>10</num_teams><season>2026</season></league><league><league_key>461.l.556</league_key><name>Work League</name><num_teams>12</num_teams><season>2026</season></league>' + (globalThis.JOINED_557 ? '<league><league_key>461.l.557</league_key><name>New Yahoo League</name><num_teams>8</num_teams><season>2026</season></league>' : '') + '</leagues></game></games></user></users>'));
  if (url.includes('games;game_keys=nfl/teams')) return new Response(YX('<users><user><games><game><teams><team><team_key>461.l.555.t.3</team_key><name>Taco Tuesday</name><managers><manager><is_commissioner>1</is_commissioner><is_current_login>1</is_current_login></manager></managers></team><team><team_key>461.l.556.t.7</team_key><name>Spreadsheet Kings</name><managers><manager><is_current_login>1</is_current_login></manager></managers></team></teams></game></games></user></users>'));
  if (url.includes('fan.api.espn.com')) {
    if (!(init.headers?.Cookie || '').includes('espn_s2=GOOD')) return new Response('no', { status: 401 });
    return Response.json({ preferences: [
      { metaData: { entry: { abbrev: 'FFL', gameId: 1, seasonId: 2026, groups: [{ groupId: 4001 }] } } },
      { metaData: { entry: { abbrev: 'FFL', gameId: 1, seasonId: 2026, groups: [{ groupId: 4002 }] } } },
      { metaData: { entry: { abbrev: 'FFL', gameId: 1, seasonId: 2025, groups: [{ groupId: 3999 }] } } },   // last season: skipped
      ...(globalThis.JOINED_4004 ? [{ metaData: { entry: { abbrev: 'FFL', gameId: 1, seasonId: 2026, groups: [{ groupId: 4004 }] } } }] : []),
      { metaData: { entry: { abbrev: 'FBA', gameId: 3, seasonId: 2026, groups: [{ groupId: 5001 }] } } },   // basketball: skipped
      { type: { code: 'team' } } ] });
  }
  if (url.includes('lm-api-reads.fantasy.espn.com') && /leagues\/(400[1-4]|4777)/.test(url)) {
    const id = url.match(/leagues\/(\d+)/)[1], me = '{CCCCCCCC-1111-2222-3333-444444444444}';
    const mine = id !== '4777';
    return Response.json({ settings: { name: { 4001: 'Office League', 4002: 'Family League', 4003: 'Old College League', 4004: 'New Rivals League', 4777: 'Strangers' }[id] },
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
let r = await call('GET', '/'); assert.equal(r.status, 200); assert.match(await text(r), /Log in with ESPN/); ok('home');
r = await call('GET', '/espn'); assert.match(await text(r), /League ID/); ok('ESPN form');

console.log('ESPN');
r = await call('POST', '/espn', { form: { league: 'abc', season: '2026' } }); assert.equal(r.status, 400); ok('bad id rejected');
r = await call('POST', '/espn', { form: { league: '123456', season: '2026' } }); assert.equal(r.status, 400); assert.match(await text(r), /Log in with ESPN/); ok('no anonymous papers: a league needs an ESPN sign-in');
jar = {};
r = await call('POST', '/espn', { form: { league: '777', season: '2026', espn_s2: 'S2SECRET', swid: '{BBBB-2222}' } });
const privSlug = r.headers.get('Location').split('/')[2];
r = await call('GET', `/l/${privSlug}/settings`); assert.equal(r.status, 403); ok('league member (not manager) cannot open settings');
jar = {};
r = await call('POST', '/espn', { form: { league: '777', season: '2026', espn_s2: 'S2BOSS', swid: '{aaaa-1111}' } });
assert.equal(r.headers.get('Location').split('/')[2], privSlug); ok('same league → same paper, no duplicate');
r = await call('GET', `/l/${privSlug}/settings`); assert.equal(r.status, 200); assert.match(await text(r), /Optional tabs/); ok('ESPN manager opens settings');
const row = gh.json(`leagues/${privSlug}.json`);
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
// the printer writes editions straight into the data repo
gh.write(`papers/${privSlug}/index.html`, '<title>The Daily Fantasizer</title><header class="mast">M</header><p>paper</p>');
gh.write(`papers/${privSlug}/week8.html`, '<p>w8</p>');
const lineFile = { week: 9, nfl: [{ id: 'N:G1', title: 'CAR @ GB', lock: '2099-01-01T00:00:00Z', markets: [{ m: 'ml', label: 'Moneyline', sel: [{ id: 'N:G1:ml:a', name: 'CAR', odds: 150 }, { id: 'N:G1:ml:h', name: 'GB', odds: -170 }] }] },
  { id: 'N:G2', title: 'NYJ @ BUF', lock: '2000-01-01T00:00:00Z', markets: [{ m: 'ml', label: 'Moneyline', sel: [{ id: 'N:G2:ml:a', name: 'NYJ', odds: 300 }] }] }] };
gh.write(`papers/${privSlug}/bets/lines9.json`, JSON.stringify(lineFile));
await call('POST', `/api/build/${privSlug}/status`, { headers: { Authorization: 'Bearer build-tok' }, body: JSON.stringify({ status: 'ok', week: 8 }) });
r = await call('GET', `/l/${privSlug}/`); let t = await text(r); assert.match(t, /<p>paper<\/p>/); assert.match(t, /\/settings"/); ok('paper served, commissioner sees a Settings button');
jar = {}; r = await call('GET', `/l/${privSlug}/`); assert.equal(r.status, 303); assert.match(r.headers.get('Location'), /^\/login\?next=%2Fl%2F/); ok('signed out → sent to log in, then back to this paper');
r = await call('GET', `/l/${privSlug}/week8.html`); assert.equal(r.status, 303); ok('every edition needs a sign-in');
await call('POST', '/espn', { form: { league: '777', season: '2026', espn_s2: 'S2SECRET', swid: '{BBBB-2222}' } });
r = await call('GET', `/l/${privSlug}/`); t = await text(r); assert.match(t, /<p>paper<\/p>/); assert.doesNotMatch(t, /\/settings"/); ok('a league member reads it (no Settings)');
r = await call('GET', `/l/${privSlug}/archive`); assert.match(await text(r), /Week 8/); ok('archive lists editions');
gh.write(`papers/${privSlug}/week8.html`, '<section class="sec" id="ps-lineup" data-lu-me=""><template data-lu-team="1"><p>LU1</p></template><template data-lu-team="2"><p>LU2</p></template></section>');
r = await call('GET', `/l/${privSlug}/week8.html`); t = await text(r); assert.ok(!t.includes('LU1') && !t.includes('LU2') && t.includes('data-lu-me="0"')); ok('member without a team in the league gets no one\'s lineup');

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
r = await call('GET', '/api/office/nosuchleague1'); assert.equal(r.status, 404); ok('unknown league office refused');

console.log('Yahoo');
jar = {};
r = await call('GET', '/auth/yahoo'); const loc = new URL(r.headers.get('Location'));
assert.equal(loc.origin + loc.pathname, 'https://api.login.yahoo.com/oauth2/request_auth'); assert.equal(loc.searchParams.get('redirect_uri'), 'https://fz.example/auth/yahoo/callback'); ok('redirect to Yahoo');
r = await call('GET', `/auth/yahoo/callback?code=C1&state=WRONG`); assert.equal(r.status, 400); ok('state mismatch rejected');
{ const before = dispatched.length;
  r = await call('GET', `/auth/yahoo/callback?code=C1&state=${loc.searchParams.get('state')}`);
  assert.equal(r.headers.get('Location'), '/mine?added=2&found=2'); assert.equal(dispatched.length - before, 2);
  ok('signed in with Yahoo → every league on the account set up, first prints queued'); }
 { const rr = await call('GET', `/l/${privSlug}/`); assert.equal(rr.status, 403); assert.match(await text(rr), /Members only/); ok('signed in, but not in this league → members only'); }
r = await call('GET', '/mine?added=2&found=2'); t = await text(r); assert.match(t, /2 papers set up/); assert.match(t, /Sunday Funday[\s\S]*Commissioner/); assert.match(t, /every Tuesday/); ok('My leagues lists both, marks where you are commissioner');
r = await call('GET', '/yahoo'); t = await text(r); assert.match(t, /Sunday Funday/); assert.match(t, /Open paper/); ok('the Yahoo league list still opens each paper');
r = await call('POST', '/yahoo/league', { form: { key: '461.l.556' } }); const workSlug = r.headers.get('Location').split('/')[2];
r = await call('GET', `/l/${workSlug}/settings`); assert.equal(r.status, 403); ok('not commissioner of Work League → settings locked');
r = await call('POST', '/yahoo/league', { form: { key: '461.l.555' } }); const ySlug = r.headers.get('Location').split('/')[2];
r = await call('GET', `/l/${ySlug}/settings`); assert.equal(r.status, 200); ok('Yahoo commissioner opens settings');
{ const keep = { ...jar }; jar = {};
  const rr = await call('GET', `/l/${ySlug}/`); assert.equal(rr.status, 303); assert.match(rr.headers.get('Location'), /^\/auth\/yahoo\?next=%2Fl%2F/);
  ok('signed out on a Yahoo paper → Yahoo sign-in, then back to it');
  const go = await call('GET', rr.headers.get('Location')); const st = new URL(go.headers.get('Location')).searchParams.get('state');
  const back = await call('GET', `/auth/yahoo/callback?code=C1&state=${st}`); assert.equal(back.headers.get('Location'), `/l/${ySlug}/`); ok('…lands on that paper');
  jar = {}; const lp2 = await text(await call('GET', '/login')); assert.match(lp2, /Log in with Yahoo instead/); ok('the ESPN login page offers Yahoo');
  const no = await call('GET', '/auth/yahoo/callback?error=access_denied&state=x'); assert.equal(no.status, 400); assert.match(await text(no), /cancelled/); ok('saying no on Yahoo\'s page → a clear message');
  jar = keep; }
gh.write(`papers/${ySlug}/index.html`, '<header class="mast">M</header><section class="sec" id="ps-lineup" data-lu-me=""><template data-lu-team="1"><p>YLU1</p></template><template data-lu-team="3"><p>YLU3</p></template></section>');
r = await call('GET', `/l/${ySlug}/`); { const yt = await text(r); assert.ok(yt.includes('YLU3') && !yt.includes('YLU1') && yt.includes('data-lu-me="3"')); } ok('Yahoo member gets their own team\'s lineup');
r = await call('POST', '/yahoo/league', { form: { key: '461.l.999' } }); assert.equal(r.status, 403); ok('cannot add a league you are not in');
r = await call('GET', `/api/build/leagues?slug=${ySlug}`, { headers: { Authorization: 'Bearer build-tok' } });
assert.equal((await r.json()).leagues[0].yahoo_token, 'AT-refresh_token'); ok('printer gets a fresh Yahoo access token');
r = await call('GET', '/mine'); t = await text(r); assert.match(t, /Sunday Funday/); assert.match(t, /Work League/); ok('My leagues');
assert.match(t, /id="a2hs-btn"[^>]*>[\s\S]*Add to home screen/); assert.match(t, /rel="manifest" href="\/manifest\.webmanifest"/);
assert.match(t, /rel="apple-touch-icon" href="\/icons\/apple-touch-icon\.png"/); ok('My leagues has the Add to home screen button and app tags');

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
  const u = gh.json('users/espn_CCCCCCCC-1111-2222-3333-444444444444.json');
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
  assert.match(page, /3 papers set up/); ok('My leagues shows all three');
  const off = gh.slugOf('4001');
  r = await call('GET', `/l/${off}/settings`); assert.equal(r.status, 200); ok('commissioner of Office League gets Settings');
  const fam = gh.slugOf('4002');
  r = await call('GET', `/l/${fam}/settings`); assert.equal(r.status, 403); ok('not commissioner of Family League → Settings locked');
  r = await call('GET', '/api/build/leagues?slug=' + fam, { headers: { Authorization: 'Bearer build-tok' } }); j = await r.json();
  assert.equal(j.leagues[0].espn_s2, GOOD); ok('printer gets the ESPN session for each league');
  r = await call('POST', '/api/espn/link', { body: JSON.stringify({ espn_s2: GOOD, swid: SW }), headers: ext, keepCookies: false }); j = await r.json();
  assert.ok(j.leagues.every((l) => l.linked)); ok('linking again marks leagues that already have a paper');
  r = await call('GET', '/extension.zip'); assert.equal(r.headers.get('Content-Type'), 'application/zip'); assert.ok((await r.arrayBuffer()).byteLength > 2000); ok('extension download');
  jar = savedJar;
}

console.log('Log in with ESPN (server signs in; user only logs in)');
{
  const savedJar = { ...jar };
  const SW = '{CCCCCCCC-1111-2222-3333-444444444444}', GOOD = 'GOOD' + 'x'.repeat(60);
  const seen = [];
  env.__espnLogin = {
    start: async (e, email, pw) => { seen.push(pw); if (pw === 'bad') return { status: 'error', error: 'ESPN didn’t accept that email and password.', trace: ['opening', 'password entered', 'ESPN error shown'] };
      if (email.startsWith('code')) return { status: 'code', sessionId: 'SESS1', trace: ['code asked'] };
      return { status: 'ok', s2: GOOD, swid: SW, trace: ['signed in'] }; },
    code: async (e, sid, code) => { assert.equal(sid, 'SESS1'); return code === '123456' ? { status: 'ok', s2: GOOD, swid: SW, trace: ['code ok'] } : { status: 'code', again: true, trace: ['code wrong'] }; },
  };
  const login = (email, password) => call('POST', '/login', { form: { email, password } });
  jar = {};
  r = await call('GET', '/login'); assert.match(await text(r), /type="password"/); ok('login page: email and password only');
  r = await login('nope', 'x'); assert.equal(r.status, 400); ok('bad email refused before contacting ESPN');
  r = await login('me@example.com', 'bad'); assert.match(await text(r), /didn’t accept that email and password/); ok('wrong password explained');
  r = await login('me@example.com', 'right'); assert.equal(r.status, 303); assert.match(r.headers.get('Location'), /^\/mine\?added=\d+&found=2$/); ok('one login → every league on the account');
  r = await call('GET', r.headers.get('Location')); let page = await text(r);
  assert.ok(page.includes('Office League') && page.includes('Family League')); ok('My leagues lists them, signed in');
  const dump = gh.dump();
  assert.ok(!dump.includes('right') && !dump.includes('me@example.com')); ok('password and email never stored; traces have step names only');
  jar = {};
  r = await login('code@example.com', 'right'); assert.match(await text(r), /emailed a code/); assert.ok(jar.fz_login); ok('ESPN code step shown when ESPN asks');
  r = await call('POST', '/login/code', { form: { code: '999999' } }); assert.match(await text(r), /didn’t work/); ok('wrong code: ask again');
  r = await call('POST', '/login/code', { form: { code: '123 456' } }); assert.equal(r.status, 303); assert.match(r.headers.get('Location'), /found=2/); ok('right code → signed in, leagues set up');
  r = await call('POST', '/login/code', { form: { code: '123456' } }); assert.equal(r.status, 400); ok('code sign-in is single-use');
  { const slugs = ['4001', '4002'].map((id) => ({ slug: gh.slugOf(id), name: gh.json(`leagues/${gh.slugOf(id)}.json`).name }));
    for (const sl of slugs) gh.write(`papers/${sl.slug}/index.html`, `<!doctype html><title>x</title><header class="mast">${sl.name} paper</header>`);
    r = await call('GET', `/l/${slugs[0].slug}/`); page = await text(r);
    assert.ok(page.includes('fz-lgbar') && page.includes("querySelector('header.mast')") && page.includes('Office League') && page.includes('Family League')); ok('paper carries a switcher to every league you are in (placed above the masthead)');
    assert.equal((page.match(/aria-current="page"/g) || []).length, 1); ok('current league highlighted');
    const saved = { ...jar }; jar = {}; r = await call('GET', `/l/${slugs[0].slug}/`); assert.equal(r.status, 303); jar = saved; ok('a shared link without a sign-in goes to the login'); 
    // Optimal Lineup: every team's lineup is in the paper; the member gets only their own team (team 3 here)
    const lu = (t) => `<template data-lu-team="${t}"><p>lineup of team ${t}</p></template>`;
    gh.write(`papers/${slugs[0].slug}/index.html`, `<!doctype html><title>x</title><header class="mast">M</header><section class="sec" id="ps-lineup" data-lu-me=""><div class="lu-box"></div>${lu(1)}${lu(3)}${lu(12)}</section>`);
    r = await call('GET', `/l/${slugs[0].slug}/`); page = await text(r);
    assert.ok(page.includes('lineup of team 3') && !page.includes('lineup of team 1<') && !page.includes('lineup of team 12')); ok('Optimal Lineup: only the signed-in member\'s own team is served');
    assert.ok(page.includes('data-lu-me="3"')); ok('page told which team is yours (matched by ESPN account)');
    assert.equal(gh.json(`members/espn_CCCCCCCC-1111-2222-3333-444444444444.json`).teams[slugs[0].slug].team, 3); ok('team remembered for the member');
  }
  r = await call('POST', '/mine/add', { form: { league: '4777' } }); assert.match(r.headers.get('Location'), /err=/); ok('add by ID refuses a league you are not in');
  r = await call('POST', '/mine/add', { form: { league: 'https://fantasy.espn.com/football/league?leagueId=4003' } }); assert.match(r.headers.get('Location'), /added=1/); ok('add by ID from a league link');
  globalThis.JOINED_4004 = true; const before = dispatched.length;
  r = await call('POST', '/api/build/refresh', { headers: { Authorization: 'Bearer build-tok' }, keepCookies: false }); assert.equal(r.status, 200);
  assert.ok(gh.slugOf('4004')); ok('Tuesday refresh (asked by the printer) adds a league joined since');
  globalThis.JOINED_557 = true;
  r = await call('POST', '/api/build/refresh', { headers: { Authorization: 'Bearer build-tok' }, keepCookies: false });
  assert.ok(gh.json('index/leagues.json')['yahoo:461.l.557:2026']); ok('…on Yahoo accounts too');
  assert.ok(dispatched.length > before); ok('and queues its first print');
  for (const k of [...gh.files.keys()]) if (k.startsWith('limits/')) gh.files.delete(k);
  for (let i = 0; i < 6; i++) await login('me@example.com', 'bad');
  r = await login('me@example.com', 'right'); assert.equal(r.status, 429); ok('six tries in 15 minutes, then wait');
  r = await call('GET', '/api/build/login-traces', { headers: { Authorization: 'Bearer build-tok' } }); assert.ok((await r.json()).traces.length > 3); ok('sign-in traces readable for fixing ESPN changes');
  delete env.__espnLogin; jar = savedJar;
}

console.log('thedailyfantasizer.com front page');
{
  const saved = { ...jar };
  env.MAIN_LEAGUE = 'espn:777';
  gh.write('public/sample.html', '<title>The Daily Fantasizer</title><b>Log in to read the paper</b><span>Log in with the ESPN account that\'s in your league.</span><a class="fz-btn" id="fz-espn" href="/login?next=/">Log in with ESPN</a>\n    <button type="button" class="fz-btn" disabled title="Yahoo is coming soon">Log in with Yahoo <small>Soon</small></button><i class="fz-veil">blurred</i>');
  jar = {}; r = await call('GET', '/'); let t0 = await text(r);
  assert.match(t0, /Log in to read the paper/); assert.doesNotMatch(t0, /<p>paper<\/p>/); ok('signed out: the blurred sample and a log-in box, no real paper');
  assert.match(t0, /<a class="fz-btn" id="fz-yahoo" href="\/auth\/yahoo\?next=\/"/); assert.doesNotMatch(t0, /Soon/); assert.match(t0, /ESPN or Yahoo account/); ok('Yahoo set up → the front page\'s Log in with Yahoo button works');
  const cid = env.YAHOO_CLIENT_ID; delete env.YAHOO_CLIENT_ID;
  t0 = await text(await call('GET', '/')); assert.match(t0, /Log in with Yahoo <small>Soon<\/small>/); ok('no Yahoo keys → it stays "Soon"');
  t0 = await text(await call('GET', '/start')); assert.match(t0, /Coming soon/);
  const ya = await call('GET', '/auth/yahoo'); assert.equal(ya.status, 503); ok('…and Yahoo sign-in says it\'s coming soon');
  env.YAHOO_CLIENT_ID = cid; t0 = await text(await call('GET', '/start')); assert.match(t0, /href="\/auth\/yahoo"/); ok('start page Yahoo card switches on with the keys');
  r = await call('GET', '/week8.html'); assert.equal(r.headers.get('Location'), '/'); ok('old week links → front page when signed out');
  r = await call('GET', '/bets/lines9.json'); assert.equal(r.status, 200); assert.equal((await r.json()).week, 9); ok('betting board stays public (the league office checks bets against it)');
  r = await call('GET', '/sw.js'); assert.match(await text(r), /caches\.delete/); ok('old home-screen app: saved copy is cleared');
  r = await call('GET', '/login?next=/'); assert.equal(jar.fz_next, '%2F'); ok('log in from the front page comes back to it');
  jar = saved;
  r = await call('GET', '/'); assert.equal(r.status, 303); assert.match(r.headers.get('Location'), /^\/(l\/[a-z0-9]+\/|mine)$/); ok('signed in: the front page opens your paper');
  r = await call('GET', '/login'); assert.equal(r.status, 303); assert.equal(r.headers.get('Location'), '/'); ok('already signed in (another tab): the login page sends you on, no second login');
  r = await call('GET', '/login?next=%2Fl%2Fabcdefgh%2F'); assert.equal(r.headers.get('Location'), '/l/abcdefgh/'); ok('…straight to the paper that asked');
  r = await worker.fetch(new Request('https://www.fz.example/l/abc/'), env, ctx); assert.equal(r.status, 301); assert.equal(r.headers.get('Location'), 'https://fz.example/l/abc/'); ok('www → the one address, so the sign-in is always the same cookie');
  { const { sign } = await import('../src/crypto.js');
    const old = await sign(env, { uid: 'espn:ROLL', display: 'ESPN', exp: Date.now() + 20 * 864e5 });
    r = await worker.fetch(new Request('https://fz.example/mine', { headers: { Cookie: `fz_s=${old}` } }), env, ctx);
    assert.match(r.headers.get('Set-Cookie') || '', /fz_s=.*Max-Age=5184000/); ok('keeps reading → sign-in renewed for another 60 days'); }
  delete env.MAIN_LEAGUE;
}

console.log('sign-in job that never reports');
{ const { sha256 } = await import('../src/crypto.js');
  const id = 'stalejob00000001', t = 'tok123', old = new Date(Date.now() - 7 * 60000).toISOString();
  gh.write(`jobs/${id}.json`, JSON.stringify({ token_hash: await sha256(t), status: 'queued', created_at: old, updated_at: old, expires: new Date(Date.now() + 6e5).toISOString() }));
  const H = { headers: { Cookie: `fz_job=${id}.${t}` } };
  let s = await (await worker.fetch(new Request('https://fz.example/login/status', H), env, ctx)).json();
  assert.equal(s.status, 'error'); ok('queued for minutes with no word from the job → error, not an endless wait');
  const w = await worker.fetch(new Request('https://fz.example/login/wait', H), env, ctx);
  assert.equal(w.status, 400); assert.match(await w.text(), /didn.t start/); ok('the waiting page says to try again');
  const id2 = 'freshjob00000001', now = new Date().toISOString();
  gh.write(`jobs/${id2}.json`, JSON.stringify({ token_hash: await sha256(t), status: 'queued', created_at: now, expires: new Date(Date.now() + 6e5).toISOString() }));
  s = await (await worker.fetch(new Request('https://fz.example/login/status', { headers: { Cookie: `fz_job=${id2}.${t}` } }), env, ctx)).json();
  assert.equal(s.status, 'queued'); ok('a job that just started keeps waiting');
  const id3 = 'slowqueue0000001', four = new Date(Date.now() - 4 * 60000).toISOString();
  gh.write(`jobs/${id3}.json`, JSON.stringify({ token_hash: await sha256(t), status: 'queued', created_at: four, updated_at: four, expires: new Date(Date.now() + 6e5).toISOString() }));
  s = await (await worker.fetch(new Request('https://fz.example/login/status', { headers: { Cookie: `fz_job=${id3}.${t}` } }), env, ctx)).json();
  assert.equal(s.status, 'queued'); ok('four minutes in GitHub\'s queue still waits');
  const r = await worker.fetch(new Request(`https://fz.example/api/build/login/${id3}`, { method: 'POST', headers: { Authorization: `Bearer ${env.BUILD_TOKEN}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ status: 'starting' }) }), env, ctx);
  assert.equal(r.status, 200);
  s = await (await worker.fetch(new Request('https://fz.example/login/status', { headers: { Cookie: `fz_job=${id3}.${t}` } }), env, ctx)).json();
  assert.equal(s.status, 'starting'); ok('the job says it started → the page shows it and keeps waiting');
  const pg = await worker.fetch(new Request('https://fz.example/login/wait', { headers: { Cookie: `fz_job=${id3}.${t}` } }), env, ctx);
  assert.match(await pg.text(), /Opening ESPN/); ok('the waiting page says ESPN\'s login page is opening'); }

console.log('cleanup');
await call('POST', `/l/${ySlug}/delete`, { form: {} });
assert.equal(gh.json(`leagues/${ySlug}.json`), null); assert.ok(!Object.values(gh.json('index/leagues.json')).includes(ySlug)); ok('commissioner can remove a league');
r = await worker.fetch(new Request('https://fz.example/l/' + privSlug + '/settings', { method: 'POST', headers: { Origin: 'https://evil.example', Cookie: '' }, body: 'rules=on' }), env, ctx);
assert.equal(r.status, 403); ok('cross-site form posts refused');
console.log('\nall passed');
