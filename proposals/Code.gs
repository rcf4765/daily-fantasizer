/**
 * The Daily Fantasizer: Proposals backend (Google Apps Script web app bound to a Google Sheet).
 *
 * The league website (GitHub Pages) is static, so votes live here. Rules enforced on this server:
 *  - A team is claimed once. Claiming hands that phone a secret key; only its SHA-256 is stored.
 *    Every later action for the team must present the key. Only the commissioner can reset a claim.
 *  - One vote per team per proposal. Voting again replaces the team's earlier vote; it never adds one.
 *  - Only claimed teams can propose. One-tap suggestions (PRESETS) carry a fixed title; only those can be
 *    applied to ESPN automatically once passed (rules_espn.py in the repo, Tuesdays).
 *  - Proposals close after WINDOW_DAYS, or as soon as the result
 *    can no longer change (PASS yes votes, or enough no votes that PASS is out of reach).
 *
 * Betting (added 2026-10-26, a side game; ESPN scores never change): a signed-in team places slips of 1..MAX_LEGS
 * legs from the week's board (LINES_URL, published by the paper). The server takes every leg's odds and lock time from
 * that file, never from the page; rejects locked legs, both sides of one market, and stakes over MAX_STAKE for the week.
 * A slip can be cancelled until its first leg locks. Grading happens in the paper's pipeline (bets.py).
 *
 * Setup and redeploy steps: proposals/SETUP.md in the repo.
 */
var TEAMS = 12;             // ESPN team ids 1..12
var PASS = 7;               // yes votes needed out of TEAMS (a majority of the whole league)
var WINDOW_DAYS = 7;        // voting stays open this long
var MAX_OPEN_PER_TEAM = 3;  // open proposals any one team may have at once
var CATEGORIES = ['Scoring', 'Rules', 'Settings'];
var PRESETS = {  // one-tap suggestions; must match rules_presets.json in the repo (the only changes sent to ESPN)
  'rolling-waivers': { category: 'Settings', title: "Rolling waiver priority" },
  'faab': { category: 'Settings', title: "Blind bidding (FAAB)" },
  'weekly-add-cap': { category: 'Rules', title: "Cap pickups at 5 per week" },
  'pass-td-6': { category: 'Scoring', title: "6-point passing touchdowns" },
  'half-ppr': { category: 'Scoring', title: "Half-point PPR" },
  'harder-veto': { category: 'Rules', title: "Harder to veto trades" }
};
var BETTING = true;
var MAX_STAKE = 50, MAX_LEGS = 6, MAX_WIN = 150;
var LINES_URL = 'https://rcf4765.github.io/daily-fantasizer/bets/lines';   // + week + '.json'
// SHA-256 of the commissioner code (the code itself is never stored here).
var ADMIN_HASH = 'be856db5f99b95913f7842695800cfe73f40782ef7380103aad8ff10179aad09';

var SHEETS = {
  Teams: ['team', 'keyHash', 'claimedAt'],
  Proposals: ['id', 'team', 'category', 'title', 'details', 'createdAt', 'deadline', 'status', 'closedAt', 'preset'],
  Votes: ['proposal', 'team', 'choice', 'at'],
  Bets: ['id', 'week', 'team', 'stake', 'legs', 'dec', 'win', 'placedAt', 'status'],
  Log: ['at', 'action', 'team', 'detail']
};

function doGet() {
  return out(withLock(function () { settle(); return state(); }));
}

function doPost(e) {
  var req;
  try { req = JSON.parse(e.postData.contents); } catch (err) { return out({ ok: false, error: 'Bad request.' }); }
  return out(withLock(function () {
    settle();
    var res = handle(req || {});
    if (res.ok) { settle(); res.state = state(); }
    return res;
  }));
}

