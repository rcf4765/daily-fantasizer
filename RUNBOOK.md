# The Daily Fantasizer — weekly runbook

The weekly newspaper for the **Men Fantasizing** ESPN league (league 1196354715, season 2026, 12 teams, PPR, H2H points, lineup QB/2RB/2WR/TE/FLEX/D-ST/K, 14 regular-season weeks, 6 playoff teams). Owner/requester: Reza Jalali (team 1, Chimpanzini Bananini).

**The approved design is the graphics-first layout introduced with the week 5 edition on 2026-10-13** ("less text, more graphics", subtle Detroit Lions accents, no memes, no trade rumors). Every new edition must look exactly like it: same template, same sections, same chart types, same voice. Only the data and words change. The older text-heavy tabloid design (week 4 reference) is archived in `legacy/` and must not be used.

## Files (repo root = project folder `daily-fantasizer/`)

| File | Role | Changes weekly? |
|---|---|---|
| `RUNBOOK.md` | This document | no |
| `template.html` | The approved design: all CSS + page skeleton with placeholders | no |
| `render.py` | Renderer: template + facts + raw rosters + trades + copy + crests → `daily-fantasizer-weekN.html` | no |
| `facts.py` | Story finder: raw data → `weekN_facts.json` + readable `weekN_facts.md` | no |
| `fetch_espn.py` | Weekly no-browser fetcher (GitHub Actions): `data/weekN_raw.txt`, crests, `data/latest.json` | no |
| `fetch_trades.py` | Same workflow: completed trades → `data/trades.json`; league trading block → `data/trade_block.json` | no |
| `extract.js`, `extract_logos.js` | Browser fallback snippets for when GitHub is unavailable | set `WEEK` only |
| `league.json` | League constants, short team names, `owner_team`, running lore | add lore when told |
| `data/logos.txt`, `data/logo_urls.txt` | 12 crests as webp data URIs + their ESPN URLs | only when crests change |
| `data/weekN_raw.txt` | ESPN dump for week N | add each week |
| `data/weekN_copy.json` | Every word of week N's edition. **`data/week5_copy.json` is the voice and schema reference** | add each week |
| `data/trades.json` | Season-to-date **completed** trades (no pending/declined offers) | refreshed weekly |
| `data/trade_block.json` | Each team's ESPN trading block + which teams ESPN returned it for | refreshed weekly |
| `legacy/` | The retired v1 design (template, renderer, copies, renders). Reference only | never |

## Weekly procedure

1. **Set up the workspace.** Attach **rcf4765/daily-fantasizer** with `add_repo` (owner `rcf4765`, repo `daily-fantasizer`, access `push`) and clone it to `/home/claude/daily-fantasizer`; work there. Only if the repo can't be reached, restore the files from the project folder instead (`project_read` each into the same layout). **Self-test before anything else**: `sha256sum` the files listed in `MANIFEST.txt` and compare; then `python3 facts.py data/week5_raw.txt && python3 render.py 5` and confirm `daily-fantasizer-week5.html` matches its manifest hash. That proves the pipeline reproduces the approved edition byte for byte. (Note: render.py reads `data/trades.json` and `data/trade_block.json`, which change weekly; if only the week 5 render hash differs and those files changed since 2026-10-13, treat it as expected.) The workspace cannot reach ESPN directly.
2. **Pick the week.** The edition covers the most recent *completed* week. NFL weeks end after Monday Night Football; ESPN finalizes overnight. If the user doesn't say, use (current matchup period − 1) on a Tuesday-or-later run.
3. **Get the data.** The GitHub Actions workflow (`.github/workflows/fetch.yml`, ESPN_S2/ESPN_SWID repo secrets) runs `fetch_espn.py` then `fetch_trades.py` every Tuesday ~5:17am Eastern (retry Wednesday) and commits `data/weekN_raw.txt`, `data/trades.json`, `data/trade_block.json`, crest updates and `data/latest.json`. So: `git pull`, then check `data/latest.json` and that `data/weekN_raw.txt` exists.
   - If it's missing, trigger it: `gh api -X POST repos/rcf4765/daily-fantasizer/actions/workflows/fetch.yml/dispatches -f ref=main -f 'inputs[week]=N'`, poll `gh api "repos/rcf4765/daily-fantasizer/actions/runs?per_page=1"` until `completed`, then `git pull`. "not final" means ESPN hasn't finished the week: stop and report.
   - 401/403/HTML means the ESPN cookies in the repo secrets expired. Tell the user to replace `ESPN_S2` and `ESPN_SWID` at https://github.com/rcf4765/daily-fantasizer/settings/secrets/actions. Never ask for or handle cookie values yourself.
   - The trade step is `continue-on-error`; if it failed, the Trade Desk / On the Block sections are left out. Say so in the report.
   - **Fallback only if GitHub is unavailable**: Claude in Chrome with `extract.js` (see the script header). Trade data can't be fetched that way; the section will be omitted.
