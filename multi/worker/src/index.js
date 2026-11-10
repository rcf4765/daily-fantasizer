// The Daily Fantasizer for any league: sign-up site, paper host, commissioner settings, league office and build API.
// Runs on any host with fetch() (Cloudflare Workers today) and keeps nothing there: every account, league, vote, bet and
// printed paper lives in the private data repo on GitHub (data.js / store.js). The data repo's own workflows sign in to
// ESPN (espn-login.yml) and print the papers (print.yml); this site starts them and they report back here.
import { sign, verify, seal, open, sha256, randomId, randomCode, cookie, setCookie, same, jobSeal, hmacHex } from './crypto.js';
import { yahooAuthUrl, yahooExchange, yahooAccess, yahooUser, yahooLeagues, espnLeague, espnUserLeagues, espnSeason, validSwid, espnTeamOf, yahooTeamOf } from './platforms.js';
import { EXTENSION_ZIP } from './extension_zip.js';
import { espnLoginStart, espnLoginCode } from './espn_login.js';
import { officeGet, officePost } from './office.js';
import { makeData } from './data.js';
import * as P from './pages.js';

const html = (body, status = 200, headers = {}) => new Response(body, { status, headers: { 'Content-Type': 'text/html; charset=utf-8', 'X-Robots-Tag': 'noindex', 'Referrer-Policy': 'same-origin', ...headers } });
const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });
const redirect = (to, headers = {}) => new Response(null, { status: 303, headers: { Location: to, ...headers } });
const SESSION_DAYS = 60;

async function session(req, env) { return verify(env, cookie(req, 'fz_s')); }
async function startSession(env, uid, display) {
  return setCookie('fz_s', await sign(env, { uid, display, exp: Date.now() + SESSION_DAYS * 864e5 }), SESSION_DAYS * 86400);
}
async function form(req) { return Object.fromEntries((await req.formData()).entries()); }
const isComm = (L, s) => !!(s && L && L.commissioner_uid && s.uid === L.commissioner_uid);