function handle(r) {
  var team = parseInt(r.team, 10);
  switch (r.action) {
    case 'claim': {
      if (!(team >= 1 && team <= TEAMS)) return fail('Pick a team.');
      if (findRow('Teams', 0, team) > 0) return fail('That team is already claimed. Ask the commissioner if it should be yours.');
      var key = Utilities.getUuid() + Utilities.getUuid();
      sheet('Teams').appendRow([team, sha(key), now()]);
      log('claim', team, '');
      return { ok: true, key: key };
    }
    case 'vote': {
      if (!owns(team, r.key)) return fail('This phone is not signed in to that team.');
      var p = proposal(r.proposal);
      if (!p) return fail('No such proposal.');
      if (p.status !== 'open') return fail('Voting on this proposal has closed.');
      var choice = r.choice === 'yes' || r.choice === 'no' ? r.choice : null;
      if (!choice) return fail('Vote yes or no.');
      var vs = sheet('Votes'), rows = vs.getDataRange().getValues();
      for (var i = rows.length - 1; i >= 1; i--) {               // drop any earlier vote by this team
        if (String(rows[i][0]) === p.id && Number(rows[i][1]) === team) vs.deleteRow(i + 1);
      }
      vs.appendRow([p.id, team, choice, now()]);
      log('vote', team, p.id + ' ' + choice);
      return { ok: true };
    }
    case 'propose': {
      if (!owns(team, r.key)) return fail('This phone is not signed in to that team.');
      var preset = r.preset ? String(r.preset) : '';
      if (preset && !PRESETS.hasOwnProperty(preset)) return fail('Unknown suggestion.');
      var title = preset ? PRESETS[preset].title : clean(r.title, 90), details = clean(r.details, 600);
      var cat = preset ? PRESETS[preset].category : (CATEGORIES.indexOf(r.category) >= 0 ? r.category : null);
      if (!cat) return fail('Pick a category.');
      if (title.length < 5) return fail('Give the proposal a title.');
      if (preset && proposals().some(function (p) { return p.preset === preset && p.status === 'open'; })) return fail('That one is already up for a vote.');
      var open = proposals().filter(function (p) { return p.team === team && p.status === 'open'; }).length;
      if (open >= MAX_OPEN_PER_TEAM) return fail('Your team already has ' + MAX_OPEN_PER_TEAM + ' open proposals.');
      var id = 'P' + (proposals().length + 1);
      var created = new Date();
      sheet('Proposals').appendRow([id, team, cat, title, details, created.toISOString(),
        new Date(created.getTime() + WINDOW_DAYS * 864e5).toISOString(), 'open', '', preset]);
      log('propose', team, id + ' ' + title);
      return { ok: true, id: id };
    }
    case 'bet': {
      if (!BETTING) return fail('Betting is closed.');
      if (!owns(team, r.key)) return fail('This phone is not signed in to that team.');
      var week = parseInt(r.week, 10), stake = Math.round(Number(r.stake) * 100) / 100;
      if (!(week >= 1 && week <= 18)) return fail('Unknown week.');
      if (!(stake >= 1)) return fail('Stake at least 1 point.');
      var ids = (r.legs || []).map(String);
      if (!ids.length || ids.length > MAX_LEGS) return fail('A slip has 1 to ' + MAX_LEGS + ' legs.');
      var board = lines(week);
      if (!board) return fail('The week ' + week + ' board isn’t posted.');
      var t = Date.now(), seen = {}, legs = [], dec = 1;
      for (var i = 0; i < ids.length; i++) {
        var L = board[ids[i]];
        if (!L) return fail('One of those lines is no longer on the board. Refresh and try again.');
        if (t >= Date.parse(L.lock)) return fail(L.desc + ' is locked: that game has started.');
        if (seen[L.mk]) return fail('Only one side of each market per slip.');
        seen[L.mk] = 1;
        legs.push({ id: ids[i], desc: L.desc, odds: L.odds, lock: L.lock });
        dec *= L.odds > 0 ? 1 + L.odds / 100 : 1 + 100 / Math.abs(L.odds);
      }
      var used = bets().filter(function (b) { return b.team === team && b.week === week && b.status !== 'cancelled'; })
        .reduce(function (s, b) { return s + b.stake; }, 0);
      if (used + stake > MAX_STAKE) return fail('That’s over your ' + MAX_STAKE + ' points for week ' + week + ' (' + (MAX_STAKE - used) + ' left).');
      var win = Math.min(MAX_WIN, Math.round(stake * (dec - 1) * 100) / 100);
      var id = 'B' + (bets().length + 1);
      sheet('Bets').appendRow([id, week, team, stake, JSON.stringify(legs), Math.round(dec * 10000) / 10000, win, now(), 'open']);
      log('bet', team, id + ' wk' + week + ' ' + stake);
      return { ok: true, id: id };
    }
    case 'cancelbet': {
      if (!owns(team, r.key)) return fail('This phone is not signed in to that team.');
      var row = findRow('Bets', 0, String(r.bet)), b = bets().filter(function (x) { return x.id === String(r.bet); })[0];
      if (row < 1 || !b || b.team !== team) return fail('No such bet.');
      if (b.status !== 'open') return fail('That bet can’t be cancelled.');
      if (b.legs.some(function (l) { return Date.now() >= Date.parse(l.lock); })) return fail('A leg has already started.');
      sheet('Bets').getRange(row, 9).setValue('cancelled');
      log('cancelbet', team, b.id);
      return { ok: true };
    }
    case 'admin': {
      if (!r.code || sha(String(r.code).trim().toUpperCase()) !== ADMIN_HASH) return fail('Wrong commissioner code.');
      if (r.op === 'check') return { ok: true };
      if (r.op === 'reset') {
        var row = findRow('Teams', 0, team);
        if (row < 1) return fail('That team is not claimed.');
        sheet('Teams').deleteRow(row);
        log('reset', team, 'by commissioner');
        return { ok: true };
      }
      if (r.op === 'withdraw') {
        var pr = findRow('Proposals', 0, String(r.proposal));
        if (pr < 1) return fail('No such proposal.');
        sheet('Proposals').getRange(pr, 8, 1, 2).setValues([['withdrawn', now()]]);
        log('withdraw', '', r.proposal);
        return { ok: true };
      }
      return fail('Unknown commissioner action.');
    }
  }
  return fail('Unknown action.');
}

