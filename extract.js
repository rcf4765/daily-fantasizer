// The Daily Fantasizer: ESPN data extractor.
// Run with Claude in Chrome's javascript_tool on a tab at
//   https://fantasy.espn.com/football/league?leagueId=1196354715&seasonId=2026
// (user must be signed in to ESPN in that Chrome). Set WEEK first.
// It writes the raw text into the page body; then read it with get_page_text
// (javascript_tool output truncates near 1,000 chars, get_page_text does not).
const WEEK = 4;            // <-- the completed week the edition covers
const LEAGUE = 1196354715, SEASON = 2026;
const base = `https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/${SEASON}/segments/0/leagues/${LEAGUE}`;
const get = async (q, headers = {}) => { const r = await fetch(base + q, { credentials: 'include', headers }); if (!r.ok) throw new Error('HTTP ' + r.status + ' ' + q); return r.json(); };
const POS = { 1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K', 16: 'D/ST' };
const SLOT = { 0: 'QB', 2: 'RB', 4: 'WR', 6: 'TE', 16: 'D/ST', 17: 'K', 20: 'BE', 21: 'IR', 23: 'FLEX', 3: 'RB/WR', 5: 'WR/TE', 7: 'OP' };
const r2 = x => Math.round((x || 0) * 100) / 100;

const L = await get('?view=mTeam&view=mSettings&view=mStatus&view=mMatchupScore');
const mem = {}; (L.members || []).forEach(m => mem[m.id] = ((m.firstName || '') + ' ' + (m.lastName || '')).trim());
const out = [];
const weekGames = L.schedule.filter(s => s.matchupPeriodId === WEEK);
const complete = weekGames.length > 0 && weekGames.every(s => s.winner && s.winner !== 'UNDECIDED');
out.push(`META|league=${LEAGUE}|season=${SEASON}|week=${WEEK}|name=${L.settings.name}|latest=${L.status.latestScoringPeriod}|complete=${complete ? 1 : 0}|regweeks=${L.settings.scheduleSettings.matchupPeriodCount}|playoffteams=${L.settings.scheduleSettings.playoffTeamCount}`);
out.push('SLOTS|' + Object.entries(L.settings.rosterSettings.lineupSlotCounts).filter(([k, v]) => v > 0 && !['20', '21'].includes(k)).map(([k, v]) => (SLOT[k] || 'SLOT' + k) + ':' + v).join(','));
out.push('TEAMS');
L.teams.forEach(t => out.push([t.id, (t.name || ((t.location || '') + ' ' + (t.nickname || ''))).trim(), t.abbrev, (t.owners || []).map(o => mem[o]).join(' & ')].join('|')));
out.push('SCHED');
L.schedule.filter(s => s.matchupPeriodId <= WEEK + 1).forEach(s => out.push([s.matchupPeriodId, s.home?.teamId, r2(s.home?.totalPoints), s.away?.teamId ?? 0, r2(s.away?.totalPoints), s.winner].join('|')));

const B = await get(`?view=mMatchupScore&view=mBoxscore&scoringPeriodId=${WEEK}`);
out.push('ROSTERS');
B.schedule.filter(s => s.matchupPeriodId === WEEK).forEach(s => [s.home, s.away].forEach(side => {
  if (!side) return; out.push('#' + side.teamId);
  (side.rosterForCurrentScoringPeriod?.entries || []).forEach(e => {
    const p = e.playerPoolEntry.player, st = p.stats || [];
    const act = st.find(x => x.statSourceId === 0 && x.scoringPeriodId === WEEK), proj = st.find(x => x.statSourceId === 1 && x.scoringPeriodId === WEEK);
    out.push([p.fullName, POS[p.defaultPositionId] || p.defaultPositionId, SLOT[e.lineupSlotId] || e.lineupSlotId, r2(act?.appliedTotal ?? e.playerPoolEntry.appliedStatTotal), Math.round((proj?.appliedTotal || 0) * 10) / 10].join('|'));
  });
}));

const X = await get(`?view=mTransactions2&scoringPeriodId=${WEEK}`);
// executed adds/drops and executed trades only (TRADE_ACCEPT rows carry no items; pending/declined proposals are private)
const txs = (X.transactions || []).filter(t => ['FREEAGENT', 'WAIVER', 'TRADE_PROPOSAL'].includes(t.type) && t.status === 'EXECUTED' && (t.items || []).length);
const ids = [...new Set(txs.flatMap(t => (t.items || []).map(i => i.playerId)))];
const nm = {};
if (ids.length) { const pl = await (await fetch(`https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/${SEASON}/players?scoringPeriodId=${WEEK}&view=players_wl`, { credentials: 'include', headers: { 'x-fantasy-filter': JSON.stringify({ filterIds: { value: ids } }) } })).json(); (Array.isArray(pl) ? pl : []).forEach(p => nm[p.id] = p.fullName); }
out.push('TX');
txs.forEach(t => out.push([{ FREEAGENT: 'F', WAIVER: 'W', TRADE_PROPOSAL: 'T' }[t.type], t.teamId, (t.items || []).map(i => i.type + ':' + (nm[i.playerId] || i.playerId) + (i.type === 'TRADE' ? ':' + i.fromTeamId + '>' + i.toTeamId : '')).join(',')].join('|')));
out.push('LOGOURLS');
L.teams.forEach(t => out.push(t.id + '|' + t.logo));

document.body.innerHTML = '<article><pre id="cd-dump"></pre></article>';
document.getElementById('cd-dump').textContent = out.join('\n');
`ok: ${out.length} lines, week ${WEEK} complete=${complete}. Now call get_page_text.`
