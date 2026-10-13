# The Daily Fantasizer — weekly runbook

The weekly newspaper for the **Men Fantasizing** ESPN league (league 1196354715, season 2026, 12 teams, PPR, H2H points, lineup QB/2RB/2WR/TE/FLEX/D-ST/K, 14 regular-season weeks, 6 playoff teams). Owner/requester: Reza Jalali (team 1, Chimpanzini Bananini). The week 4 edition is the approved reference design. Every new edition must look exactly like it: same template, same sections, same chart types, same voice. Only the data and words change.

## Files in this project (folder `daily-fantasizer/`)

| File | Role | Changes weekly? |
|---|---|---|
| `RUNBOOK.md` | This document | no |
| `extract.js` | Browser snippet: pulls the week's data from ESPN and writes it into the page | set `WEEK` only |
| `extract_logos.js` | Browser snippet: turns team crests into small webp data URIs | only when crests change |
| `facts.py` | Story finder: raw data → `weekN_facts.json` + readable `weekN_facts.md` | no |
| `render.py` | Renderer: template + facts + copy + crests → `daily-fantasizer-weekN.html` | no |
| `template.html` | The approved design (all CSS + page skeleton with placeholders) | no |
| `league.json` | League constants, short team names, running lore | add lore when told |
| `fetch_espn.py` + `.github/workflows/fetch.yml` | No-browser fetcher for a GitHub repo (pending setup; see "Automation") | no |
| `logos.txt` | 12 crests, one line each: `@<teamId> data:image/webp;base64,...` | only when crests change |
| `logo_urls.txt` | ESPN logo URL per team, used to detect crest changes | with logos |
| `week4_raw.txt` | Example raw dump (format reference) | — |
| `week4_copy.json` | **The voice and structure reference.** Every word of the approved edition | — |
| `weekN_raw.txt`, `weekN_copy.json` | Saved after each new edition so later weeks can reference history | add each week |

## Weekly procedure