/** Start a workflow in the private data repo (print.yml or espn-login.yml). Inputs carry the site's signature. */
async function startJob(env, workflow, inputs, signed) {
  if (!env.GITHUB_TOKEN || !env.DATA_REPO) return false;
  const r = await fetch(`https://api.github.com/repos/${env.DATA_REPO}/actions/workflows/${workflow}/dispatches`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${env.GITHUB_TOKEN}`, Accept: 'application/vnd.github+json', 'User-Agent': 'daily-fantasizer-site', 'X-GitHub-Api-Version': '2022-11-28' },
    body: JSON.stringify({ ref: env.DATA_BRANCH || 'main', inputs: { ...inputs, site: env.SITE_URL, sig: await hmacHex(env.BUILD_TOKEN || '', `${env.SITE_URL}|${signed}`) } }),
  });
  if (!r.ok) console.log('start job failed', workflow, r.status, await r.text());
  return r.ok;
}

/** Ask the printer to print one league (or every league when slug is empty). */
async function dispatch(env, D, slug = '') {
  if (slug) {
    const L = await D.league(slug);
    if (L && L.last_dispatch_at && Date.now() - Date.parse(L.last_dispatch_at) < 120000) return true;  // a run was just started
    await D.patchLeague(slug, (L) => ({ last_dispatch_at: new Date().toISOString(), status: L.status === 'ok' ? 'ok' : 'queued' }));
  }
  return startJob(env, 'print.yml', { slug }, slug);
}

async function createOrUpdateLeague(env, D, { platform, leagueId, season, name, teams, uid, commissioner, s2, swid, tokenUid }) {
  let L = await D.findLeague(platform, String(leagueId), season);
  if (!L) {
    L = await D.createLeague({ slug: randomId(10), platform, league_id: String(leagueId), season, name, teams,
      commissioner_uid: commissioner ? uid : null, token_uid: tokenUid || null, espn_s2: await seal(env, s2), swid: await seal(env, swid),
      feat_rules: 0, feat_bets: 0, accent: '#33658a', comm_code_hash: null, status: 'queued', status_msg: null,
      last_week: null, last_built_at: null, last_dispatch_at: null, created_by: uid, created_at: new Date().toISOString() });
    await dispatch(env, D, L.slug);
  } else {
    // fresher credentials win; a verified commissioner takes over the settings
    const patch = { name, teams };
    if (s2 && swid) Object.assign(patch, { espn_s2: await seal(env, s2), swid: await seal(env, swid) });
    if (tokenUid) patch.token_uid = tokenUid;
    if (commissioner) patch.commissioner_uid = uid;
    const wasError = L.status === 'error';
    L = (await D.patchLeague(L.slug, patch)) || L;
    if (wasError && (s2 || tokenUid)) await dispatch(env, D, L.slug);  // new credentials: try again
  }
  await D.remember(uid, L.slug, commissioner);
  return L;
}

/** The signed-in member's team in this league, for Optimal Lineup. ESPN: the team whose owners include their SWID
 *  (uid = espn:<SWID>), asked of ESPN with the league's stored session. Yahoo: the team Yahoo marks as theirs.
 *  A found team is remembered for a day; "no team" is never remembered, so the next view asks again. */
async function viewerTeam(env, D, L, uid) {
  if (!L) return null;
  const k = await D.memberTeam(uid, L.slug);
  if (k && k.team && Date.now() - Date.parse(k.at) < 86400e3) return k.team;
  let t;
  if (L.platform === 'espn' && String(uid).startsWith('espn:')) {
    let s2 = null, swid = null;
    try { if (L.espn_s2 && L.swid) { s2 = await open(env, L.espn_s2); swid = await open(env, L.swid); } } catch (e) { /* public league */ }
    t = await espnTeamOf(L.league_id, L.season, s2, swid, uid.slice(5));
  } else if (L.platform === 'yahoo' && String(uid).startsWith('yahoo:')) {
    t = await yahooTeamOf(await yahooAccess(env, uid, D), L.league_id).catch(() => undefined);
  }
  if (t === undefined) return k ? k.team : null;   // couldn't ask: keep what we knew
  if (t) await D.setMemberTeam(uid, L.slug, t).catch(() => {});
  return t;
}

/** Optimal Lineup: the paper carries every team's lineup in <template data-lu-team="N">; a member gets only their own. */
function onlyMyLineup(page, team) {
  if (page.indexOf('data-lu-team="') < 0) return page;
  return page.replace(/<template data-lu-team="(\d+)">[\s\S]*?<\/template>/g, (m, t) => (team && +t === +team ? m : ''))
    .replace('id="ps-lineup" data-lu-me=""', `id="ps-lineup" data-lu-me="${team ? +team : 0}"`);
}

/** One ESPN account → every football league on it gets a paper. Used by the login, the extension and the weekly refresh. */
/** Leagues found by the sign-in job's browser (trusted: the job authenticates with BUILD_TOKEN); cleaned up. */
function cleanLeagues(list, season) {
  if (!Array.isArray(list)) return null;
  return list.filter((l) => l && /^\d{3,12}$/.test(String(l.id))).slice(0, 20).map((l) => ({ id: String(l.id), season,
    name: String(l.name || `League ${l.id}`).slice(0, 100), teams: Math.max(0, Math.min(40, parseInt(l.teams, 10) || 0)),
    team: String(l.team || '').slice(0, 100), commissioner: !!l.commissioner }));
}

async function linkEspnAccount(env, D, s2, swid, given = null) {
  const season = espnSeason();
  const uid = `espn:${String(swid).toUpperCase().replace(/[{}]/g, '')}`;
  await D.saveUser(uid, { platform: 'espn', espn_s2: await seal(env, s2), swid: await seal(env, swid) });
  const fromJob = cleanLeagues(given, season);
  const res = fromJob && fromJob.length ? { leagues: fromJob } : await espnUserLeagues(s2, swid, season);
  if (res.error) return { uid, error: res.error, leagues: [] };
  const leagues = [];
  for (const l of res.leagues) {
    const had = await D.findLeague('espn', l.id, season);
    const L = await createOrUpdateLeague(env, D, { platform: 'espn', leagueId: l.id, season, name: l.name, teams: l.teams, uid, commissioner: l.commissioner, s2, swid });
    leagues.push({ ...l, slug: L.slug, isNew: !had });
  }
  return { uid, leagues, listError: res.listError || '' };
}
/** Weekly (the printer asks first): every linked ESPN account picks up leagues it joined since; expired sessions are
 *  marked so the user is asked to log in again. */
async function refreshEspnAccounts(env, D) {
  for (const u of (await D.allUsers()).filter((x) => x.platform === 'espn' && x.espn_s2)) {
    try {
      // only adds leagues; an expired sign-in shows up when the printer can't read a league (ESPN answers it 401)
      await linkEspnAccount(env, D, await open(env, u.espn_s2), await open(env, u.swid));
    } catch (e) { console.log('refresh failed', u.id, e.message); }
  }
}
const signer = (env) => env.__espnLogin || { start: espnLoginStart, code: espnLoginCode };
async function finishLogin(env, D, r) {
  const acct = await linkEspnAccount(env, D, r.s2, r.swid);
  const headers = new Headers({ Location: `/mine?added=${acct.leagues.filter((l) => l.isNew).length}&found=${acct.leagues.length}` });
  headers.append('Set-Cookie', await startSession(env, acct.uid, 'ESPN'));
  headers.append('Set-Cookie', setCookie('fz_login', '', 0));
  return new Response(null, { status: 303, headers });
}

// ---------------- pages ----------------
async function route(req, env, ctx) {
  const url = new URL(req.url), path = url.pathname, method = req.method;
  // the old workers.dev address: people go to the real one (the GitHub jobs and APIs keep working on both)
  if (env.SITE_URL && url.origin !== new URL(env.SITE_URL).origin && method === 'GET' && !path.startsWith('/api/')
      && (url.hostname.endsWith('.workers.dev') || url.hostname === 'www.' + new URL(env.SITE_URL).hostname)) {
    return Response.redirect(env.SITE_URL + path + url.search, 301);
  }
  const s = await session(req, env);
  const D = makeData(env);

  if (method === 'POST' && !path.startsWith('/api/')) {  // forms: same-site only
    const o = req.headers.get('Origin');
    if (o && o !== new URL(env.SITE_URL).origin) return html(P.message('Not allowed', 'That form came from another site.'), 403);
  }

  // ---- the front page and the old public addresses (thedailyfantasizer.com used to be the Men Fantasizing paper) ----
  const mainSlug = async () => (env.MAIN_LEAGUE ? (await D.index())[`${env.MAIN_LEAGUE}:${espnSeason()}`] || '' : '');
  if (path === '/' && method === 'GET') {
    if (s) {   // signed in: straight to your paper (the main league first, if you're in it)
      const mine = await D.myLeagues(s.uid), main = await mainSlug();
      const pick = mine.find((L) => L.slug === main) || mine.sort((a, b) => a.name.localeCompare(b.name))[0];
      return redirect(pick ? `/l/${pick.slug}/` : '/mine');
    }
    const sample = await D.st.raw('public/sample.html').catch(() => null);   // the paper, blurred, made-up names
    return sample ? html(sample.body, 200, { 'Cache-Control': 'no-cache' }) : html(P.home(env, false));
  }
  if (path === '/start' && method === 'GET') return html(P.home(env, !!s));
  {
    const lm = path.match(/^\/(bets\/lines\d{1,2}\.json|rulebook\.json)$/);
    if (lm && method === 'GET') {   // public: the league office (Google Sheet) checks bets and rules against these
      const slug = await mainSlug(), f = slug && await D.paper(slug, lm[1]);
      return f ? new Response(f.body, { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-cache', 'Access-Control-Allow-Origin': '*' } }) : json({ error: 'not found' }, 404);
    }
    if (path === '/sw.js') {   // the old home-screen app kept a copy of the paper offline: this clears it
      return new Response(`self.addEventListener('install',()=>self.skipWaiting());self.addEventListener('activate',e=>e.waitUntil((async()=>{for(const k of await caches.keys())await caches.delete(k);await self.clients.claim();await self.registration.unregister();for(const c of await self.clients.matchAll({type:'window'}))c.navigate(c.url)})()));`,
        { headers: { 'Content-Type': 'text/javascript', 'Cache-Control': 'no-cache' } });
    }
    if (/^\/(manifest\.webmanifest|icons\/[a-z0-9._-]+\.png)$/.test(path) && env.CODE_REPO) {
      const f = await fetch(`https://raw.githubusercontent.com/${env.CODE_REPO}/main/docs${path}`);
      return new Response(f.body, { status: f.status, headers: { 'Content-Type': path.endsWith('.png') ? 'image/png' : 'application/manifest+json', 'Cache-Control': 'public, max-age=86400' } });
    }
    const old = path.match(/^\/(index\.html|archive\.html|install\.html|week(\d{1,2})\.html)$/);
    if (old && method === 'GET') {
      const slug = s && await mainSlug();
      return redirect(!slug ? '/' : old[2] ? `/l/${slug}/week${old[2]}.html` : old[1] === 'archive.html' ? `/l/${slug}/archive` : `/l/${slug}/`);
    }
  }
  if (path === '/signout') return redirect('/', { 'Set-Cookie': setCookie('fz_s', '', 0) });

  // ---- Yahoo ----
  if (path === '/auth/yahoo') {
    if (!env.YAHOO_CLIENT_ID) return html(P.message('Yahoo isn’t set up yet', 'The site owner still has to register the Yahoo app (see the setup guide).'), 503);
    const state = randomId(24);
    return redirect(yahooAuthUrl(env, state), { 'Set-Cookie': setCookie('fz_oauth', state, 600) });
  }
  if (path === '/auth/yahoo/callback') {
    const state = url.searchParams.get('state'), code = url.searchParams.get('code');
    if (!code || !state || state !== cookie(req, 'fz_oauth')) return html(P.message('Sign-in expired', 'Start again from the home page.'), 400);
    try {
      const tok = await yahooExchange(env, code);
      const guid = tok.xoauth_yahoo_guid || (await yahooUser(tok.access_token)).guid;
      const uid = `yahoo:${guid}`;
      await D.saveUser(uid, { platform: 'yahoo', yahoo_refresh: await seal(env, tok.refresh_token) });
      const headers = new Headers({ Location: '/yahoo' });
      headers.append('Set-Cookie', await startSession(env, uid, 'Yahoo'));
      headers.append('Set-Cookie', setCookie('fz_oauth', '', 0));
      return new Response(null, { status: 303, headers });
    } catch (e) {
      return html(P.message('Yahoo sign-in failed', e.message), 502);
    }
  }
  if (path === '/yahoo' && method === 'GET') {
    if (!s || !s.uid.startsWith('yahoo:')) return redirect('/auth/yahoo');
    try {
      const leagues = await yahooLeagues(await yahooAccess(env, s.uid, D));
      const existing = {};
      for (const l of leagues) {
        const row = await D.findLeague('yahoo', l.key, l.season);
        if (row) existing[l.key] = row.slug;
      }
      return html(P.pickYahoo(leagues, existing));
    } catch (e) {
      return html(P.message('Couldn’t read your Yahoo leagues', e.message), 502);
    }
  }
  if (path === '/yahoo/league' && method === 'POST') {
    if (!s || !s.uid.startsWith('yahoo:')) return redirect('/auth/yahoo');
    const f = await form(req);
    const leagues = await yahooLeagues(await yahooAccess(env, s.uid, D));
    const l = leagues.find((x) => x.key === f.key);
    if (!l) return html(P.message('Not your league', 'That league isn’t on your Yahoo account.', '/yahoo'), 403);
    const L = await createOrUpdateLeague(env, D, { platform: 'yahoo', leagueId: l.key, season: l.season, name: l.name, teams: l.teams,
      uid: s.uid, commissioner: l.commissioner, tokenUid: s.uid });
    return redirect(`/l/${L.slug}/`);
  }

  // ---- ESPN: log in once (the server signs in to ESPN; the password is used once, never stored) ----
  const nextOk = (n) => (n === '/' || (/^\/l\/[a-z0-9]{6,16}\/[a-z0-9./-]*$/.test(n || '') && !n.includes('..')) ? n : '');
  if (path === '/login' && method === 'GET') {
    const next = nextOk(url.searchParams.get('next'));
    if (s) return redirect(next || '/');   // already signed in (in any tab): no second login
    return html(P.espnLogin({ next }), 200, next ? { 'Set-Cookie': setCookie('fz_next', next, 1800) } : {});
  }
  if (path === '/login' && method === 'POST') {
    const f = await form(req);
    const email = String(f.email || '').trim(), password = String(f.password || '');
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) || !password) return html(P.espnLogin({ error: 'Enter the email and password you use for ESPN.', email }), 400);
    const ip = req.headers.get('CF-Connecting-IP') || req.headers.get('X-Forwarded-For') || 'local';
    if ((await D.attempt(ip)) > 6) return html(P.espnLogin({ error: 'Too many tries. Wait 15 minutes and try again.', email }), 429);
    if (!env.BROWSER && !env.__espnLogin) {
      // A GitHub Actions run in the private data repo signs in (espn-login.yml). The login goes to it encrypted, inside
      // the job's start request, and is never stored: jobs/<id>.json only tracks progress.
      if (!env.LOGIN_KEY) return html(P.espnLogin({ error: 'ESPN sign-in isn’t switched on yet.', email }), 503);
      if (email.length + password.length > 300) return html(P.espnLogin({ error: 'That email or password is too long.', email }), 400);
      const id = randomId(16), t = randomId(32);
      await D.setTemp('jobs', id, { token_hash: await sha256(t), status: 'queued', created_at: new Date().toISOString() }, 15);
      if (!(await startJob(env, 'espn-login.yml', { job: id, login: await jobSeal(env, JSON.stringify({ email, password })) }, id))) {
        await D.setTemp('jobs', id, { status: 'error', msg: 'Couldn’t start the ESPN sign-in.' }, 15);
        return html(P.espnLogin({ error: 'Couldn’t start the ESPN sign-in. Try again in a minute.', email }), 502);
      }
      return redirect('/login/wait', { 'Set-Cookie': setCookie('fz_job', `${id}.${t}`, 900) });
    }
    const r = await signer(env).start(env, email, password);
    await D.trace(r.status !== 'error', r.trace);
    if (r.status === 'ok') return finishLogin(env, D, r);
    if (r.status === 'code') {
      const t = randomId(32);
      await D.setTemp('links', await sha256(t), { session_id: r.sessionId, tries: 0 }, 10);
      return html(P.espnCode({ email }), 200, { 'Set-Cookie': setCookie('fz_login', t, 600) });
    }
    return html(P.espnLogin({ error: r.error, email }), 400);
  }
  // ---- free-plan sign-in: waiting page, status, code, finish ----
  const job = async () => {
    const [id, t] = String(cookie(req, 'fz_job') || '').split('.');
    if (!/^[a-z0-9]{16}$/.test(id || '') || !t) return null;
    const j = await D.temp('jobs', id);
    if (!j || j.token_hash !== await sha256(t)) return null;
    // A job that never reported (GitHub didn't start it, or it stopped before it could) would leave the page waiting
    // until the 15-minute expiry: give up after a few quiet minutes and say so.
    const quiet = Date.now() - Date.parse(j.updated_at || j.created_at);
    if ((j.status === 'queued' && quiet > 180000) || ((j.status === 'running' || j.status === 'code_sent') && quiet > 300000)) {
      const msg = j.status === 'queued' ? 'The ESPN sign-in didn’t start. Try again.' : 'The ESPN sign-in stopped partway. Try again.';
      await D.setTemp('jobs', id, { status: 'error', msg }, 15);
      return { ...j, id, status: 'error', msg };
    }
    return { ...j, id };
  };
  if (path === '/login/status' && method === 'GET') {
    const j = await job();
    return json({ status: j ? j.status : 'expired' });
  }
  if (path === '/login/wait' && method === 'GET') {
    const j = await job();
    if (!j) return html(P.espnLogin({ error: 'That sign-in timed out. Log in again.' }), 400);
    if (j.status === 'ok') return redirect('/login/finish');
    if (j.status === 'error') return html(P.espnLogin({ error: j.msg || 'Signing in to ESPN failed. Try again in a minute.' }), 400);
    if (j.status === 'code' || j.status === 'code_wrong') return html(P.espnCode({ error: j.status === 'code_wrong' ? 'That code didn’t work. Check the newest email from ESPN.' : '', wait: true }));
    return html(P.loginWait(j.status, Date.now() - Date.parse(j.created_at)));
  }
  if (path === '/login/finish' && method === 'GET') {
    const j = await job();
    if (!j || j.status !== 'ok' || j.finished) return redirect(s ? '/mine' : '/login');
    await D.setTemp('jobs', j.id, { finished: 1 }, 15);
    const next = nextOk(cookie(req, 'fz_next'));
    const headers = new Headers({ Location: next || `/mine?added=${j.added || 0}&found=${j.found || 0}` });
    headers.append('Set-Cookie', await startSession(env, j.uid, 'ESPN'));
    headers.append('Set-Cookie', setCookie('fz_job', '', 0));
    if (next) headers.append('Set-Cookie', setCookie('fz_next', '', 0));
    return new Response(null, { status: 303, headers });
  }
  if (path === '/login/code' && method === 'POST' && cookie(req, 'fz_job')) {
    const j = await job();
    if (!j) return html(P.espnLogin({ error: 'That sign-in timed out. Log in again.' }), 400);
    const f = await form(req);
    const code = String(f.code || '').replace(/\D/g, '');
    if (code.length < 4 || code.length > 8) return html(P.espnCode({ error: 'Enter the code from ESPN’s email.', wait: true }), 400);
    await D.setTemp('jobs', j.id, { code_enc: await jobSeal(env, code), status: 'code_sent' }, 15);
    return redirect('/login/wait');
  }
  if (path === '/login/code' && method === 'POST') {
    const f = await form(req);
    const key = await sha256(cookie(req, 'fz_login') || '');
    const row = await D.temp('links', key);
    if (!row || !row.session_id) return html(P.espnLogin({ error: 'That sign-in timed out. Log in again.' }), 400);
    const code = String(f.code || '').replace(/\D/g, '');
    if (code.length < 4 || code.length > 8) return html(P.espnCode({ error: 'Enter the code from ESPN’s email.' }), 400);
    if (row.tries >= 4) return html(P.espnLogin({ error: 'Too many wrong codes. Log in again.' }), 400);
    await D.setTemp('links', key, { tries: row.tries + 1 }, 10);
    const r = await signer(env).code(env, row.session_id, code);
    await D.trace(r.status !== 'error', r.trace);
    if (r.status === 'ok') { await D.dropTemp('links', key); return finishLogin(env, D, r); }
    if (r.status === 'code') return html(P.espnCode({ error: 'That code didn’t work. Check the newest email from ESPN.' }), 400);
    return html(P.espnLogin({ error: r.error }), 400);
  }
  if (path === '/mine/add' && method === 'POST') {   // a league ESPN's list missed, by ID, with the stored ESPN session
    if (!s || !s.uid.startsWith('espn:')) return redirect('/login');
    const f = await form(req);
    const id = String(f.league || '').match(/leagueId=(\d+)/)?.[1] || String(f.league || '').trim().match(/^\d{3,12}$/)?.[0];
    const u = await D.user(s.uid);
    if (!id || !u || !u.espn_s2) return redirect('/mine?err=' + encodeURIComponent('That doesn’t look like an ESPN league ID.'));
    const s2 = await open(env, u.espn_s2), swid = await open(env, u.swid), season = espnSeason();
    const info = await espnLeague(id, season, s2, swid);
    if (info.error || !info.member) return redirect('/mine?err=' + encodeURIComponent(info.error || `Your ESPN account isn’t in ${info.name}.`));
    await createOrUpdateLeague(env, D, { platform: 'espn', leagueId: id, season, name: info.name, teams: info.teams, uid: s.uid, commissioner: info.commissioner, s2, swid });
    return redirect('/mine?added=1');
  }

  // ---- ESPN by league ID (no sign-in; public leagues, or pasted cookies) ----
  if (path === '/espn' && method === 'GET') return html(P.espnForm());
  if (path === '/espn' && method === 'POST') {
    const f = await form(req);
    const m = String(f.league || '').match(/leagueId=(\d+)/) || String(f.league || '').match(/^\s*(\d{3,12})\s*$/);
    const season = parseInt(f.season, 10) || new Date().getUTCFullYear();
    if (!m) return html(P.espnForm({ error: 'That doesn’t look like an ESPN league ID.', leagueId: f.league, season }), 400);
    const s2 = String(f.espn_s2 || '').trim(), swid = String(f.swid || '').trim();
    // everyone signs in: a league is only set up with an ESPN sign-in that proves the person is in it
    if (!s2 || !swid) return html(P.espnForm({ error: 'Log in with ESPN instead: papers are for league members, so we need to know you’re in the league.', leagueId: f.league, season }), 400);
    const info = await espnLeague(m[1], season, s2, swid);
    if (info.error) return html(P.espnForm({ error: info.error, leagueId: f.league, season }), 400);
    if (s2 && !info.member) return html(P.espnForm({ error: 'Those cookies belong to an ESPN account that isn’t in this league.', leagueId: f.league, season }), 403);
    const uid = s2 ? `espn:${swid.toUpperCase().replace(/[{}]/g, '')}` : (s && s.uid) || `anon:${randomId(16)}`;
    const L = await createOrUpdateLeague(env, D, { platform: 'espn', leagueId: m[1], season, name: info.name, teams: info.teams, uid,
      commissioner: info.commissioner, s2: s2 || null, swid: swid || null });
    return redirect(`/l/${L.slug}/`, { 'Set-Cookie': await startSession(env, uid, 'ESPN') });
  }

  // ---- ESPN through the browser extension (works like FantasyPros' ESPN sync) ----
  // /api/espn/link: the extension sends the ESPN session after you sign in on ESPN → we store it encrypted on your
  //   account and answer with every football league on that account plus a short-lived, single-use token.
  // /api/espn/check: a league the list missed, by ID. /api/espn/sync: the leagues you ticked → one paper each.
  // /espn/done: back on this site with a session; the token is used up.
  if (path.startsWith('/api/espn/') && method === 'POST') {
    if (!req.headers.get('X-Fantasizer-Extension')) return json({ ok: false, error: 'Use the Daily Fantasizer extension.' }, 400);
    let b = {};
    try { b = await req.json(); } catch (e) { return json({ ok: false, error: 'Bad request.' }, 400); }
    const season = espnSeason();
    if (path === '/api/espn/link') {
      const s2 = String(b.espn_s2 || '').trim(), swid = String(b.swid || '').trim();
      if (s2.length < 40 || !validSwid(swid)) return json({ ok: false, error: 'ESPN’s sign-in looks incomplete. Sign out of ESPN, sign in again and retry.' }, 400);
      const res = await espnUserLeagues(s2, swid, season);
      if (res.error) return json({ ok: false, error: res.error }, 401);
      const uid = `espn:${swid.toUpperCase().replace(/[{}]/g, '')}`;
      await D.saveUser(uid, { platform: 'espn', espn_s2: await seal(env, s2), swid: await seal(env, swid) });
      for (const l of res.leagues) l.linked = !!(await D.findLeague('espn', l.id, season));
      const token = randomId(32);
      await D.setTemp('links', await sha256(token), { uid, leagues: res.leagues.map((l) => l.id), synced: 0 }, 30);
      return json({ ok: true, token, leagues: res.leagues, listError: res.listError || '' });
    }
    const linkKey = await sha256(String(b.token || ''));
    const link = await D.temp('links', linkKey);
    if (!link || link.synced || !link.uid) return json({ ok: false, error: 'This link expired. Start again from The Daily Fantasizer.' }, 401);
    const u = await D.user(link.uid);
    const s2 = await open(env, u.espn_s2), swid = await open(env, u.swid);
    const known = link.leagues || [];
    if (path === '/api/espn/check') {
      const id = String(b.league || '').match(/^\d{3,12}$/)?.[0];
      if (!id) return json({ ok: false, error: 'That doesn’t look like an ESPN league ID.' }, 400);
      const info = await espnLeague(id, season, s2, swid);
      if (info.error) return json({ ok: false, error: info.error }, 400);
      if (!info.member) return json({ ok: false, error: `This ESPN account isn’t in ${info.name}.` }, 403);
      if (!known.includes(id)) await D.setTemp('links', linkKey, { leagues: [...known, id] }, 30);
      const linked = !!(await D.findLeague('espn', id, season));
      return json({ ok: true, league: { id, name: info.name, teams: info.teams, team: info.team, commissioner: info.commissioner, season, linked } });
    }
    if (path === '/api/espn/sync') {
      const ids = [...new Set((Array.isArray(b.leagues) ? b.leagues : []).map(String))].filter((id) => known.includes(id)).slice(0, 20);
      if (!ids.length) return json({ ok: false, error: 'Pick at least one league.' }, 400);
      const results = [];
      for (const id of ids) {
        const info = await espnLeague(id, season, s2, swid);
        if (info.error || !info.member) { results.push({ id, error: info.error || 'This ESPN account isn’t in that league.' }); continue; }
        const L = await createOrUpdateLeague(env, D, { platform: 'espn', leagueId: id, season, name: info.name, teams: info.teams, uid: link.uid,
          commissioner: info.commissioner, s2, swid });
        results.push({ id, name: info.name, slug: L.slug });
      }
      const added = results.filter((r) => r.slug).length;
      if (!added) return json({ ok: false, error: results[0].error, results }, 400);
      const done = randomId(32);
      await D.setTemp('links', linkKey, { synced: 1 }, 30);
      await D.setTemp('links', await sha256(done), { done_for: link.uid, results }, 60);
      return json({ ok: true, next: `/espn/done?t=${done}`, results });
    }
    return json({ ok: false, error: 'Not found.' }, 404);
  }
  if (path === '/espn/done' && method === 'GET') {
    const doneKey = await sha256(url.searchParams.get('t') || '');
    const link = await D.temp('links', doneKey);
    if (!link || !link.done_for) return html(P.message('Link expired', 'Start again with Link ESPN Fantasy account.'), 400);
    await D.dropTemp('links', doneKey);
    link.uid = link.done_for;
    const res = link.results || [];
    const failed = res.filter((r) => r.error).map((r) => `League ${r.id}: ${r.error}`);
    const q = new URLSearchParams({ added: String(res.filter((r) => r.slug).length) });
    if (failed.length) q.set('failed', failed.join('|').slice(0, 600));
    return redirect(`/mine?${q}`, { 'Set-Cookie': await startSession(env, link.uid, 'ESPN') });
  }
  if (path === '/extension.zip') {
    return new Response(Uint8Array.from(atob(EXTENSION_ZIP), (c) => c.charCodeAt(0)), { headers: { 'Content-Type': 'application/zip',
      'Content-Disposition': 'attachment; filename="daily-fantasizer-espn-extension.zip"' } });
  }

  if (path === '/mine') {
    if (!s) return redirect('/');
    const results = (await D.myLeagues(s.uid)).sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
    return html(P.mine(results.map((L) => ({ ...L, is_comm: L.commissioner_uid === s.uid })),
      { added: +url.searchParams.get('added') || 0, found: url.searchParams.get('found'), espn: s.uid.startsWith('espn:'),
        failed: (url.searchParams.get('failed') || '').split('|').concat(url.searchParams.get('err') || '').filter(Boolean) }));
  }

  // ---- a league's paper ----
  let m = path.match(/^\/l\/([a-z0-9]{6,16})(\/.*)?$/);
  if (m) {
    const L = await D.league(m[1]);
    if (!L) return html(P.message('No such paper', 'Check the link, or set your league up from the home page.'), 404);
    const rest = m[2] || '';
    if (!rest) return redirect(`/l/${L.slug}/`);
    if (rest === '/settings' || rest === '/code' || rest === '/rebuild' || rest === '/delete') {
      if (!isComm(L, s)) {
        const how = L.platform === 'yahoo' ? 'Sign in with Yahoo as the league’s commissioner, then open this page again.'
          : 'Set the league up again from the ESPN page with the commissioner’s espn_s2 and SWID cookies, then open this page again.';
        return html(P.message('Commissioners only', how, `/l/${L.slug}/`), 403);
      }
      if (rest === '/settings' && method === 'GET') return html(P.settings(env, L));
      if (rest === '/settings' && method === 'POST') {
        const f = await form(req);
        const rules = f.rules ? 1 : 0, bets = f.bets ? 1 : 0;
        const accent = /^#[0-9a-f]{6}$/i.test(f.accent || '') ? f.accent : L.accent;
        let code = '';
        if ((rules || bets) && !L.comm_code_hash) code = randomCode();
        await D.patchLeague(L.slug, { feat_rules: rules, feat_bets: bets, accent, ...(code ? { comm_code_hash: await sha256(code) } : {}) });
        await dispatch(env, D, L.slug);
        return html(P.settings(env, await D.league(L.slug), { saved: true, code }));
      }
      if (rest === '/code' && method === 'POST') {
        const code = randomCode();
        await D.patchLeague(L.slug, { comm_code_hash: await sha256(code) });
        return html(P.settings(env, await D.league(L.slug), { code }));
      }
      if (rest === '/rebuild' && method === 'POST') {
        await dispatch(env, D, L.slug);
        return html(P.settings(env, await D.league(L.slug), { saved: true }));
      }
      if (rest === '/delete' && method === 'POST') {
        await D.deleteLeague(L.slug);
        return html(P.message('League removed', 'Every paper and record for that league is gone from this site.'));
      }
    }
    // Papers are for the league's members only: signed in, and the ESPN account is in this league
    // (membership is recorded when that account signs in and its leagues are found; viewing never adds it).
    if (!s) return redirect(`/login?next=${encodeURIComponent(`/l/${L.slug}${rest}`)}`);
    if (!isComm(L, s) && !(await D.memberships(s.uid))[L.slug]) {
      return html(P.message('Members only', `This paper is for ${L.name}. Log in with the ESPN account that's in this league.`, '/mine'), 403);
    }
    if (rest === '/archive') {
      return html(P.archive(L, await D.weeks(L.slug)));
    }
    if (rest === '/rulebook.json') {
      const rb = await D.paper(L.slug, 'rulebook.json');
      return rb ? new Response(rb.body, { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-cache' } }) : json({ entries: {} });
    }
    const file = rest === '/' ? 'index.html' : rest.slice(1);
    if (/^(index\.html|week\d{1,2}\.html|bets\/lines\d{1,2}\.json)$/.test(file)) {
      const obj = await D.paper(L.slug, file);
      if (!obj) return file === 'index.html' ? html(P.status(L, null, isComm(L, s))) : html(P.message('Not printed', 'That edition doesn’t exist.', `/l/${L.slug}/`), 404);
      if (!file.endsWith('.html')) return new Response(obj.body, { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-cache' } });
      // Signed in: a bar above the masthead to switch between every league you're in (and Settings for commissioners).
      // The bar rides at the end of the paper and moves itself into place.
      const mineRows = (await D.myLeagues(s.uid)).sort((a, b) => a.name.localeCompare(b.name));
      if (!mineRows.some((r) => r.slug === L.slug)) mineRows.push(L);
      const bar = P.leagueBar(L.slug, mineRows, isComm(L, s), file !== 'index.html');
      // fz-carry: a member's Rule Changes/Betting team pass handed over from the old public address (landing page),
      // kept only in this browser; the server never sees it (it travels in the link's #fragment).
      const tail = `<template id="fz-lgbar-t">${bar}</template><script>(function(){var t=document.getElementById('fz-lgbar-t'),h=document.querySelector('header.mast');if(t&&h)h.parentNode.insertBefore(t.content.cloneNode(true),h);
try{var v=(location.hash.match(/^#fzt=([^&]+)/)||[])[1]||sessionStorage.getItem('fz-carry');if(v){v=decodeURIComponent(v);var j=JSON.parse(atob(v));if(j&&j.key&&j.team&&!localStorage.getItem('fz-team')){localStorage.setItem('fz-team',JSON.stringify(j));location.reload()}sessionStorage.removeItem('fz-carry');if(location.hash.indexOf('#fzt=')===0)history.replaceState(null,'',location.pathname)}}catch(e){}})()</script>`;
      // Optimal Lineup: keep only the signed-in member's own team (every other team's lineup is removed here)
      let page = await new Response(obj.body).text();
      if (page.indexOf('data-lu-team="') >= 0) page = onlyMyLineup(page, await viewerTeam(env, D, L, s.uid).catch(() => null));
      return html(page + tail, 200, { 'Cache-Control': 'private, max-age=60' });
    }
    return html(P.message('Not found', 'Nothing here.', `/l/${L.slug}/`), 404);
  }

  // ---- league office (the paper's Rule Changes / Betting tabs) ----
  m = path.match(/^\/api\/office\/([a-z0-9]{6,16})$/);
  if (m) {
    const L = await D.league(m[1]);
    if (!L) return json({ ok: false, error: 'No such league.' }, 404);
    if (!L.feat_rules && !L.feat_bets) return json({ ok: false, error: 'The commissioner hasn’t turned this on.' });
    try {
      return json(method === 'POST' ? await officePost(env, L, req, D) : await officeGet(env, L, D));
    } catch (e) {
      return json({ ok: false, error: 'Server error: ' + e.message });
    }
  }

  // ---- build API (the GitHub Actions printer) ----
  if (path.startsWith('/api/build/')) {
    const auth = (req.headers.get('Authorization') || '').replace(/^Bearer\s+/, '');
    if (!same(auth, env.BUILD_TOKEN || '')) return json({ error: 'unauthorized' }, 401);
    m = path.match(/^\/api\/build\/login\/([a-z0-9]{16})$/);
    if (m) {   // the GitHub sign-in job: read the code once typed (it's cleared as it's read), report progress and the result
      const j = await D.temp('jobs', m[1]);
      if (!j) return json({ error: 'gone' }, 410);
      if (method === 'GET') {
        if (j.code_enc) await D.setTemp('jobs', m[1], { code_enc: null }, 15);
        return json({ status: j.status, code_enc: j.code_enc || null });
      }
      const b = await req.json();
      const st = ['running', 'code', 'code_wrong', 'ok', 'error'].includes(b.status) ? b.status : 'error';
      if (b.trace) await D.trace(st !== 'error', b.trace);
      if (st === 'ok') {
        const acct = await linkEspnAccount(env, D, String(b.s2 || ''), String(b.swid || ''), b.leagues);
        if (acct.error) {
          await D.setTemp('jobs', m[1], { status: 'error', msg: acct.error }, 15);
          return json({ ok: false, error: acct.error });
        }
        await D.setTemp('jobs', m[1], { status: 'ok', uid: acct.uid, added: acct.leagues.filter((l) => l.isNew).length, found: acct.leagues.length }, 15);
        return json({ ok: true });
      }
      await D.setTemp('jobs', m[1], { status: st, msg: String(b.msg || '').slice(0, 300) }, 15);
      return json({ ok: true });
    }
    if (path === '/api/build/login-traces') return json({ traces: await D.traces() });
    if (path === '/api/build/refresh' && method === 'POST') { await refreshEspnAccounts(env, D); return json({ ok: true }); }
    if (path === '/api/build/leagues') {
      const only = url.searchParams.get('slug');
      const results = only ? [await D.league(only)].filter(Boolean) : (await D.allLeagues()).sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)));
      const out = [];
      for (const L of results) {
        const c = { slug: L.slug, platform: L.platform, league_id: L.league_id, season: L.season, accent: L.accent, own_paper: !!L.own_paper,
          features: { rules: !!L.feat_rules, bets: !!L.feat_bets }, office_api: `${env.SITE_URL}/api/office/${L.slug}` };
        try {
          if (L.platform === 'espn' && L.espn_s2) { c.espn_s2 = await open(env, L.espn_s2); c.swid = await open(env, L.swid); }
          if (L.platform === 'yahoo') c.yahoo_token = await yahooAccess(env, L.token_uid, D);
        } catch (e) {
          c.error = e.message;
        }
        out.push(c);
      }
      return json({ leagues: out });
    }
    m = path.match(/^\/api\/build\/([a-z0-9]{6,16})\/status$/);
    if (m && method === 'POST') {   // the printer reports each league (it writes the papers into the data repo itself)
      const L = await D.league(m[1]);
      if (!L) return json({ error: 'no such league' }, 404);
      const b = await req.json();
      const st = ['ok', 'waiting', 'error', 'building'].includes(b.status) ? b.status : 'error';
      await D.patchLeague(L.slug, { status: st, status_msg: String(b.message || '').slice(0, 400), ...(st === 'ok' ? { last_week: b.week || null, last_built_at: new Date().toISOString() } : {}) });
      return json({ ok: true });
    }
    return json({ error: 'not found' }, 404);
  }
  return html(P.message('Not found', 'Nothing here.'), 404);
}

export default {
  async fetch(req, env, ctx) {
    try {
      const res = await route(req, env, ctx);
      const s = await session(req, env).catch(() => null);
      if (!s || !s.exp || s.exp - Date.now() > 50 * 864e5 || (res.headers.get('Set-Cookie') || '').includes('fz_s=')) return res;
      const out = new Response(res.body, res);   // copy (redirect responses have fixed headers)
      out.headers.append('Set-Cookie', await startSession(env, s.uid, s.display));
      return out;
    } catch (e) {
      console.log(e.stack || e);
      return html(P.message('Something broke', 'Try again in a minute.'), 500);
    }
  },
  // No host schedule: the data repo's print.yml runs itself on Tuesdays and Wednesdays (it calls /api/build/refresh
  // first), so moving hosts needs no cron.
};
