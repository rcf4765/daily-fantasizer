// What the site keeps, as files in the private data repo (see store.js). Layout:
//   leagues/<slug>.json          one league: settings, status, encrypted ESPN session or whose Yahoo sign-in prints it
//   index/leagues.json           "<platform>:<league id>:<season>" → slug (find a league; list them all)
//   users/<id>.json              one account: encrypted ESPN session or Yahoo refresh token
//   members/<id>.json            which leagues an account is in, and where it is commissioner
//   office/<slug>.json           Rule Changes and Betting for a league (claims, proposals, votes, bets, log)
//   papers/<slug>/...            printed editions, written by the printer job in the data repo
//   jobs/<id>.json               an ESPN sign-in in progress (status only; the password never gets here)
//   links/<hash>.json            short-lived hand-offs (extension sign-in, paid-plan code step)
//   limits/<hash>.json           sign-in attempts per (hashed) address, for the 6-per-15-minutes limit
//   traces.json                  the last 30 sign-in traces (step names only)
// Encrypted fields use ENC_KEY (crypto.js seal/open). Nothing here is ever sent to a page.
import { makeStore } from './store.js';
import { sha256 } from './crypto.js';

const safe = (id) => String(id).replace(/[^A-Za-z0-9_.-]/g, '_');
const now = () => new Date().toISOString();

export function makeData(env) {
  const st = makeStore(env);
  const leagueKey = (platform, id, season) => `${platform}:${id}:${season}`;
  const D = {
    st,
    // ---- leagues ----
    async league(slug) { return slug && /^[a-z0-9]{6,16}$/.test(slug) ? (await st.get(`leagues/${slug}.json`))?.data || null : null; },
    async index() { return (await st.get('index/leagues.json'))?.data || {}; },
    async findLeague(platform, id, season) { const slug = (await D.index())[leagueKey(platform, id, season)]; return slug ? D.league(slug) : null; },
    async createLeague(L) {
      await st.put(`leagues/${L.slug}.json`, L, null, `site: new league ${L.slug}`);
      await st.update('index/leagues.json', (cur) => ({ ...(cur || {}), [leagueKey(L.platform, L.league_id, L.season)]: L.slug }));
      return L;
    },
    /** patch: an object, or fn(L) → object of changed fields. Returns the updated league (null if gone). */
    async patchLeague(slug, patch) {
      return st.update(`leagues/${slug}.json`, (cur) => {
        if (!cur) return undefined;
        const p = typeof patch === 'function' ? patch(cur) : patch;
        if (!p || Object.keys(p).every((k) => cur[k] === p[k])) return undefined;
        return { ...cur, ...p };
      });
    },
    async deleteLeague(slug) {
      const files = [];
      for (const f of await st.list(`papers/${slug}`)) {
        if (f === 'bets' || f === 'cache') files.push(...(await st.list(`papers/${slug}/${f}`)).map((g) => `${f}/${g}`)); else files.push(f);
      }
      for (const f of files) {   // papers are removed by path; their sha comes from the listing's file read
        const p = `papers/${slug}/${f}`, cur = await st.sha(p);
        if (cur) await st.del(p, cur);
      }
      await st.update(`office/${slug}.json`, () => null);
      await st.update(`leagues/${slug}.json`, () => null);
      await st.update('index/leagues.json', (cur) => Object.fromEntries(Object.entries(cur || {}).filter(([, v]) => v !== slug)));
    },
    async allLeagues() { return (await Promise.all(Object.values(await D.index()).map((s) => D.league(s)))).filter(Boolean); },
    // ---- accounts ----
    async user(uid) { return (await st.get(`users/${safe(uid)}.json`))?.data || null; },
    async saveUser(uid, patch) { return st.update(`users/${safe(uid)}.json`, (cur) => ({ id: uid, created_at: now(), ...(cur || {}), ...patch })); },
    async allUsers() { return (await Promise.all((await st.list('users')).map(async (f) => (await st.get(`users/${f}`))?.data))).filter(Boolean); },
    async memberships(uid) { return (await st.get(`members/${safe(uid)}.json`))?.data?.leagues || {}; },
    /** Remember that uid reads slug (no write when nothing changes, so paper views stay cheap). */
    async remember(uid, slug, comm) {
      return st.update(`members/${safe(uid)}.json`, (cur) => {
        const l = { ...(cur?.leagues || {}) };
        if (l[slug] && (l[slug].comm || !comm)) return undefined;
        l[slug] = { comm: !!comm, since: l[slug]?.since || now() };
        return { leagues: l };
      });
    },
    /** The member's own team in a league (Optimal Lineup), kept apart from `leagues` so it never adds a membership. */
    async memberTeam(uid, slug) { return (await st.get(`members/${safe(uid)}.json`))?.data?.teams?.[slug] || null; },
    async setMemberTeam(uid, slug, team) {
      return st.update(`members/${safe(uid)}.json`, (cur) => {
        const prev = cur?.teams?.[slug];
        if (prev && prev.team === team && Date.now() - Date.parse(prev.at) < 3600e3) return undefined;
        return { ...(cur || {}), teams: { ...(cur?.teams || {}), [slug]: { team, at: now() } } };
      });
    },
    async myLeagues(uid) {
      const m = await D.memberships(uid);
      return (await Promise.all(Object.keys(m).map((s) => D.league(s)))).filter(Boolean);
    },
    // ---- the league office ----
    async office(slug) { return (await st.get(`office/${slug}.json`))?.data || { claims: {}, proposals: [], votes: [], bets: [], log: [] }; },
    async updateOffice(slug, fn) {
      return st.update(`office/${slug}.json`, (cur) => fn(cur || { claims: {}, proposals: [], votes: [], bets: [], log: [] }));
    },
    // ---- short-lived records (expire by their own clock; old ones are cleaned when touched) ----
    async temp(kind, key) {
      const v = (await st.get(`${kind}/${safe(key)}.json`))?.data;
      return v && (!v.expires || Date.parse(v.expires) > Date.now()) ? v : null;
    },
    async setTemp(kind, key, value, minutes) {
      return st.update(`${kind}/${safe(key)}.json`, (cur) => ({ ...(cur || {}), ...value, updated_at: now(), expires: new Date(Date.now() + minutes * 60000).toISOString() }));
    },
    async dropTemp(kind, key) { return st.update(`${kind}/${safe(key)}.json`, () => null); },
    /** Count a sign-in attempt from this address; returns how many in the last 15 minutes (including this one). */
    async attempt(ip) {
      const k = (await sha256(`fz-ip|${ip}`)).slice(0, 24);
      const v = await st.update(`limits/${k}.json`, (cur) => {
        const t = Date.now();
        const times = (cur?.times || []).filter((x) => t - Date.parse(x) < 15 * 60000);
        return { times: [...times, now()] };
      });
      return v.times.length;
    },
    async trace(ok, steps) {
      return st.update('traces.json', (cur) => ({ traces: [{ at: now(), ok: ok ? 1 : 0, steps: (steps || []).join('\n').slice(0, 4000) }, ...((cur && cur.traces) || [])].slice(0, 30) }));
    },
    async traces() { return (await st.get('traces.json'))?.data?.traces || []; },
    // ---- papers ----
    paper: (slug, file) => st.raw(`papers/${slug}/${file}`),
    async weeks(slug) { return (await st.list(`papers/${slug}`)).map((f) => +f.match(/^week(\d+)\.html$/)?.[1]).filter(Boolean).sort((a, b) => b - a); },
  };
  return D;
}
