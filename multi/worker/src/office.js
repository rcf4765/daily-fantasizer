// The league office for any league: Rule Changes votes and Betting slips.
// A port of proposals/Code.gs (the Men Fantasizing Google Sheet backend) onto one file per league in the data repo
// (office/<slug>.json, see data.js), with the same request and
// response shapes, so the paper's own page script talks to it unchanged. Differences, per league:
//  - teams = the league's size, a proposal passes with a majority of the whole league;
//  - only works when the commissioner turned Rule Changes and/or Betting on in Settings;
//  - the week's betting board comes from the printed edition (papers/<slug>/bets/linesN.json);
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

export async function officeGet(env, L, D) {
  await D.updateOffice(L.slug, (o) => (settle(L, o) ? o : undefined));
  return state(L, await D.office(L.slug));
}

export async function officePost(env, L, req, D) {
  let r;
  try { r = await req.json(); } catch { return fail('Bad request.'); }
  const board = r && r.action === 'bet' ? await lines(D, L, parseInt(r.week, 10)) : null;
  let res;
  const o = await D.updateOffice(L.slug, async (o) => {
    settle(L, o);
    res = await handle(L, o, r || {}, board);
    if (!res.ok) return undefined;
    settle(L, o);
    return o;
  });
  if (res.ok) res.state = state(L, o);
  return res;
}

const owns = async (o, team, key) => !!key && !!o.claims[team] && o.claims[team].key_hash === await sha256(String(key));
const log = (o, action, team, detail) => { o.log.push({ at: now(), action, team: team === '' ? null : team, detail: String(detail || '') }); o.log = o.log.slice(-500); };

