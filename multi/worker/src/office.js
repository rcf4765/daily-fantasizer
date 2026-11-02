// The league office for any league: Rule Changes votes and Betting slips.
// A port of proposals/Code.gs (the Men Fantasizing Google Sheet backend) onto D1, with the same request and
// response shapes, so the paper's own page script talks to it unchanged. Differences, per league:
//  - teams = the league's size, a proposal passes with a majority of the whole league;
//  - only works when the commissioner turned Rule Changes and/or Betting on in Settings;
//  - the week's betting board comes from this site's storage (uploaded with each edition);
//  - the commissioner code is generated per league and shown only on the commissioner's Settings page;
//  - passed proposals are never applied to ESPN or Yahoo automatically: the commissioner sets them by hand.
import { sha256 } from './crypto.js';

const WINDOW_DAYS = 7;
const MAX_OPEN_PER_TEAM = 3;
const CATEGORIES = ['Scoring', 'Rules', 'Settings'];
const PRESETS = {  // same one-tap suggestions as rules_presets.json
  'rolling-waivers': { category: 'Settings', title: 'Rolling waiver priority' },
  'faab': { category: 'Settings', title: 'Blind bidding (FAAB)' },
  'weekly-add-cap': { category: 'Rules', title: 'Cap pickups at 5 per week' },
  'pass-td-6': { category: 'Scoring', title: '6-point passing touchdowns' },
  'half-ppr': { category: 'Scoring', title: 'Half-point PPR' },
  'harder-veto': { category: 'Rules', title: 'Harder to veto trades' },
};
const MAX_STAKE = 5, MAX_LEGS = 6, MAX_WIN = 150;

const now = () => new Date().toISOString();
const fail = (error) => ({ ok: false, error });
const clean = (s, n) => String(s || '').replace(/[\u0000-\u001f]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, n);

export async function officeGet(env, L) {
  await settle(env, L);
  return state(env, L);
}

export async function officePost(env, L, req) {
  let r;
  try { r = await req.json(); } catch { return fail('Bad request.'); }
  await settle(env, L);
  const res = await handle(env, L, r || {});
  if (res.ok) { await settle(env, L); res.state = await state(env, L); }
  return res;
}

async function owns(env, L, team, key) {
  if (!key) return false;
  const row = await env.DB.prepare('SELECT key_hash FROM claims WHERE slug=? AND team=?').bind(L.slug, team).first();
  return !!row && row.key_hash === await sha256(String(key));
}

async function log(env, L, action, team, detail) {
  await env.DB.prepare('INSERT INTO office_log (slug, at, action, team, detail) VALUES (?,?,?,?,?)')
    .bind(L.slug, now(), action, team === '' ? null : team, String(detail || '')).run();
}

async function proposals(env, L) {
  const { results } = await env.DB.prepare('SELECT * FROM proposals WHERE slug=? ORDER BY seq').bind(L.slug).all();
  return results.map((p) => ({ id: p.id, team: p.team, category: p.category, title: p.title, details: p.details,
    createdAt: p.created_at, deadline: p.deadline, status: p.status, closedAt: p.closed_at || '', preset: p.preset || '' }));
}

async function bets(env, L) {
  const { results } = await env.DB.prepare('SELECT * FROM bets WHERE slug=? ORDER BY seq').bind(L.slug).all();
  return results.map((b) => ({ id: b.id, week: b.week, team: b.team, stake: b.stake, legs: JSON.parse(b.legs || '[]'),
    dec: b.dec, win: b.win, placedAt: b.placed_at, status: b.status }));
}

async function lines(env, L, week) {
  const obj = await env.PAPERS.get(`papers/${L.slug}/bets/lines${week}.json`);
  if (!obj) return null;
  const B = await obj.json(), ix = {};
  for (const g of ['nfl', 'league', 'props']) {
    for (const ev of B[g] || []) {
      const who = ev.name || ev.title;
      for (const mk of ev.markets) {
        for (const s of mk.sel) {
          ix[s.id] = { odds: Number(s.odds), lock: ev.lock, mk: `${ev.id}|${mk.m}`,
            desc: (g === 'props' ? `${who} ` : '') + s.name + (g === 'props' ? ` (${mk.label.toLowerCase()})` : mk.m === 'tot' ? ` · ${who}` : '') };
        }
      }
    }
  }
  return ix;
}

