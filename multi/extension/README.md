# Daily Fantasizer: ESPN link (Chrome extension)

Links ESPN Fantasy leagues to The Daily Fantasizer the way FantasyPros' ESPN sync does: sign in on ESPN's own page,
tick your leagues in the panel the extension shows there, press Add leagues. See `multi/SETUP.md` → "ESPN: the Chrome
extension".

- `manifest.json` (Manifest V3; permissions: cookies, storage, tabs; reads only espn.com and the Daily Fantasizer site)
- `background.js`: opens the ESPN tab, waits for the sign-in, talks to the site's `/api/espn/*`
- `espn_panel.js`: the panel on fantasy.espn.com (closed shadow DOM)
- `content.js`: on the Daily Fantasizer site, relays the Link button to the extension; never sees cookies
- `config.js`: `SITES`, the only sites it will link to
- `pack.py`: zips it with your SITE_URL for the site's `/extension.zip`
