# The Daily Fantasizer for any league: setup

The Men Fantasizing paper keeps working exactly as before (same pipeline, same site, same Tuesday task). This folder adds a
second, separate service: a website where anyone signs in with Yahoo or enters an ESPN league, gets a link, and a fresh
edition prints for their league every Tuesday.

```
 League member ──► Cloudflare Worker (multi/worker)  ── D1: accounts, leagues, votes, bets
   (browser)        sign-up, Yahoo OAuth, ESPN setup  ── R2: printed papers
                    commissioner settings, papers,
                    league office (Rule Changes/Betting)
                          │ starts ▲ uploads
                          ▼        │
                 GitHub Actions: fantasizer-leagues.yml  → multi/run_all.py → multi/build_league.py
                 (fetches ESPN/Yahoo + player data,        (the same render.py, facts.py, players.py …
                  prints each league's paper)                as the Men Fantasizing paper)
```

## What other leagues get

- **Three tabs by default**: This Week's Paper, League & Teams, Player Stats. Same design, same sections.
- **Rule Changes and Betting are off** until the league's commissioner turns them on in Settings. Only the commissioner
  can open Settings: on Yahoo, Yahoo says who the commissioner is; on ESPN, the commissioner proves it by entering their
  espn_s2/SWID cookies (ESPN marks league managers). Passed rule changes are never applied automatically; the commissioner
  sets them in ESPN/Yahoo. Betting alone keeps a slim "Your Team" sign-in tab (betting needs a team sign-in).
- **Words are written automatically** from the stats (multi/autocopy.py): headlines, recaps, Police Blotter, Missing
  Persons, Manager of the Week. No AI, no cost. Different every week, same every rebuild.
- **The league's own colors**: the commissioner picks an accent; the Lions blue and the "313" footer are Men Fantasizing only.
- **Not included for other leagues**: Optimal Lineup (your private tool), auto-applying rules to ESPN, league lore and
  announcements, the home-screen install page.

## One-time setup (about 30 minutes)

You need a free Cloudflare account and a free Yahoo developer account. Commands run in `multi/worker` with Node 18+.

1. **Cloudflare storage**
   ```
   cd multi/worker && npm install
   npx wrangler login
   npx wrangler d1 create fantasizer          # copy the database_id into wrangler.toml
   npx wrangler r2 bucket create fantasizer-papers
   npx wrangler d1 execute fantasizer --remote --file schema.sql
   npx wrangler deploy                         # prints your URL, e.g. https://fantasizer.<you>.workers.dev
   ```
   Put that URL in `wrangler.toml` as `SITE_URL` (no trailing slash) and deploy again.

2. **Yahoo app** at https://developer.yahoo.com/apps/create/
   - Application type: Web Application. Redirect URI: `SITE_URL/auth/yahoo/callback`.
   - API permissions: **Fantasy Sports → Read**.
   - Copy the Client ID and Client Secret.

3. **GitHub token** so the site can start the printer: a fine-grained personal access token for
   `rcf4765/daily-fantasizer` with **Actions: Read and write** (nothing else).

4. **Secrets** (each command asks for the value):
   ```
   npx wrangler secret put SESSION_SECRET       # any long random string
   npx wrangler secret put ENC_KEY              # another long random string (encrypts ESPN cookies, Yahoo tokens)
   npx wrangler secret put BUILD_TOKEN          # a third long random string
   npx wrangler secret put GITHUB_TOKEN         # from step 3
   npx wrangler secret put YAHOO_CLIENT_ID      # from step 2
   npx wrangler secret put YAHOO_CLIENT_SECRET  # from step 2
   ```
   Random strings: `openssl rand -hex 32`.

5. **GitHub repo settings** (Settings → Secrets and variables → Actions):
   - Secret `FZ_BUILD_TOKEN` = the same value as BUILD_TOKEN.
   - Variable `FZ_SITE_URL` = your SITE_URL.

6. **Merge the `multi-league` branch into `main`.** GitHub only lets the site start workflows that exist on `main`.
   The Men Fantasizing pipeline is unchanged by the merge (its week 7 render is byte-identical apart from the betting
   board's timestamp; MANIFEST.txt is updated for the eight parameterized files).

7. Open SITE_URL, set up a test league, and watch the run under the repo's Actions tab.

## How a league is printed

`run_all.py` asks the site for the leagues (with decrypted cookies / a fresh Yahoo token, masked in the logs), fetches the
shared player data once (nflverse, FantasyPros, ESPN's player pool), then for each league: restores its saved data,
`build_league.py` fetches the new week(s), runs facts.py → autocopy.py → render.py → postprocess.py, and uploads the
edition, the next week's betting board and the data back to the site. One league failing never stops the others; the
error shows on that league's page. The site's own cron starts a full run Tuesday and Wednesday at 10:17 UTC.

## Limits worth knowing

- **ESPN**: there is no ESPN sign-in for other sites. Public leagues need only the league ID. Private leagues need the
  espn_s2 and SWID cookies, which work like a password; they're stored encrypted and only used to read the league. They
  usually last about a year; when they expire the league's page says so and the commissioner re-enters them.
- **Yahoo**: read-only OAuth. Yahoo has no weekly projections in its API, so the paper uses FantasyPros' consensus
  projection for QB/RB/WR/TE (kickers and defenses are left out of the "beat / missed projection" stories), there's no
  trading block, and Player Stats points are rescored with the league's own stat modifiers.
- **Lineups**: Roster Radar, Matchup of the Week and the Matchmaker follow each league's real starting lineup (superflex,
  3 WR, no kicker…). Optimal Lineup is not offered.
- **Cost**: Cloudflare and GitHub free tiers cover a few dozen leagues. Each league adds about a minute to the Tuesday run.

## Tests

- `node --no-warnings multi/worker/test/run.mjs`: the whole site against fake Yahoo/ESPN/GitHub (sign-up, commissioner
  checks, encrypted storage, build API, league office votes and bets). No Cloudflare account needed.
- `python3 multi/platforms/test_yahoo.py`: the Yahoo adapter against a fixture league (ties, trades, lineup slots).
- A push to `multi-league` runs the workflow's self-test: the Men Fantasizing league printed through the generic path
  from real ESPN data, saved as a workflow artifact.
