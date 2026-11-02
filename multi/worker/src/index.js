// The Daily Fantasizer for any league: sign-up site, paper host, commissioner settings, league office and build API.
// Cloudflare Worker + D1 (accounts, leagues, votes, bets) + R2 (the printed papers). The papers themselves are
// printed by the GitHub Actions workflow "fantasizer-leagues.yml", which this Worker starts and which uploads back here.
import { sign, verify, seal, open, sha256, randomId, randomCode, cookie, setCookie, same } from './crypto.js';
import { yahooAuthUrl, yahooExchange, yahooAccess, yahooUser, yahooLeagues, espnLeague } from './platforms.js';
import { officeGet, officePost } from './office.js';
import * as P from './pages.js';

const html = (body, status = 200, headers = {}) => new Response(body, { status, headers: { 'Content-Type': 'text/html; charset=utf-8', 'X-Robots-Tag': 'noindex', 'Referrer-Policy': 'same-origin', ...headers } });
const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });
const redirect = (to, headers = {}) => new Response(null, { status: 303, headers: { Location: to, ...headers } });
const SESSION_DAYS = 60;
const FILE_OK = /^(index\.html|week\d{1,2}\.html|meta\.json|bets\/lines\d{1,2}\.json|cache\/data\.tgz)$/;

async function session(req, env) { return verify(env, cookie(req, 'fz_s')); }
async function startSession(env, uid, display) {
  return setCookie('fz_s', await sign(env, { uid, display, exp: Date.now() + SESSION_DAYS * 864e5 }), SESSION_DAYS * 86400);
}
async function form(req) { return Object.fromEntries((await req.formData()).entries()); }
async function league(env, slug) { return env.DB.prepare('SELECT * FROM leagues WHERE slug=?').bind(slug).first(); }
const isComm = (L, s) => !!(s && L && L.commissioner_uid && s.uid === L.commissioner_uid);

async function remember(env, uid, slug, comm) {
  await env.DB.prepare('INSERT INTO members (uid, slug, is_comm) VALUES (?,?,?) ON CONFLICT(uid, slug) DO UPDATE SET is_comm=MAX(is_comm, excluded.is_comm)')
    .bind(uid, slug, comm ? 1 : 0).run();
}

