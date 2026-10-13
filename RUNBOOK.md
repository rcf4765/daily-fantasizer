# The Daily Fantasizer — weekly runbook

The weekly newspaper for the **Men Fantasizing** ESPN league (league 1196354715, season 2026, 12 teams, PPR, H2H points, lineup QB/2RB/2WR/TE/FLEX/D-ST/K, 14 regular-season weeks, 6 playoff teams). Owner/requester: Reza Jalali (team 1, Chimpanzini Bananini). The week 4 edition is the approved reference design. Every new edition must look exactly like it: same template, same sections, same chart types, same voice. Only the data and words change.

## Files in this project (folder `daily-fantasizer/`)

| File | Role | Changes weekly? |
|---|---|---|
| `RUNBOOK.md` | This document | no |
| `extract.js` | Fallback browser snippet: pulls the week's data from ESPN and writes it into the page | set `WEEK` only |
| `extract_logos.js` | Browser snippet: turns team crests into small webp data URIs | only when crests change |
| `facts.py` | Story finder: raw data → `weekN_facts.json` + readable `weekN_facts.md` | no |
| `render.py` | Renderer: template + facts + copy + crests → `daily-fantasizer-weekN.html` | no |
| `template.html` | The approved design (all CSS + page skeleton with placeholders) | no |
| `league.json` | League constants, short team names, running lore | add lore when told |
| `fetch_espn.py` + `.github/workflows/fetch.yml` | Weekly no-browser fetcher run by GitHub Actions in rcf4765/daily-fantasizer | no |
| `logos.txt` | 12 crests, one line each: `@<teamId> data:image/webp;base64,...` | only when crests change |
| `logo_urls.txt` | ESPN logo URL per team, used to detect crest changes | with logos |
| `week4_raw.txt` | Example raw dump (format reference) | — |
| `week4_copy.json` | **The voice and structure reference.** Every word of the approved edition | — |
| `weekN_raw.txt`, `weekN_copy.json` | Saved after each new edition so later weeks can reference history | add each week |

## Weekly procedure