async function handle(env, L, r) {
  const T = L.teams, team = parseInt(r.team, 10);
  const rulesOn = !!L.feat_rules, betsOn = !!L.feat_bets;
  switch (r.action) {
    case 'claim': {
      if (!(team >= 1 && team <= T)) return fail('Pick a team.');
      const taken = await env.DB.prepare('SELECT 1 FROM claims WHERE slug=? AND team=?').bind(L.slug, team).first();
      if (taken) return fail('That team is already claimed. Ask the commissioner if it should be yours.');
      const key = crypto.randomUUID() + crypto.randomUUID();
      await env.DB.prepare('INSERT INTO claims (slug, team, key_hash, claimed_at) VALUES (?,?,?,?)').bind(L.slug, team, await sha256(key), now()).run();
      await log(env, L, 'claim', team, '');
      return { ok: true, key };
    }
    case 'vote': {
      if (!rulesOn) return fail('Rule Changes is turned off for this league.');
      if (!await owns(env, L, team, r.key)) return fail('This phone is not signed in to that team.');
      const p = (await proposals(env, L)).find((x) => x.id === String(r.proposal));
      if (!p) return fail('No such proposal.');
      if (p.status !== 'open') return fail('Voting on this proposal has closed.');
      const choice = r.choice === 'yes' || r.choice === 'no' ? r.choice : null;
      if (!choice) return fail('Vote yes or no.');
      await env.DB.batch([
        env.DB.prepare('DELETE FROM votes WHERE slug=? AND proposal=? AND team=?').bind(L.slug, p.id, team),
        env.DB.prepare('INSERT INTO votes (slug, proposal, team, choice, at) VALUES (?,?,?,?,?)').bind(L.slug, p.id, team, choice, now()),
      ]);
      await log(env, L, 'vote', team, `${p.id} ${choice}`);
      return { ok: true };
    }
    case 'propose': {
      if (!rulesOn) return fail('Rule Changes is turned off for this league.');
      if (!await owns(env, L, team, r.key)) return fail('This phone is not signed in to that team.');
      const preset = r.preset ? String(r.preset) : '';
      if (preset && !Object.prototype.hasOwnProperty.call(PRESETS, preset)) return fail('Unknown suggestion.');
      const title = preset ? PRESETS[preset].title : clean(r.title, 90), details = clean(r.details, 600);
      const cat = preset ? PRESETS[preset].category : (CATEGORIES.includes(r.category) ? r.category : null);
      if (!cat) return fail('Pick a category.');
      if (title.length < 5) return fail('Give the proposal a title.');
      const all = await proposals(env, L);
      if (preset && all.some((p) => p.preset === preset && p.status === 'open')) return fail('That one is already up for a vote.');
      if (all.filter((p) => p.team === team && p.status === 'open').length >= MAX_OPEN_PER_TEAM) return fail(`Your team already has ${MAX_OPEN_PER_TEAM} open proposals.`);
      const id = `P${all.length + 1}`, created = new Date();
      await env.DB.prepare('INSERT INTO proposals (slug, seq, id, team, category, title, details, created_at, deadline, status, closed_at, preset) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)')
        .bind(L.slug, all.length + 1, id, team, cat, title, details, created.toISOString(), new Date(created.getTime() + WINDOW_DAYS * 864e5).toISOString(), 'open', '', preset).run();
      await log(env, L, 'propose', team, `${id} ${title}`);
      return { ok: true, id };
    }
    case 'bet': {
      if (!betsOn) return fail('Betting is turned off for this league.');
      if (!await owns(env, L, team, r.key)) return fail('This phone is not signed in to that team.');
      const week = parseInt(r.week, 10), stake = Math.round(Number(r.stake) * 100) / 100;
      if (!(week >= 1 && week <= 18)) return fail('Unknown week.');
      if (!(stake >= 1)) return fail('Stake at least 1 point.');
      const ids = (r.legs || []).map(String);
      if (!ids.length || ids.length > MAX_LEGS) return fail(`A slip has 1 to ${MAX_LEGS} legs.`);
      const board = await lines(env, L, week);
      if (!board) return fail(`The week ${week} board isn’t posted.`);
      const t = Date.now(), seen = {}, legs = [];
      let decv = 1;
      for (const id of ids) {
        const x = board[id];
        if (!x) return fail('One of those lines is no longer on the board. Refresh and try again.');
        if (t >= Date.parse(x.lock)) return fail(`${x.desc} is locked: that game has started.`);
        if (seen[x.mk]) return fail('Only one side of each market per slip.');
        seen[x.mk] = 1;
        legs.push({ id, desc: x.desc, odds: x.odds, lock: x.lock });
        decv *= x.odds > 0 ? 1 + x.odds / 100 : 1 + 100 / Math.abs(x.odds);
      }
      const all = await bets(env, L);
      const used = all.filter((b) => b.team === team && b.week === week && b.status !== 'cancelled').reduce((s, b) => s + b.stake, 0);
      if (used + stake > MAX_STAKE) return fail(`That’s over your ${MAX_STAKE} points for week ${week} (${MAX_STAKE - used} left).`);
      const win = Math.min(MAX_WIN, Math.round(stake * (decv - 1) * 100) / 100);
      const id = `B${all.length + 1}`;
      await env.DB.prepare('INSERT INTO bets (slug, seq, id, week, team, stake, legs, dec, win, placed_at, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)')
        .bind(L.slug, all.length + 1, id, week, team, stake, JSON.stringify(legs), Math.round(decv * 10000) / 10000, win, now(), 'open').run();
      await log(env, L, 'bet', team, `${id} wk${week} ${stake}`);
      return { ok: true, id };
    }
    case 'cancelbet': {
      if (!await owns(env, L, team, r.key)) return fail('This phone is not signed in to that team.');
      const b = (await bets(env, L)).find((x) => x.id === String(r.bet));
      if (!b || b.team !== team) return fail('No such bet.');
      if (b.status !== 'open') return fail('That bet can’t be cancelled.');
      if (b.legs.some((l) => Date.now() >= Date.parse(l.lock))) return fail('A leg has already started.');
      await env.DB.prepare("UPDATE bets SET status='cancelled' WHERE slug=? AND id=?").bind(L.slug, b.id).run();
      await log(env, L, 'cancelbet', team, b.id);
      return { ok: true };
    }
    case 'admin': {
      if (!r.code || !L.comm_code_hash || await sha256(String(r.code).trim().toUpperCase()) !== L.comm_code_hash) return fail('Wrong commissioner code.');
      if (r.op === 'check') return { ok: true };
      if (r.op === 'reset') {
        const res = await env.DB.prepare('DELETE FROM claims WHERE slug=? AND team=?').bind(L.slug, team).run();
        if (!res.meta.changes) return fail('That team is not claimed.');
        await log(env, L, 'reset', team, 'by commissioner');
        return { ok: true };
      }
      if (r.op === 'withdraw') {
        const res = await env.DB.prepare("UPDATE proposals SET status='withdrawn', closed_at=? WHERE slug=? AND id=?").bind(now(), L.slug, String(r.proposal)).run();
        if (!res.meta.changes) return fail('No such proposal.');
        await log(env, L, 'withdraw', '', r.proposal);
        return { ok: true };
      }
      return fail('Unknown commissioner action.');
    }
  }
  return fail('Unknown action.');
}