1. **Set up the workspace.** `mkdir -p paper/data && cd paper`. `project_read` each file above into it (`data/` holds `logos.txt`, `logo_urls.txt`, `weekN_raw.txt`, `weekN_copy.json`; scripts, `template.html`, `league.json` sit at the top level). `project_read` may return the text inline instead of as a local file; then save it with Write exactly as returned (keep the final newline). **Self-test before anything else**: run `sha256sum` on the restored files and compare with `MANIFEST.txt`; re-read any file that doesn't match. Then `python3 facts.py data/week4_raw.txt && python3 render.py 4` and check `sha256sum daily-fantasizer-week4.html` equals the `daily-fantasizer-week4.html` line in the manifest. That proves the pipeline reproduces the approved edition byte for byte. (Later weeks' copy files change nothing about this test.) The workspace cannot reach ESPN directly, so all ESPN access goes through the user's Chrome.
2. **Pick the week.** The edition covers the most recent *completed* week. NFL weeks end after Monday Night Football; ESPN finalizes overnight. If the user doesn't say, use (current matchup period − 1) on a Tuesday-or-later run; on Monday evening the current week is usually still running, so cover the previous one and say so.
3. **Pull data via Claude in Chrome** (the user's Chrome is signed into ESPN; the league is private, so never ask for passwords or cookies):
   - Load the Chrome tools in one ToolSearch (`tabs_context_mcp, navigate, javascript_tool, get_page_text, tabs_create_mcp, tabs_close_mcp`), read the chrome-browser skill if listed, open a new tab, navigate to `https://fantasy.espn.com/football/league?leagueId=1196354715&seasonId=2026`.
   - Paste the full contents of `extract.js` into `javascript_tool` with `WEEK` set. It returns `ok: N lines, week W complete=true|false`. If `complete=false`, stop and tell the user the week isn't final yet.
   - Call `get_page_text` on the same tab. Its output (META…LOGOURLS) is the raw dump. **Do not use javascript_tool return values for data; they truncate at ~1,000 characters.** `get_page_text` returned 40K+ characters without truncation.
   - Write the dump verbatim to `data/weekN_raw.txt` (everything from the `META|` line through the last `LOGOURLS` line).
   - Compare the LOGOURLS block with `data/logo_urls.txt`. If any URL changed (or a team is new), navigate the tab back to the league URL, run `extract_logos.js` (set `ONLY = [ids]` for just the changed teams), `get_page_text`, and replace those lines in `logos.txt` verbatim; update `logo_urls.txt`. Validate every crest: `python3 -c` with PIL to base64-decode each line and `Image.open(...).load()`; a failure means a transcription error, so redo that line.
   - Close the tab.
4. **Compute facts.** `python3 facts.py data/weekN_raw.txt`. It warns if the week isn't final or if any team's starter total doesn't match ESPN's score (a mismatch means bad data; re-extract). Read `data/weekN_facts.md` in full. It lists each game, each team's starters with projections, optimal lineups, points left on the bench, season highs/lows, all-play, luck, misses vs projection, transactions (UNVERIFIED adds may be post-game pickups; skip them or treat with care) and next week's lines.
5. **Write `data/weekN_copy.json`.** Same schema as `week4_copy.json` (read it first, every time). Rules in "Writing the copy" below.
6. **Render.** `python3 render.py N` → `daily-fantasizer-weekN.html`. It fails loudly if a Missing Persons player isn't a starter, and prints leftover placeholders (must be `[]`).
7. **Check before publishing.** One headless screenshot pass (Playwright is installed): 1200px and 400px wide, full page. Look at the hero, the scoreboard chart (axis labels must not collide), game cards, blotter, posters, table, forecast. Fix copy that overflows (long headlines) and re-render once.
8. **Fact-check the copy against `weekN_facts.md`**: every number in the prose must appear in the facts (or be simple arithmetic on them). Recompute any sum you wrote.
9. **Publish** with the Artifact tool as a **new** artifact per week: `file_path` = `daily-fantasizer-weekN.html`, `icon` = `newspaper`, description "Week N edition of The Daily Fantasizer for the Men Fantasizing ESPN league…". The `<title>` stays "The Daily Fantasizer".
10. **Save back to the project**: `project_write` `daily-fantasizer/weekN_raw.txt` and `daily-fantasizer/weekN_copy.json` (via `local_path`), plus `logos.txt`/`logo_urls.txt` if they changed. Don't rewrite unchanged files.
11. **Report** to the user in a few sentences: which week, the lead story, anything odd (unfinished week, unverified transactions, crests updated). Remind them the page is private until shared.

## Writing the copy (voice and rules)

- **Voice**: tabloid sports desk, dry and specific. Short declarative sentences. The joke lives in the numbers ("Three starters projected for zero, three zeros delivered."). Roast lineup *decisions* and results, never anyone's looks, family, job or personal life. Default tone is "normal"; the user may ask for gentler or harsher.
- **Every number comes from the facts file.** No invented quotes, no claims about real NFL events beyond the scores in the data (no injuries, no "he was out with an ankle" unless the user says so; a 0-projection starter means "projected for zero", nothing more).
- **Team references in prose use tokens**: `{T7}` = full name with crest, `{S7}` = short name with crest (short names in `league.json`). Use a token the first time a team appears in a paragraph; later mentions in the same paragraph can be plain short names. Headlines and titles are plain text (no tokens).
- **Hero/lead**: the week's best story, usually the biggest blowout, a historic score, a streak, an upset, or a matchup decided by the bench. `hero.big` is the headline number (usually the margin) with `hero.label`. Lead = kicker, headline (≤ 9 words, punchy, Title-ish caps), deck (one sentence), 3–4 paragraphs of ~45–70 words.
- **Sidebar**: exactly two boxes. Box 1 `style: "hi"` (yellow) is a "Strange but true" oddity; box 2 `style: "plain"` is an analytical angle (luck, all-play, trend). Each has an optional `viz`: `twin` (two crests with values and a symbol), `wins` (actual vs all-play-earned wins for listed teams), or `bars` (`rows: [{team|label, value, alt?}]`).
- **Recaps**: one per game, keyed `"winnerId-loserId"` (either order works). Headline ≤ 7 words; text 40–60 words: the winner's top performers, the loser's misses, and the bench verdict when the best lineup would have won. The page-one game gets a short recap ending the pattern "See Page One".
- **Honor**: "Manager of the week" by default = the team that left the fewest points on the bench (ties: higher score). `big` is that number with 2 decimals, `big_label` "pts left on bench". Owner's first name may appear in the text.
- **Police Blotter**: 4–5 teams with the most points left on the bench or the most absurd lineup decision (zero-projection starters, benched a pickup who went off, wrong D/ST). Title = the "charge"; text = the evidence in 1–2 sentences. The booking number is filled in automatically.
- **Missing Persons**: 4–5 *starters* with the biggest misses vs projection (from "Biggest misses"), names spelled exactly as in the facts. Text is one deadpan sentence.
- **Pecking notes**: one short note (≤ 10 words) per team, all 12, keyed by team id as a string.
- **Classifieds**: one ad per notable executed transaction (6–8 ads; combine a team's small moves). Title is a want-ad phrase; text says who came and went and what they scored if they played. Trades get an ad too.
- **Forecast blurbs**: one per next-week matchup keyed `"homeId-awayId"` from the facts' next-week list, weather-report style, 1 sentence. During the playoffs/championship, if `next_week` is empty the forecast section disappears automatically.
- **Running lore**: if the user shares rivalries, jokes, punishments, nicknames, add them to `league.json` `lore` (and save it to the project) and weave them in on later weeks.

## Design facts (don't change unless the user asks)

Tabloid layout: Big Shoulders Display headlines, Literata body, IBM Plex Mono numbers; ink #151a24 on #f4f5f0 sheet, accent blue #1c3fae, highlight yellow #f2d23c, red #b3261e for the average line and misses; full dark theme. Sections in order: masthead with 12 crests → blue ticker (auto) → halftone hero (two big crests + margin) → lead + two sidebar boxes → "Week N at a Glance" bar chart (actual score bars, blue = won, grey = lost, yellow hatched extension = points left on bench, dashed red league-average line) → six game cards (closest first, crest vs crest, share bar, yellow "Best lineup would have won" tag) → blue Manager of the Week band → Police Blotter (crest mugshots) + Missing Persons (dashed posters with projected vs found bars) → Pecking Order table (all-play rank, record, all-play, PF, weekly sparkline, luck bar, note) → Classifieds → Week N+1 Forecast → footer. Crests are embedded as data URIs (the artifact page can't load ESPN images).

## Known quirks

- ESPN `record.overall` includes nothing in-progress; facts.py computes records from the schedule instead, which is what the paper uses.
- `TRADE_ACCEPT` rows carry no players; extract.js uses executed `TRADE_PROPOSAL` rows for trades.
- Week 4 had a waiver add (Sam Darnold to team 10) that didn't match the roster; facts.py now marks such adds UNVERIFIED.
- Playoff weeks can be two-week matchups in some leagues; this league's settings should be checked when week 15 arrives (look at `regweeks` in META and the schedule's matchup periods).

## Automation

- A Claude scheduled task runs every Tuesday ~9am Pacific and follows this runbook to build and publish that week's edition. No email or text delivery: the user asked for the edition to be created and published only (2026-10-12).
- Data source: Claude in Chrome on the user's computer (needs the computer awake with Chrome signed into ESPN). Planned upgrade: a private GitHub repo `daily-fantasizer` holding this pipeline, where `fetch_espn.py` runs via GitHub Actions on Tuesday mornings using ESPN_S2/ESPN_SWID repo secrets and commits `data/weekN_raw.txt`. Once the repo exists, its name goes in `league.json` as `"repo"`; then clone it (attach with add_repo) and use its `data/weekN_raw.txt` instead of Chrome.
