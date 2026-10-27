# Rule Changes tab: league office setup

The **Rule Changes** tab on the league site lets managers propose scoring, rules or settings changes and vote on them. The site is static (GitHub Pages), so proposals and votes live in a Google Sheet owned by the commissioner, behind a small Apps Script web app (`proposals/Code.gs`). That script is the only thing that can record a vote, and it enforces the rules.

## How one vote per team is enforced

- **Claim once.** The first time a manager opens the tab, he taps his team. The server creates a random secret key and gives it to that phone (kept in the browser). Only a SHA-256 hash of the key is stored in the Sheet, so even the Sheet can't be used to vote. A claimed team can't be claimed again.
- **Every vote and proposal must carry the team's key.** A wrong or missing key is refused. Votes are stored as one row per team per proposal: voting again replaces the team's vote, never adds one.
- **Commissioner code** (kept out of the repo; only its hash is in `Code.gs`) unlocks the "Commissioner" panel at the bottom of the tab: reset a team's claim (wrong phone, new phone, cleared browser) or withdraw a proposal.
- **Results:** a proposal passes with `PASS` (7) yes votes out of 12 teams. It closes as soon as the result is locked in (7 yes, or 6 no) or after `WINDOW_DAYS` (7) days, whichever comes first. Each team may have at most 3 open proposals.
- **Moving phones:** "Use on another phone" shares a private sign-in link (`?team=N&key=…`). Anyone with that link can vote for the team, so it says so.
- Not prevented: the very first claim of a team is first come, first served. The "Who's signed in" list shows every claim and when, so a wrong claim is spotted and reset.

## One-time setup (about 2 minutes, on a computer)

1. Go to sheets.new (signed in with the commissioner's Google account). Name it **Daily Fantasizer League Office**.
2. **Extensions ▸ Apps Script.** Delete the sample code, paste all of `proposals/Code.gs`, save.
3. Pick `setup` in the function menu and click **Run**. Approve the permissions (it only touches this Sheet). Four tabs appear: Teams, Proposals, Votes, Log.
4. **Deploy ▸ New deployment ▸ Select type: Web app.** Execute as: **Me**. Who has access: **Anyone**. Deploy, and copy the **Web app URL** (ends in `/exec`).
5. Put that URL in `league.json` as `"proposals_api"` and republish (or give it to Claude). The tab goes live on the next render; until then it says "Voting opens soon".

Changing `Code.gs` later: paste the new version, then **Deploy ▸ Manage deployments ▸ edit ▸ Version: New version**. The URL stays the same.

## Changing the rules

`TEAMS`, `PASS`, `WINDOW_DAYS`, `MAX_OPEN_PER_TEAM` and `CATEGORIES` at the top of `Code.gs`. The tab reads them from the server, so the site needs no change. New commissioner code: put the SHA-256 of the new code (upper case) in `ADMIN_HASH` and redeploy.

## Suggestions and auto-apply (2026-10-26)

`PRESETS` in `Code.gs` lists the one-tap suggestions (same ids as `rules_presets.json`). When one passes, the "Apply rule changes" GitHub Action sets it in ESPN the next Tuesday and the League Rulebook on the tab shows whether it's live. After changing `Code.gs`, redeploy: open the Sheet ▸ Extensions ▸ Apps Script, paste, save, then **Deploy ▸ Manage deployments ▸ ✏️ edit ▸ Version: New version ▸ Deploy**. The web app URL stays the same.

## Betting (added 2026-10-27)

The same web app records bets for the Betting tab. After pasting the new `Code.gs`:
1. Save, then **Run ▸ setup** once and approve the new permission (it now fetches the week's board from the league website to check each bet's odds and lock time).
2. **Deploy ▸ Manage deployments ▸ ✏️ edit ▸ Version: New version ▸ Deploy.** The URL stays the same.
Bets land in a new **Bets** tab of the Sheet. `BETTING = false` at the top switches betting off; `MAX_STAKE`, `MAX_LEGS` and `MAX_WIN` set the limits (keep them equal to `bets.py`).