1. **Set up the workspace.** The GitHub repo **rcf4765/daily-fantasizer** is the source of truth (the project folder mirrors it). Attach it with `add_repo` (owner `rcf4765`, repo `daily-fantasizer`, access `push`) and clone it to `/home/claude/daily-fantasizer`; work there. Only if the repo can't be reached, restore the files from the project folder instead (`project_read` each into `paper/` and `paper/data/`; save inline results with Write exactly as returned). **Self-test before anything else**: `sha256sum` the files listed in `MANIFEST.txt` and compare; then `python3 facts.py data/week4_raw.txt && python3 render.py 4` and confirm `daily-fantasizer-week4.html` matches its manifest hash. That proves the pipeline reproduces the approved edition byte for byte. The workspace cannot reach ESPN directly.
2. **Pick the week.** The edition covers the most recent *completed* week. NFL weeks end after Monday Night Football; ESPN finalizes overnight. If the user doesn't say, use (current matchup period − 1) on a Tuesday-or-later run; on Monday evening the current week is usually still running, so cover the previous one and say so.
3. **Get the data.** A GitHub Actions workflow (`.github/workflows/fetch.yml` running `fetch_espn.py` with the ESPN_S2/ESPN_SWID repo secrets) fetches the latest completed week every Tuesday ~5:17am Eastern (retry Wednesday) and commits `data/weekN_raw.txt` plus any crest updates (`logos.txt`, `logo_urls.txt`) and `data/latest.json`. So: `git pull`, then check `data/latest.json` and that `data/weekN_raw.txt` exists for the week.
   - If it's missing, trigger it yourself: `gh api -X POST repos/rcf4765/daily-fantasizer/actions/workflows/fetch.yml/dispatches -f ref=main -f 'inputs[week]=N'`, wait ~1–2 min, poll `gh api "repos/rcf4765/daily-fantasizer/actions/runs?per_page=1"` until `completed`, then `git pull`. A run that prints "not final" means ESPN hasn't finished the week: stop and report.
   - If the run fails with 401/403/HTML, the ESPN cookies in the repo secrets have expired. Tell the user to replace `ESPN_S2` and `ESPN_SWID` at https://github.com/rcf4765/daily-fantasizer/settings/secrets/actions (values from Chrome DevTools → Application → Cookies → fantasy.espn.com). Never ask for or handle the cookie values yourself.
   - **Fallback only if GitHub is unavailable**: the Claude in Chrome method. Load the Chrome tools in one ToolSearch (`tabs_context_mcp, navigate, javascript_tool, get_page_text, tabs_create_mcp, tabs_close_mcp`), open a new tab at `https://fantasy.espn.com/football/league?leagueId=1196354715&seasonId=2026`, run `extract.js` with `WEEK` set via `javascript_tool`, then `get_page_text` and save the dump verbatim to `data/weekN_raw.txt` (javascript_tool return values truncate at ~1,000 chars; get_page_text doesn't). For changed crests, run `extract_logos.js` the same way and validate each crest with PIL. Close the tab.
4. **Compute facts.** `python3 facts.py data/weekN_raw.txt`. It warns if the week isn't final or if any team's starter total doesn't match ESPN's score (a mismatch means bad data; re-extract). Read `data/weekN_facts.md` in full. It lists each game, each team's starters with projections, optimal lineups, points left on the bench, season highs/lows, all-play, luck, misses vs projection, transactions (UNVERIFIED adds may be post-game pickups; skip them or treat with care) and next week's lines.
5. **Write `data/weekN_copy.json`.** Same schema as `week4_copy.json` (read it first, every time). Rules in "Writing the copy" below.
6. **Render.** `python3 render.py N` → `daily-fantasizer-weekN.html`. It fails loudly if a Missing Persons player isn't a starter, and prints leftover placeholders (must be `[]`).
7. **Check before publishing.** One headless screenshot pass (Playwright is installed): 1200px and 400px wide, full page. Look at the hero, the scoreboard chart (axis labels must not collide), game cards, blotter, posters, table, forecast. Fix copy that overflows (long headlines) and re-render once.
8. **Fact-check the copy against `weekN_facts.md`**: every number in the prose must appear in the facts (or be simple arithmetic on them). Recompute any sum you wrote.
9. **Publish** with the Artifact tool as a **new** artifact per week: `file_path` = `daily-fantasizer-weekN.html`, `icon` = `newspaper`, description "Week N edition of The Daily Fantasizer for the Men Fantasizing ESPN league…". The `<title>` stays "The Daily Fantasizer".
10. **Save.** Commit `data/weekN_copy.json` and `daily-fantasizer-weekN.html` to the repo and push (data/*_facts.* stay ignored). Also `project_write` `daily-fantasizer/weekN_raw.txt` and `weekN_copy.json` to the project as a mirror, plus `logos.txt`/`logo_urls.txt`/`league.json` if they changed.
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

- **Tuesday ~5:17am Eastern** (4:17am in winter): GitHub Actions fetches the week's ESPN data into the repo (no computer or browser needed). Wednesday same time: retry if the week wasn't final.
- **Tuesday 6am Eastern** (America/Detroit; changed from 9am Pacific on 2026-10-13 at the user's request): a Claude scheduled task ("Daily Fantasizer weekly edition") follows this runbook, builds and publishes the edition as a new artifact. No email or text delivery (user's choice, 2026-10-12).
- ESPN cookies usually last about a year. GitHub disables scheduled workflows after 60 days with no repo activity; the weekly commits keep it alive, but in the off-season it may need re-enabling from the repo's Actions tab.
- `fetch_espn.py` was validated 2026-10-12: its week 4 dump matched the Chrome extraction exactly (plus one waiver row facts.py flags UNVERIFIED), and the rendered week 4 edition was byte-identical to the approved one.