/** Close proposals whose result is decided or whose window has ended. */
async function settle(env, L) {
  const T = L.teams, PASS = Math.floor(T / 2) + 1, t = Date.now();
  const open = (await proposals(env, L)).filter((p) => p.status === 'open');
  if (!open.length) return;
  const { results } = await env.DB.prepare('SELECT proposal, choice, COUNT(*) AS n FROM votes WHERE slug=? GROUP BY proposal, choice').bind(L.slug).all();
  const tally = {};
  for (const v of results) (tally[v.proposal] = tally[v.proposal] || { yes: 0, no: 0 })[v.choice] = v.n;
  for (const p of open) {
    const c = tally[p.id] || { yes: 0, no: 0 };
    let status = null;
    if (c.yes >= PASS) status = 'passed';
    else if (T - c.no < PASS) status = 'failed';
    else if (t >= Date.parse(p.deadline)) status = 'failed';
    if (status) {
      await env.DB.prepare('UPDATE proposals SET status=?, closed_at=? WHERE slug=? AND id=?').bind(status, now(), L.slug, p.id).run();
      await log(env, L, status, '', p.id);
    }
  }
}

/** Everything the page shows. Keys and hashes never leave the server. */
async function state(env, L) {
  const T = L.teams;
  const { results: votes } = await env.DB.prepare('SELECT proposal, team, choice, at FROM votes WHERE slug=?').bind(L.slug).all();
  const { results: claims } = await env.DB.prepare('SELECT team, claimed_at FROM claims WHERE slug=? ORDER BY team').bind(L.slug).all();
  return {
    ok: true,
    rules: { teams: T, pass: Math.floor(T / 2) + 1, windowDays: WINDOW_DAYS, categories: CATEGORIES, maxOpen: MAX_OPEN_PER_TEAM,
      presets: L.feat_rules ? Object.keys(PRESETS) : [], betting: !!L.feat_bets, maxStake: MAX_STAKE, maxLegs: MAX_LEGS, maxWin: MAX_WIN },
    bets: await bets(env, L),
    claims: claims.map((c) => ({ team: c.team, at: c.claimed_at })),
    proposals: (await proposals(env, L)).map((p) => ({ ...p, votes: votes.filter((v) => v.proposal === p.id).map((v) => ({ team: v.team, choice: v.choice, at: v.at })) })),
    now: now(),
  };
}