/** Ask GitHub Actions to print one league (or every league when slug is empty). */
async function dispatch(env, slug = '') {
  if (!env.GITHUB_TOKEN || !env.GITHUB_REPO) return false;
  if (slug) {
    const L = await league(env, slug);
    if (L && L.last_dispatch_at && Date.now() - Date.parse(L.last_dispatch_at) < 120000) return true;  // a run was just started
    await env.DB.prepare("UPDATE leagues SET last_dispatch_at=?, status=CASE WHEN status='ok' THEN status ELSE 'queued' END WHERE slug=?").bind(new Date().toISOString(), slug).run();
  }
  const r = await fetch(`https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/fantasizer-leagues.yml/dispatches`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${env.GITHUB_TOKEN}`, Accept: 'application/vnd.github+json', 'User-Agent': 'daily-fantasizer-site', 'X-GitHub-Api-Version': '2022-11-28' },
    body: JSON.stringify({ ref: env.GITHUB_REF || 'main', inputs: { slug } }),
  });
  if (!r.ok) console.log('dispatch failed', r.status, await r.text());
  return r.ok;
}

async function createOrUpdateLeague(env, { platform, leagueId, season, name, teams, uid, commissioner, s2, swid, tokenUid }) {
  let L = await env.DB.prepare('SELECT * FROM leagues WHERE platform=? AND league_id=? AND season=?').bind(platform, String(leagueId), season).first();
  if (!L) {
    const slug = randomId(10);
    await env.DB.prepare(`INSERT INTO leagues (slug, platform, league_id, season, name, teams, commissioner_uid, token_uid, espn_s2, swid, feat_rules, feat_bets, accent, status, created_by, created_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,0,0,'#33658a','queued',?,?)`)
      .bind(slug, platform, String(leagueId), season, name, teams, commissioner ? uid : null, tokenUid || null, await seal(env, s2), await seal(env, swid), uid, new Date().toISOString()).run();
    L = await league(env, slug);
    await dispatch(env, slug);
  } else {
    // fresher credentials win; a verified commissioner takes over the settings
    const sets = [], vals = [];
    if (s2 && swid) { sets.push('espn_s2=?', 'swid=?'); vals.push(await seal(env, s2), await seal(env, swid)); }
    if (tokenUid) { sets.push('token_uid=?'); vals.push(tokenUid); }
    if (commissioner) { sets.push('commissioner_uid=?'); vals.push(uid); }
    sets.push('name=?', 'teams=?'); vals.push(name, teams);
    await env.DB.prepare(`UPDATE leagues SET ${sets.join(', ')} WHERE slug=?`).bind(...vals, L.slug).run();
    L = await league(env, L.slug);
    if (L.status === 'error' && (s2 || tokenUid)) await dispatch(env, L.slug);  // new credentials: try again
  }
  await remember(env, uid, L.slug, commissioner);
  return L;
}

// ---------------- pages ----------------
async function route(req, env, ctx) {
  const url = new URL(req.url), path = url.pathname, method = req.method;
  const s = await session(req, env);

  if (method === 'POST' && !path.startsWith('/api/')) {  // forms: same-site only
    const o = req.headers.get('Origin');
    if (o && o !== new URL(env.SITE_URL).origin) return html(P.message('Not allowed', 'That form came from another site.'), 403);
  }

  if (path === '/' && method === 'GET') return html(P.home(env, !!s));
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
      await env.DB.prepare('INSERT INTO users (id, platform, yahoo_refresh, created_at) VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET yahoo_refresh=excluded.yahoo_refresh')
        .bind(uid, 'yahoo', await seal(env, tok.refresh_token), new Date().toISOString()).run();
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
      const leagues = await yahooLeagues(await yahooAccess(env, s.uid));
      const existing = {};
      for (const l of leagues) {
        const row = await env.DB.prepare("SELECT slug FROM leagues WHERE platform='yahoo' AND league_id=? AND season=?").bind(l.key, l.season).first();
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
    const leagues = await yahooLeagues(await yahooAccess(env, s.uid));
    const l = leagues.find((x) => x.key === f.key);
    if (!l) return html(P.message('Not your league', 'That league isn’t on your Yahoo account.', '/yahoo'), 403);
    const L = await createOrUpdateLeague(env, { platform: 'yahoo', leagueId: l.key, season: l.season, name: l.name, teams: l.teams,
      uid: s.uid, commissioner: l.commissioner, tokenUid: s.uid });
    return redirect(`/l/${L.slug}/`);
  }

  // ---- ESPN ----
  if (path === '/espn' && method === 'GET') return html(P.espnForm());
  if (path === '/espn' && method === 'POST') {
    const f = await form(req);
    const m = String(f.league || '').match(/leagueId=(\d+)/) || String(f.league || '').match(/^\s*(\d{3,12})\s*$/);
    const season = parseInt(f.season, 10) || new Date().getUTCFullYear();
    if (!m) return html(P.espnForm({ error: 'That doesn’t look like an ESPN league ID.', leagueId: f.league, season }), 400);
    const s2 = String(f.espn_s2 || '').trim(), swid = String(f.swid || '').trim();
    if ((s2 && !swid) || (!s2 && swid)) return html(P.espnForm({ error: 'Add both cookies, espn_s2 and SWID, or neither.', leagueId: f.league, season }), 400);
    const info = await espnLeague(m[1], season, s2, swid);
    if (info.error) return html(P.espnForm({ error: info.error, leagueId: f.league, season }), 400);
    if (s2 && !info.member) return html(P.espnForm({ error: 'Those cookies belong to an ESPN account that isn’t in this league.', leagueId: f.league, season }), 403);
    const uid = s2 ? `espn:${swid.toUpperCase().replace(/[{}]/g, '')}` : (s && s.uid) || `anon:${randomId(16)}`;
    const L = await createOrUpdateLeague(env, { platform: 'espn', leagueId: m[1], season, name: info.name, teams: info.teams, uid,
      commissioner: info.commissioner, s2: s2 || null, swid: swid || null });
    return redirect(`/l/${L.slug}/`, { 'Set-Cookie': await startSession(env, uid, 'ESPN') });
  }

  if (path === '/mine') {
    if (!s) return redirect('/');
    const { results } = await env.DB.prepare('SELECT l.*, m.is_comm FROM members m JOIN leagues l ON l.slug=m.slug WHERE m.uid=? ORDER BY l.created_at DESC').bind(s.uid).all();
    return html(P.mine(results.map((L) => ({ ...L, is_comm: L.commissioner_uid === s.uid }))));
  }

  // ---- a league's paper ----
  let m = path.match(/^\/l\/([a-z0-9]{6,16})(\/.*)?$/);
  if (m) {
    const L = await league(env, m[1]);
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
        await env.DB.prepare('UPDATE leagues SET feat_rules=?, feat_bets=?, accent=?' + (code ? ', comm_code_hash=?' : '') + ' WHERE slug=?')
          .bind(rules, bets, accent, ...(code ? [await sha256(code)] : []), L.slug).run();
        await dispatch(env, L.slug);
        return html(P.settings(env, await league(env, L.slug), { saved: true, code }));
      }
      if (rest === '/code' && method === 'POST') {
        const code = randomCode();
        await env.DB.prepare('UPDATE leagues SET comm_code_hash=? WHERE slug=?').bind(await sha256(code), L.slug).run();
        return html(P.settings(env, await league(env, L.slug), { code }));
      }
      if (rest === '/rebuild' && method === 'POST') {
        await dispatch(env, L.slug);
        return html(P.settings(env, await league(env, L.slug), { saved: true }));
      }
      if (rest === '/delete' && method === 'POST') {
        const keys = await env.PAPERS.list({ prefix: `papers/${L.slug}/` });
        for (const o of keys.objects) await env.PAPERS.delete(o.key);
        await env.DB.batch(['claims', 'proposals', 'votes', 'bets', 'office_log', 'members'].map((t) => env.DB.prepare(`DELETE FROM ${t} WHERE slug=?`).bind(L.slug))
          .concat(env.DB.prepare('DELETE FROM leagues WHERE slug=?').bind(L.slug)));
        return html(P.message('League removed', 'Every paper and record for that league is gone from this site.'));
      }
    }
    if (rest === '/archive') {
      const keys = await env.PAPERS.list({ prefix: `papers/${L.slug}/week` });
      const weeks = keys.objects.map((o) => +o.key.match(/week(\d+)\.html$/)?.[1]).filter(Boolean).sort((a, b) => b - a);
      return html(P.archive(L, weeks));
    }
    if (rest === '/rulebook.json') return json({ entries: {} });
    const file = rest === '/' ? 'index.html' : rest.slice(1);
    if (/^(index\.html|week\d{1,2}\.html|bets\/lines\d{1,2}\.json)$/.test(file)) {
      const obj = await env.PAPERS.get(`papers/${L.slug}/${file}`);
      if (!obj) return file === 'index.html' ? html(P.status(L, null, isComm(L, s))) : html(P.message('Not printed', 'That edition doesn’t exist.', `/l/${L.slug}/`), 404);
      if (s) ctx.waitUntil(remember(env, s.uid, L.slug, isComm(L, s)));
      const bar = isComm(L, s) && file.endsWith('.html')
        ? `<a href="/l/${L.slug}/settings" style="position:fixed;left:12px;bottom:12px;z-index:60;font:600 13px/1 ui-monospace,monospace;letter-spacing:.06em;text-transform:uppercase;background:#151a24;color:#fff;padding:10px 12px;text-decoration:none">Settings</a>` : '';
      if (!file.endsWith('.html')) return new Response(obj.body, { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-cache' } });
      const body = bar ? (await obj.text()) + bar : obj.body;
      return html(body, 200, { 'Cache-Control': 'private, max-age=60' });
    }
    return html(P.message('Not found', 'Nothing here.', `/l/${L.slug}/`), 404);
  }

  // ---- league office (the paper's Rule Changes / Betting tabs) ----
  m = path.match(/^\/api\/office\/([a-z0-9]{6,16})$/);
  if (m) {
    const L = await league(env, m[1]);
    if (!L) return json({ ok: false, error: 'No such league.' }, 404);
    if (!L.feat_rules && !L.feat_bets) return json({ ok: false, error: 'The commissioner hasn’t turned this on.' });
    try {
      return json(method === 'POST' ? await officePost(env, L, req) : await officeGet(env, L));
    } catch (e) {
      return json({ ok: false, error: 'Server error: ' + e.message });
    }
  }

  // ---- build API (the GitHub Actions printer) ----
  if (path.startsWith('/api/build/')) {
    const auth = (req.headers.get('Authorization') || '').replace(/^Bearer\s+/, '');
    if (!same(auth, env.BUILD_TOKEN || '')) return json({ error: 'unauthorized' }, 401);
    if (path === '/api/build/leagues') {
      const only = url.searchParams.get('slug');
      const { results } = only ? await env.DB.prepare('SELECT * FROM leagues WHERE slug=?').bind(only).all()
        : await env.DB.prepare('SELECT * FROM leagues ORDER BY created_at').all();
      const out = [];
      for (const L of results) {
        const c = { slug: L.slug, platform: L.platform, league_id: L.league_id, season: L.season, accent: L.accent,
          features: { rules: !!L.feat_rules, bets: !!L.feat_bets }, office_api: `${env.SITE_URL}/api/office/${L.slug}` };
        try {
          if (L.platform === 'espn' && L.espn_s2) { c.espn_s2 = await open(env, L.espn_s2); c.swid = await open(env, L.swid); }
          if (L.platform === 'yahoo') c.yahoo_token = await yahooAccess(env, L.token_uid);
        } catch (e) {
          c.error = e.message;
        }
        out.push(c);
      }
      return json({ leagues: out });
    }
    m = path.match(/^\/api\/build\/([a-z0-9]{6,16})\/(file|status)$/);
    if (m) {
      const L = await league(env, m[1]);
      if (!L) return json({ error: 'no such league' }, 404);
      if (m[2] === 'status' && method === 'POST') {
        const b = await req.json();
        const st = ['ok', 'waiting', 'error', 'building'].includes(b.status) ? b.status : 'error';
        await env.DB.prepare('UPDATE leagues SET status=?, status_msg=?' + (st === 'ok' ? ', last_week=?, last_built_at=?' : '') + ' WHERE slug=?')
          .bind(st, String(b.message || '').slice(0, 400), ...(st === 'ok' ? [b.week || null, new Date().toISOString()] : []), L.slug).run();
        return json({ ok: true });
      }
      const fp = url.searchParams.get('path') || '';
      if (!FILE_OK.test(fp)) return json({ error: 'bad path' }, 400);
      const key = `papers/${L.slug}/${fp}`;
      if (method === 'PUT') { await env.PAPERS.put(key, req.body); return json({ ok: true }); }
      if (method === 'GET') { const o = await env.PAPERS.get(key); return o ? new Response(o.body) : json({ error: 'missing' }, 404); }
    }
    return json({ error: 'not found' }, 404);
  }
  return html(P.message('Not found', 'Nothing here.'), 404);
}

export default {
  async fetch(req, env, ctx) {
    try {
      return await route(req, env, ctx);
    } catch (e) {
      console.log(e.stack || e);
      return html(P.message('Something broke', 'Try again in a minute.'), 500);
    }
  },
  // Tuesday (and a Wednesday retry, for weeks ESPN or Yahoo finalize late): print every league.
  async scheduled(event, env, ctx) {
    ctx.waitUntil(dispatch(env, ''));
  },
};