4. **Compute facts.** `python3 facts.py data/weekN_raw.txt`. Read `data/weekN_facts.md` in full.
5. **Write `data/weekN_copy.json`.** Same schema as `data/week5_copy.json` (read it first, every time). Rules below.
6. **Render.** `python3 render.py N` → `daily-fantasizer-weekN.html`. Leftover placeholders must be `[]`.
7. **Check.** One headless screenshot pass (Playwright): 1200px and 400px wide, full page; `document.documentElement.scrollWidth` must equal the viewport width. Look at the hero starter strips, the glance chart axis, boom/bust names, scatter (crests must not sit on the quadrant labels), heat map, trade cards if present. Fix overflowing copy and re-render once.
8. **Fact-check** every number in the copy against `weekN_facts.md` (or `weekN_raw.txt` / earlier weeks' facts for history claims).
9. **Publish** with the Artifact tool as a **new** artifact per week: `file_path` = `daily-fantasizer-weekN.html`, `icon` = `newspaper`, description "Week N edition of The Daily Fantasizer for the Men Fantasizing ESPN league". The `<title>` stays "The Daily Fantasizer".
10. **Save.** Commit `data/weekN_copy.json` and `daily-fantasizer-weekN.html` and push. Mirror `weekN_raw.txt` and `weekN_copy.json` (and `league.json`/crest files if changed) to the project folder.
11. **Report** in a few sentences: week, lead story, anything odd (unfinished week, unverified transactions, crest updates, missing trade data, and how many teams On the Block covered). Remind the user the page is private until shared.

## Writing the copy (voice and rules)

**Less text, more graphics.** The charts carry the story; words are captions. Keep every field near the lengths in `week5_copy.json`.

- **Voice**: tabloid sports desk, dry and specific. The joke lives in the numbers. Roast lineup *decisions* and results, never anyone's looks, family, job or personal life. **No memes** (the user removed them).
- **Every number comes from the data.** No invented quotes, injuries or NFL news. A 0-projection starter is "projected for zero", nothing more.
- **Team tokens** in prose: `{T7}` full name with crest, `{S7}` short name with crest. Headlines and titles are plain text.
- `hero`: `winner`, `loser` (usually the week's lead game), `big` (the headline number, usually the margin), `label` (≤ 6 words). The starter strips under it are automatic.
- `lead`: kicker, headline (≤ 6 words), deck (one sentence, ≤ 20 words), **two** paragraphs of ≤ 35 words.
- `sidebar`: exactly two boxes. Box 1 `style: "hi"` "Strange but true"; box 2 `style: "plain"` analytical angle. Each has a `viz` (`bars` with rows `{team|label, value, alt?}`, or `wins` with `teams`) and ≤ 25 words of text.
- `recaps`: one per game keyed `"winnerId-loserId"`; headline ≤ 6 words, text ≤ 20 words (top performers, the bench verdict). The page-one game's headline is "See Page One".
- `honor`: Manager of the Week = fewest points left on the bench (ties: higher score). `big` with 2 decimals, `big_label` "pts left on bench", text ≤ 30 words.
- `blotter`: 4 teams, title = the charge (≤ 6 words), text ≤ 15 words. Booking number is automatic.
- `missing`: 4 starters with the biggest misses vs projection, names exactly as in facts; text ≤ 8 words.
- `pecking_notes`: all 12 teams, ≤ 6 words each.
- `forecast_blurbs`: one per next-week matchup keyed `"homeId-awayId"`, ≤ 8 words.
- Automatic sections (no copy): stat tiles, hero strips, Week at a Glance, Boom or Bust, Scoreboard lanes, Points by Position, Position Kings, Season Heat Map, Good or Lucky?, The Wire (verified transactions), Trade Desk, On the Block, forecast bars.
- **Running lore**: add rivalries/jokes/nicknames the user shares to `league.json` `lore` and weave them in later.

## Design facts (don't change unless the user asks)

Fonts: Big Shoulders Display headlines, Literata body, IBM Plex Mono numbers. Ink #151a24 on #f4f5f0 sheet, royal blue #1c3fae (won/main data), yellow #f2d23c (highlights, bench gap), red #b3261e (average line, busts, misses). **Lions accents, kept subtle:** Honolulu blue #0076b6 and silver #b0b7bc for the pinstripe under the masthead, the tab on every section rule, the heat-map scale, the "earned" bars, position colors, forecast card tops, and the Honolulu Manager of the Week band with silver ring; losing bars are silver; footer "printed in the 313". Full dark theme.

Sections in order: masthead with 12 crests → blue stat tiles (avg, high, low, top player, left on benches, perfect lineups) → halftone hero (two crests, margin, starter strips) → lead + two sidebar boxes → Week at a Glance (score bars + bench gap + avg line) beside Boom or Bust (top 5 beats / top 5 misses vs projection) → The Scoreboard (six game cards, closest first, score lanes with yellow best-lineup tick, "Best lineup would have won" tag) → Manager of the Week band → Points by Position stacked bars beside Position Kings → Police Blotter beside Missing Persons → Season Heat Map beside Good or Lucky? (PF vs PA scatter) → Pecking Order table (all-play rank, record, W/L form chips, all-play, PF, sparkline, luck bar, note) → Trade Desk (only when a trade has been completed: season tallies + newest 6 completed trades, players received with week-N points) → On the Block (when at least 10 teams report trading-block data) → The Wire (add/drop chips with points) → Week N+1 Forecast → footer.

## Trades and the trading block

- **No trade rumors.** The user decided (2026-10-13) to publish only trades that actually happened. ESPN only shows pending/declined/expired offers to the managers involved, so those are never fetched, stored or mentioned.
- **Trade Desk**: completed trades (`TRADE_PROPOSAL` with status EXECUTED) are league-public. The section appears automatically when the season has at least one; otherwise it is omitted.
- **On the Block** lists players managers marked "on the trading block" in ESPN (ON_THE_BLOCK only; untouchable and normal players are never shown), as yellow-tagged cards with week-N points, projection and whether they started. **User's rule (updated 2026-10-13): 10 of 12 teams reporting is enough** (`league.json` `trade_block_min_teams`). The note under the section names teams with no trading block data. If no player is listed, the section shows a "Nobody's selling" card. As of 2026-10-13 ESPN returns the field for 10 of 12 teams (not Kazakhstan [11] or Bedazzled Balls [12]).

## Known quirks

- ESPN `record.overall` ignores in-progress games; facts.py computes records from the schedule.
- `TRADE_ACCEPT` rows carry no players; executed trades come from `TRADE_PROPOSAL` rows with status EXECUTED.
- Waiver adds not on the week's roster are marked UNVERIFIED by facts.py and left out of The Wire.
- Playoff weeks: check `regweeks` in META and the schedule's matchup periods when week 15 arrives. If `next_week` is empty the forecast disappears automatically.

## Automation

- **Tuesday ~5:17am Eastern**: GitHub Actions fetches the week's ESPN data and trade activity into the repo. Wednesday same time: retry.
- **Tuesday 5:58am Eastern** (America/Detroit): the Claude scheduled task "Daily Fantasizer weekly edition" follows this runbook, builds and publishes the edition as a new artifact. No email or text delivery (user's choice, 2026-10-12).
- ESPN cookies usually last about a year. GitHub disables scheduled workflows after 60 days without repo activity; in the off-season it may need re-enabling from the repo's Actions tab.
- History: v1 design approved 2026-10-12 (week 4); replaced by the graphics-first design 2026-10-13 (week 5) at the user's request.
