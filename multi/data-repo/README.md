# Daily Fantasizer data (private)

The website's database. Plain files, kept up to date by the website and by this repo's two workflows:

| Path | What |
|---|---|
| `leagues/<slug>.json` | one league: settings, status, encrypted ESPN sign-in |
| `index/leagues.json` | finds a league by platform, league id and season |
| `users/<id>.json` | one account: encrypted ESPN sign-in or Yahoo token |
| `members/<id>.json` | which leagues an account is in |
| `office/<slug>.json` | Rule Changes and Betting |
| `papers/<slug>/` | printed editions and each league's saved data |
| `jobs/`, `links/`, `limits/` | short-lived sign-in records (no passwords; they expire) |
| `traces.json` | the last 30 ESPN sign-in traces (step names only) |
| `site.json` | the website's address |

Encrypted fields can only be read with the keys derived from `FZ_MASTER_KEY`. Keep this repo private.
The workflows here are installed by the code repo's "Deploy the sign-up site" workflow; edit them there.