/** Close proposals whose result is decided or whose window has ended. */
function settle() {
  var t = Date.now(), ps = sheet('Proposals'), tally = tallies();
  proposals().forEach(function (p, i) {
    if (p.status !== 'open') return;
    var c = tally[p.id] || { yes: 0, no: 0 }, status = null;
    if (c.yes >= PASS) status = 'passed';
    else if (TEAMS - c.no < PASS) status = 'failed';
    else if (t >= Date.parse(p.deadline)) status = 'failed';
    if (status) { ps.getRange(i + 2, 8, 1, 2).setValues([[status, now()]]); log(status, '', p.id); }
  });
}

/** Everything the site shows. Keys and hashes never leave the server. */
function state() {
  var votes = rows('Votes').map(function (v) { return { proposal: String(v[0]), team: Number(v[1]), choice: v[2], at: v[3] }; });
  return {
    ok: true,
    rules: { teams: TEAMS, pass: PASS, windowDays: WINDOW_DAYS, categories: CATEGORIES, maxOpen: MAX_OPEN_PER_TEAM, presets: Object.keys(PRESETS),
             betting: BETTING, maxStake: MAX_STAKE, maxLegs: MAX_LEGS, maxWin: MAX_WIN },
    bets: bets(),
    claims: rows('Teams').map(function (t) { return { team: Number(t[0]), at: t[2] }; }),
    proposals: proposals().map(function (p) {
      p.votes = votes.filter(function (v) { return v.proposal === p.id; }).map(function (v) { return { team: v.team, choice: v.choice, at: v.at }; });
      return p;
    }),
    now: now()
  };
}

