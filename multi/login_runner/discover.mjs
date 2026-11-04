// Find every football league on a signed-in ESPN account, from inside a real browser on fantasy.espn.com: the same
// requests ESPN's own site makes, with the account's cookies. (Asked from a server instead, ESPN may answer with
// nothing.) Returns { leagues: [{ id, name, teams, team, commissioner, season }], notes: [lines for the trace] }.
// Notes hold counts, statuses and league ids only: no names of people, cookies or emails.

export async function discoverLeagues(chromium, launchOptions, { s2, swid, season, startUrl }) {
  const notes = [];
  const browser = await chromium.launch(launchOptions);
  try {
    const ctx = await browser.newContext({ locale: 'en-US',
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36' });
    const host = startUrl ? new URL(startUrl).hostname : 'fantasy.espn.com';
    const domain = startUrl ? host : '.espn.com';
    await ctx.addCookies([
      { name: 'espn_s2', value: s2, domain, path: '/', secure: !startUrl, sameSite: 'Lax' },
      { name: 'SWID', value: swid, domain, path: '/', secure: !startUrl, sameSite: 'Lax' },
    ]);
    const page = await ctx.newPage();
    await page.goto(startUrl || 'https://fantasy.espn.com/football/', { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => notes.push('fantasy page slow to load'));
    const out = await page.evaluate(async ({ swid, season, api }) => {
      const res = { notes: [], leagues: [] };
      const norm = (s) => String(s || '').toUpperCase().replace(/[{}]/g, '');
      const ids = new Set();
      // 1) ESPN's fan profile: one entry per fantasy team the account has, with its league ("group")
      for (const q of ['?displayHiddenPrefs=true&context=fantasy&useCookieAuth=true&source=fantasyapp-ios&featureFlags=challengeEntries',
                       '?displayEvents=true&displayNow=true&displayRecs=false&displayHiddenPrefs=true&featureFlags=challengeEntries&platform=web&source=fantasy']) {
        try {
          const r = await fetch(`${api.fan}/apis/v2/fans/${encodeURIComponent('{' + norm(swid) + '}')}${q}`, { credentials: 'include' });
          const j = r.ok ? await r.json().catch(() => null) : null;
          const prefs = (j && j.preferences) || [];
          const seen = [];
          for (const p of prefs) {
            const e = p && p.metaData && p.metaData.entry;
            if (!e) continue;
            const gs = (e.groups || []).map((g) => g && g.groupId).filter(Boolean);
            seen.push(`${e.abbrev || '?'}/${e.gameId ?? '?'}/${e.seasonId ?? '?'}:${gs.join(',')}`);
            const football = e.abbrev === 'FFL' || e.gameId === 1 || /football|ffl/i.test(String(e.entryURL || e.name || ''));
            if (football && (!e.seasonId || +e.seasonId === +season)) gs.forEach((g) => ids.add(String(g)));
          }
          res.notes.push(`fan profile: HTTP ${r.status}, ${prefs.length} preference(s), fantasy entries ${seen.join(' ') || 'none'}`);
          if (ids.size) break;
        } catch (e) { res.notes.push(`fan profile failed: ${String(e.message || e).slice(0, 80)}`); }
      }
      // 2) each league: read it with the account's cookies and confirm the account is a member
      for (const id of ids) {
        try {
          const r = await fetch(`${api.lm}/apis/v3/games/ffl/seasons/${season}/segments/0/leagues/${id}?view=mSettings&view=mTeam`, { credentials: 'include' });
          const j = r.ok ? await r.json().catch(() => null) : null;
          if (!j) { res.notes.push(`league ${id}: HTTP ${r.status}`); continue; }
          const me = (j.members || []).find((m) => norm(m.id) === norm(swid));
          const t = (j.teams || []).find((x) => (x.owners || []).some((o) => norm(o) === norm(swid)) || norm(x.primaryOwner) === norm(swid));
          if (!me) { res.notes.push(`league ${id}: account not in member list`); continue; }
          res.leagues.push({ id: String(id), season: +season, name: (j.settings && j.settings.name) || `League ${id}`, teams: (j.teams || []).length,
            commissioner: !!me.isLeagueManager, team: t ? (t.name || [t.location, t.nickname].filter(Boolean).join(' ')) : '' });
          res.notes.push(`league ${id}: member${me.isLeagueManager ? ', commissioner' : ''}, ${(j.teams || []).length} teams`);
        } catch (e) { res.notes.push(`league ${id} failed: ${String(e.message || e).slice(0, 80)}`); }
      }
      return res;
    }, { swid, season, api: startUrl ? { fan: new URL(startUrl).origin, lm: new URL(startUrl).origin } : { fan: 'https://fan.api.espn.com', lm: 'https://lm-api-reads.fantasy.espn.com' } });
    notes.push(...out.notes);
    return { leagues: out.leagues, notes };
  } catch (e) {
    notes.push(`league lookup failed: ${String(e.message || e).slice(0, 120)}`);
    return { leagues: null, notes };
  } finally {
    await browser.close().catch(() => {});
  }
}
