// Talking to Yahoo (official OAuth + Fantasy Sports API, read-only) and ESPN (league ID + optional cookies).
import { open, seal } from './crypto.js';

// ---------------- Yahoo ----------------
const YAUTH = 'https://api.login.yahoo.com/oauth2';
const YAPI = 'https://fantasysports.yahooapis.com/fantasy/v2';

export function yahooAuthUrl(env, state) {
  const q = new URLSearchParams({ client_id: env.YAHOO_CLIENT_ID, redirect_uri: `${env.SITE_URL}/auth/yahoo/callback`,
    response_type: 'code', language: 'en-us', state });
  return `${YAUTH}/request_auth?${q}`;
}

async function yahooToken(env, params) {
  const r = await fetch(`${YAUTH}/get_token`, {
    method: 'POST',
    headers: { Authorization: 'Basic ' + btoa(`${env.YAHOO_CLIENT_ID}:${env.YAHOO_CLIENT_SECRET}`), 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ redirect_uri: `${env.SITE_URL}/auth/yahoo/callback`, ...params }),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || !j.access_token) throw new Error(`Yahoo sign-in failed (${r.status}${j.error ? ': ' + j.error : ''})`);
  return j;  // access_token, refresh_token, expires_in, xoauth_yahoo_guid
}

export const yahooExchange = (env, code) => yahooToken(env, { grant_type: 'authorization_code', code });

/** A fresh access token for a stored user (refresh tokens are kept encrypted in D1). */
export async function yahooAccess(env, uid) {
  const u = await env.DB.prepare('SELECT yahoo_refresh FROM users WHERE id=?').bind(uid).first();
  if (!u || !u.yahoo_refresh) throw new Error('No Yahoo sign-in stored for this league. Sign in with Yahoo again.');
  const j = await yahooToken(env, { grant_type: 'refresh_token', refresh_token: await open(env, u.yahoo_refresh) });
  if (j.refresh_token) await env.DB.prepare('UPDATE users SET yahoo_refresh=? WHERE id=?').bind(await seal(env, j.refresh_token), uid).run();
  return j.access_token;
}

async function yget(token, path) {
  const r = await fetch(`${YAPI}/${path}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!r.ok) throw new Error(`Yahoo returned ${r.status} for ${path.split('/')[0]}`);
  return r.text();
}

// Yahoo's XML is regular enough to read with a few patterns (Workers have no XML parser).
const blocks = (xml, tag) => [...xml.matchAll(new RegExp(`<${tag}>([\\s\\S]*?)</${tag}>`, 'g'))].map((m) => m[1]);
const val = (xml, tag) => { const m = xml.match(new RegExp(`<${tag}>([^<]*)</${tag}>`)); return m ? m[1].replace(/&amp;/g, '&').replace(/&#39;|&apos;/g, "'").replace(/&quot;/g, '"') : ''; };

export async function yahooUser(token) {
  const xml = await yget(token, 'users;use_login=1');
  return { guid: val(xml, 'guid') };
}

/** The signed-in user's NFL leagues this season, with whether they are the commissioner of each. */
export async function yahooLeagues(token) {
  const lx = await yget(token, 'users;use_login=1/games;game_keys=nfl/leagues');
  const tx = await yget(token, 'users;use_login=1/games;game_keys=nfl/teams');
  const comm = {};
  for (const t of blocks(tx, 'team')) {
    const lk = val(t, 'team_key').split('.t.')[0];
    const me = blocks(t, 'manager').find((m) => val(m, 'is_current_login') === '1') || '';
    comm[lk] = { commissioner: val(me, 'is_commissioner') === '1', team: val(t, 'name') };
  }
  return blocks(lx, 'league').map((l) => ({ key: val(l, 'league_key'), name: val(l, 'name'), teams: +val(l, 'num_teams') || 0,
    season: +val(l, 'season') || 0, ...(comm[val(l, 'league_key')] || { commissioner: false, team: '' }) }));
}

// ---------------- ESPN ----------------
// ESPN has no sign-in for outside sites. Public leagues need only the league ID; private leagues need the two
// cookies from a signed-in ESPN session (espn_s2 and SWID). With cookies we can tell who the commissioner is:
// SWID identifies the person, and ESPN marks league managers in the member list.
export async function espnLeague(leagueId, season, s2, swid) {
  const url = `https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/${season}/segments/0/leagues/${leagueId}?view=mSettings&view=mTeam`;
  const headers = { 'User-Agent': 'Mozilla/5.0 (DailyFantasizer)', Accept: 'application/json' };
  if (s2 && swid) headers.Cookie = `espn_s2=${s2}; SWID=${swid}`;
  const r = await fetch(url, { headers });
  const type = r.headers.get('content-type') || '';
  if (r.status === 401 || r.status === 403) return { error: s2 ? 'ESPN didn’t accept those cookies. Copy them again from a signed-in ESPN tab.' : 'This league is private. Add your espn_s2 and SWID cookies below.', private: true };
  if (r.status === 404) return { error: `No ESPN league ${leagueId} in the ${season} season.` };
  if (!r.ok || !type.includes('json')) return { error: `ESPN didn’t answer (status ${r.status}). Try again in a minute.` };
  const j = await r.json();
  const norm = (s) => String(s || '').toUpperCase().replace(/[{}]/g, '');
  const me = swid ? (j.members || []).find((m) => norm(m.id) === norm(swid)) : null;
  return { name: j.settings?.name || `League ${leagueId}`, teams: (j.teams || []).length, member: !!me,
    commissioner: !!(me && me.isLeagueManager), isPublic: !!j.settings?.isPublic };
}
