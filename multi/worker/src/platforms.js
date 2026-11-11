// Talking to Yahoo (official OAuth + Fantasy Sports API, read-only) and ESPN (league ID + optional cookies).
import { open, seal } from './crypto.js';

// ---------------- Yahoo ----------------
const YAUTH = 'https://api.login.yahoo.com/oauth2';
const YAPI = 'https://fantasysports.yahooapis.com/fantasy/v2';

export function yahooAuthUrl(env, state) {
  const q = new URLSearchParams({ client_id: env.YAHOO_CLIENT_ID, redirect_uri: `${env.SITE_URL}/auth/yahoo/callback`,
    response_type: 'code', language: 'en-us', scope: 'fspt-r', state });   // fspt-r: Fantasy Sports, read-only
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

/** A fresh access token for a stored user (refresh tokens are kept encrypted in the data repo). */
export async function yahooAccess(env, uid, D) {
  const u = await D.user(uid);
  if (!u || !u.yahoo_refresh) throw new Error('No Yahoo sign-in stored for this league. Sign in with Yahoo again.');
  const j = await yahooToken(env, { grant_type: 'refresh_token', refresh_token: await open(env, u.yahoo_refresh) });
  if (j.refresh_token) await D.saveUser(uid, { yahoo_refresh: await seal(env, j.refresh_token) });
  return j.access_token;
}

async function yget(token, path) {
  const r = await fetch(`${YAPI}/${path}`, { headers: { Authorization: `Bearer ${token}`, Accept: 'application/xml',
    'User-Agent': 'Mozilla/5.0 (compatible; DailyFantasizer/1.0; +https://thedailyfantasizer.com)' } });
  if (!r.ok) {
    // Yahoo says why in the body (<description> in XML, or JSON); keep a short, safe piece of it for the message
    const body = await r.text().catch(() => '');
    const why = (body.match(/<description>([^<]{1,160})<\/description>/) || body.match(/"description"\s*:\s*"([^"]{1,160})"/) || [])[1] || '';
    console.log('yahoo api', r.status, path.split('/')[0], body.slice(0, 300).replace(/\s+/g, ' '));
    throw new Error(`Yahoo returned ${r.status} for ${path.split('/')[0]}${why ? `: ${why}` : ''}`);
  }
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

/** The signed-in Yahoo user's team id in one league (team_key "<league_key>.t.<id>"), null if none. */
export async function yahooTeamOf(token, leagueKey) {
  const tx = await yget(token, 'users;use_login=1/games;game_keys=nfl/teams');
  const k = blocks(tx, 'team').map((t) => val(t, 'team_key')).find((k) => k.split('.t.')[0] === String(leagueKey));
  return k ? +k.split('.t.')[1] : null;
}

// ---------------- ESPN ----------------
// ESPN has no sign-in for outside sites. Public leagues need only the league ID; private leagues need the two
// cookies from a signed-in ESPN session (espn_s2 and SWID). With cookies we can tell who the commissioner is:
// SWID identifies the person, and ESPN marks league managers in the member list.
export const espnSeason = (d = new Date()) => d.getUTCFullYear() - (d.getUTCMonth() < 2 ? 1 : 0);  // Jan–Feb still belong to last season
const normSwid = (s) => String(s || '').toUpperCase().replace(/[{}]/g, '');
export const validSwid = (s) => /^\{?[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\}?$/i.test(String(s || '').trim());

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
  const me = swid ? (j.members || []).find((m) => normSwid(m.id) === normSwid(swid)) : null;
  const myTeam = me ? (j.teams || []).find((t) => (t.owners || []).some((o) => normSwid(o) === normSwid(swid)) || normSwid(t.primaryOwner) === normSwid(swid)) : null;
  const teamName = myTeam ? (myTeam.name || [myTeam.location, myTeam.nickname].filter(Boolean).join(' ')) : '';
  return { name: j.settings?.name || `League ${leagueId}`, teams: (j.teams || []).length, member: !!me,
    commissioner: !!(me && me.isLeagueManager), isPublic: !!j.settings?.isPublic, team: teamName };
}

/** Which team in this league belongs to the ESPN account `viewerSwid` (its SWID is in the team's owners).
 *  Returns the team id, null when the account owns no team, undefined when ESPN couldn't be asked. */
export async function espnTeamOf(leagueId, season, s2, swid, viewerSwid) {
  const url = `https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/${season}/segments/0/leagues/${leagueId}?view=mTeam`;
  const headers = { 'User-Agent': 'Mozilla/5.0 (DailyFantasizer)', Accept: 'application/json' };
  if (s2 && swid) headers.Cookie = `espn_s2=${s2}; SWID=${swid}`;
  try {
    const r = await fetch(url, { headers });
    if (!r.ok || !(r.headers.get('content-type') || '').includes('json')) return undefined;
    const j = await r.json(), v = normSwid(viewerSwid);
    const t = (j.teams || []).find((t) => (t.owners || []).some((o) => normSwid(o) === v) || normSwid(t.primaryOwner) === v);
    return t ? +t.id : null;
  } catch (e) { return undefined; }
}

/** Every football league on one ESPN account this season (an account can be in several). ESPN's fan profile lists the
 *  account's fantasy entries; each candidate is then checked against the league itself, so a guess never becomes a league. */
export async function espnUserLeagues(s2, swid, season) {
  const id = encodeURIComponent('{' + normSwid(swid) + '}');
  const r = await fetch(`https://fan.api.espn.com/apis/v2/fans/${id}?displayHiddenPrefs=true&context=fantasy&useCookieAuth=true&source=fantasyapp-ios&featureFlags=challengeEntries`,
    { headers: { 'User-Agent': 'Mozilla/5.0 (DailyFantasizer)', Accept: 'application/json', Cookie: `espn_s2=${s2}; SWID=${swid}` } });
  if (r.status === 401 || r.status === 403) return { error: 'ESPN didn’t accept this sign-in. Sign out of ESPN, sign in again and retry.', auth: true };
  const j = r.ok ? await r.json().catch(() => null) : null;
  if (!j) return { leagues: [], listError: 'ESPN didn’t send the list of your leagues.' };
  const ids = new Set();
  for (const p of j.preferences || []) {
    const e = p?.metaData?.entry;
    if (!e) continue;
    const football = e.abbrev === 'FFL' || e.gameId === 1 || /football/i.test(String(e.name || e.entryURL || ''));
    if (!football || (e.seasonId && +e.seasonId !== +season)) continue;
    for (const g of e.groups || []) if (g && g.groupId) ids.add(String(g.groupId));
  }
  const leagues = [];
  for (const lid of [...ids].slice(0, 20)) {
    const info = await espnLeague(lid, season, s2, swid);
    if (!info.error && info.member) leagues.push({ id: lid, name: info.name, teams: info.teams, team: info.team, commissioner: info.commissioner, season });
  }
  return { leagues, listError: ids.size ? '' : 'ESPN didn’t list any football leagues for this account this season.' };
}