async function lines(D, L, week) {
  if (!(week >= 1 && week <= 18)) return null;
  const r = await D.paper(L.slug, `bets/lines${week}.json`);
  if (!r) return null;
  const B = await r.json(), ix = {};
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

async function handle(L, o, r, board) {
  const T = L.teams, team = parseInt(r.team, 10);
  const rulesOn = !!L.feat_rules, betsOn = !!L.feat_bets;
  switch (r.action) {
    case 'claim': {
      if (!(team >= 1 && team <= T)) return fail('Pick a team.');
      if (o.claims[team]) return fail('That team is already claimed. Ask the commissioner if it should be yours.');
      const key = crypto.randomUUID() + crypto.randomUUID();
      o.claims[team] = { key_hash: await sha256(key), at: now() };
      log(o, 'claim', team, '');
      return { ok: true, key };
    }
    case 'vote': {
      if (!rulesOn) return fail('Rule Changes is turned off for this league.');
      if (!await owns(o, team, r.key)) return fail('This phone is not signed in to that team.');
      const p = o.proposals.find((x) => x.id === String(r.proposal));
      if (!p) return fail('No such proposal.');
      if (p.status !== 'open') return fail('Voting on this proposal has closed.');
      const choice = r.choice === 'yes' || r.choice === 'no' ? r.choice : null;
      if (!choice) return fail('Vote yes or no.');
      o.votes = o.votes.filter((v) => !(v.proposal === p.id && v.team === team));
      o.votes.push({ proposal: p.id, team, choice, at: now() });
      log(o, 'vote', team, `${p.id} ${choice}`);
      return { ok: true };
    }
    case 'propose': {
      if (!rulesOn) return fail('Rule Changes is turned off for this league.');
      if (!await owns(o, team, r.key)) return fail('This phone is not signed in to that team.');
      const preset = r.preset ? String(r.preset) : '';
      if (preset && !Object.prototype.hasOwnProperty.call(PRESETS, preset)) return fail('Unknown suggestion.');
      const title = preset ? PRESETS[preset].title : clean(r.title, 90), details = clean(r.details, 600);
      const cat = preset ? PRESETS[preset].category : (CATEGORIES.includes(r.category) ? r.category : null);
      if (!cat) return fail('Pick a category.');
      if (title.length < 5) return fail('Give the proposal a title.');
      const all = o.proposals;
      if (preset && all.some((p) => p.preset === preset && p.status === 'open')) return fail('That one is already up for a vote.');
      if (all.filter((p) => p.team === team && p.status === 'open').length >= MAX_OPEN_PER_TEAM) return fail(`Your team already has ${MAX_OPEN_PER_TEAM} open proposals.`);
      const id = `P${all.length + 1}`, created = new Date();
      all.push({ id, team, category: cat, title, details, createdAt: created.toISOString(),
        deadline: new Date(created.getTime() + WINDOW_DAYS * 864e5).toISOString(), status: 'open', closedAt: '', preset });
      log(o, 'propose', team, `${id} ${title}`);
      return { ok: true, id };
    }
    case 'bet': {
      if (!betsOn) return fail('Betting is turned off for this league.');
      if (!await owns(o, team, r.key)) return fail('This phone is not signed in to that team.');
      const week = parseInt(r.week, 10), stake = Math.round(Number(r.stake) * 100) / 100;
      if (!(week >= 1 && week <= 18)) return fail('Unknown week.');
      if (!(stake >= 1)) return fail('Stake at least 1 point.');
      const ids = (r.legs || []).map(String);
      if (!ids.length || ids.length > MAX_LEGS) return fail(`A slip has 1 to ${MAX_LEGS} legs.`);
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
      const used = o.bets.filter((b) => b.team === team && b.week === week && b.status !== 'cancelled').reduce((s, b) => s + b.stake, 0);
      if (used + stake > MAX_STAKE) return fail(`That’s over your ${MAX_STAKE} points for week ${week} (${MAX_STAKE - used} left).`);
      const win = Math.min(MAX_WIN, Math.round(stake * (decv - 1) * 100) / 100);
      const id = `B${o.bets.length + 1}`;
      o.bets.push({ id, week, team, stake, legs, dec: Math.round(decv * 10000) / 10000, win, placedAt: now(), status: 'open' });
      log(o, 'bet', team, `${id} wk${week} ${stake}`);
      return { ok: true, id };
    }
    case 'cancelbet': {
      if (!await owns(o, team, r.key)) return fail('This phone is not signed in to that team.');
      const b = o.bets.find((x) => x.id === String(r.bet));
      if (!b || b.team !== team) return fail('No such bet.');
      if (b.status !== 'open') return fail('That bet can’t be cancelled.');
      if (b.legs.some((l) => Date.now() >= Date.parse(l.lock))) return fail('A leg has already started.');
      b.status = 'cancelled';
      log(o, 'cancelbet', team, b.id);
      return { ok: true };
    }
    case 'admin': {
      if (!r.code || !L.comm_code_hash || await sha256(String(r.code).trim().toUpperCase()) !== L.comm_code_hash) return fail('Wrong commissioner code.');
      if (r.op === 'check') return { ok: true };
      if (r.op === 'reset') {
        if (!o.claims[team]) return fail('That team is not claimed.');
        delete o.claims[team];
        log(o, 'reset', team, 'by commissioner');
        return { ok: true };
      }
      if (r.op === 'withdraw') {
        const p = o.proposals.find((x) => x.id === String(r.proposal));
        if (!p) return fail('No such proposal.');
        p.status = 'withdrawn'; p.closedAt = now();
        log(o, 'withdraw', '', r.proposal);
        return { ok: true };
      }
      return fail('Unknown commissioner action.');
    }
  }
  return fail('Unknown action.');
}

/** Close proposals whose result is decided or whose window has ended. Returns true when anything changed. */
function settle(L, o) {
  const T = L.teams, PASS = Math.floor(T / 2) + 1, t = Date.now();
  let changed = false;
  for (const p of o.proposals.filter((x) => x.status === 'open')) {
    const yes = o.votes.filter((v) => v.proposal === p.id && v.choice === 'yes').length;
    const no = o.votes.filter((v) => v.proposal === p.id && v.choice === 'no').length;
    let status = null;
    if (yes >= PASS) status = 'passed';
    else if (T - no < PASS) status = 'failed';
    else if (t >= Date.parse(p.deadline)) status = 'failed';
    if (status) { p.status = status; p.closedAt = now(); log(o, status, '', p.id); changed = true; }
  }
  return changed;
}

/** Everything the page shows. Keys and hashes never leave the server. */
function state(L, o) {
  const T = L.teams;
  return {
    ok: true,
    rules: { teams: T, pass: Math.floor(T / 2) + 1, windowDays: WINDOW_DAYS, categories: CATEGORIES, maxOpen: MAX_OPEN_PER_TEAM,
      presets: L.feat_rules ? Object.keys(PRESETS) : [], betting: !!L.feat_bets, maxStake: MAX_STAKE, maxLegs: MAX_LEGS, maxWin: MAX_WIN },
    bets: o.bets,
    claims: Object.entries(o.claims).map(([team, c]) => ({ team: +team, at: c.at })).sort((a, b) => a.team - b.team),
    proposals: o.proposals.map((p) => ({ ...p, votes: o.votes.filter((v) => v.proposal === p.id).map((v) => ({ team: v.team, choice: v.choice, at: v.at })) })),
    now: now(),
  };
}