// ---- helpers ----
function owns(team, key) {
  if (!key) return false;
  var row = findRow('Teams', 0, team);
  return row > 0 && sheet('Teams').getRange(row, 2).getValue() === sha(String(key));
}
function proposals() {
  return rows('Proposals').map(function (r) {
    return { id: String(r[0]), team: Number(r[1]), category: r[2], title: String(r[3]), details: String(r[4]),
      createdAt: iso(r[5]), deadline: iso(r[6]), status: r[7], closedAt: iso(r[8]), preset: String(r[9] || '') };
  });
}
function bets() {
  return rows('Bets').map(function (r) {
    var legs = []; try { legs = JSON.parse(r[4]); } catch (e) {}
    return { id: String(r[0]), week: Number(r[1]), team: Number(r[2]), stake: Number(r[3]), legs: legs, dec: Number(r[5]),
      win: Number(r[6]), placedAt: iso(r[7]), status: String(r[8]) };
  });
}
/** The week's board from the paper's website, indexed by leg id: odds, lock time, market key, description. */
function lines(week) {
  var res = UrlFetchApp.fetch(LINES_URL + week + '.json', { muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) return null;
  var B = JSON.parse(res.getContentText()), ix = {};
  ['nfl', 'league', 'props'].forEach(function (g) {
    (B[g] || []).forEach(function (ev) {
      var who = ev.name || ev.title;
      ev.markets.forEach(function (mk) {
        mk.sel.forEach(function (s) {
          ix[s.id] = { odds: Number(s.odds), lock: ev.lock, mk: ev.id + '|' + mk.m,
            desc: (g === 'props' ? who + ' ' : '') + s.name + (g === 'props' ? ' (' + mk.label.toLowerCase() + ')' : mk.m === 'tot' ? ' · ' + who : '') };
        });
      });
    });
  });
  return ix;
}
function proposal(id) { return proposals().filter(function (p) { return p.id === String(id); })[0]; }
function tallies() {
  var t = {};
  rows('Votes').forEach(function (v) { var k = String(v[0]); t[k] = t[k] || { yes: 0, no: 0 }; if (v[2] === 'yes' || v[2] === 'no') t[k][v[2]]++; });
  return t;
}
function sheet(name) {
  var ss = SpreadsheetApp.getActiveSpreadsheet(), s = ss.getSheetByName(name);
  if (!s) { s = ss.insertSheet(name); s.appendRow(SHEETS[name]); s.setFrozenRows(1); s.getRange('A:Z').setNumberFormat('@'); }
  return s;
}
function rows(name) { var v = sheet(name).getDataRange().getValues(); return v.slice(1); }
function findRow(name, col, value) {
  var v = sheet(name).getDataRange().getValues();
  for (var i = 1; i < v.length; i++) if (String(v[i][col]) === String(value)) return i + 1;
  return -1;
}
function sha(s) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, s, Utilities.Charset.UTF_8)
    .map(function (b) { return ('0' + (b & 255).toString(16)).slice(-2); }).join('');
}
function clean(s, n) { return String(s || '').replace(/[\u0000-\u001f]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, n); }
function iso(v) { return v instanceof Date ? v.toISOString() : String(v || ''); }
function now() { return new Date().toISOString(); }
function log(action, team, detail) { sheet('Log').appendRow([now(), action, team, detail]); }
function fail(msg) { return { ok: false, error: msg }; }
function withLock(fn) {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(15000)) return fail('The league office is busy. Try again in a moment.');
  try { return fn(); } catch (err) { return fail('Server error: ' + err.message); } finally { lock.releaseLock(); }
}
function out(obj) { return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON); }

/** Run once from the editor (Run ▸ setup) to create the tabs and grant permissions. */
function setup() { Object.keys(SHEETS).forEach(sheet); }
