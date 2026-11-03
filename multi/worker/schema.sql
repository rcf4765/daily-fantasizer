-- The Daily Fantasizer for any league: D1 schema. Apply with: npx wrangler d1 execute fantasizer --remote --file schema.sql
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,               -- yahoo:<guid> or espn:<SWID>
  platform TEXT NOT NULL,
  yahoo_refresh TEXT,                -- AES-GCM sealed refresh token (read-only fantasy scope)
  espn_s2 TEXT, swid TEXT,           -- ESPN accounts linked with the extension: sealed cookies (one account, many leagues)
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS leagues (
  slug TEXT PRIMARY KEY,             -- random, the paper lives at /l/<slug>/
  platform TEXT NOT NULL,            -- espn | yahoo
  league_id TEXT NOT NULL,           -- ESPN league id, or Yahoo league key (461.l.12345)
  season INTEGER NOT NULL,
  name TEXT NOT NULL,
  teams INTEGER NOT NULL,
  commissioner_uid TEXT,             -- only this person can open Settings
  token_uid TEXT,                    -- Yahoo: whose sign-in prints the paper
  espn_s2 TEXT, swid TEXT,           -- ESPN private leagues: sealed cookies
  feat_rules INTEGER NOT NULL DEFAULT 0,
  feat_bets INTEGER NOT NULL DEFAULT 0,
  accent TEXT NOT NULL DEFAULT '#33658a',
  comm_code_hash TEXT,               -- sha256 of the commissioner code for the paper's Commissioner panel
  status TEXT NOT NULL DEFAULT 'queued', status_msg TEXT,
  last_week INTEGER, last_built_at TEXT, last_dispatch_at TEXT,
  created_by TEXT, created_at TEXT NOT NULL,
  UNIQUE (platform, league_id, season)
);
CREATE TABLE IF NOT EXISTS members (uid TEXT NOT NULL, slug TEXT NOT NULL, is_comm INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (uid, slug));
-- league office (same data as the Men Fantasizing Google Sheet tabs)
CREATE TABLE IF NOT EXISTS claims (slug TEXT NOT NULL, team INTEGER NOT NULL, key_hash TEXT NOT NULL, claimed_at TEXT NOT NULL, PRIMARY KEY (slug, team));
CREATE TABLE IF NOT EXISTS proposals (slug TEXT NOT NULL, seq INTEGER NOT NULL, id TEXT NOT NULL, team INTEGER NOT NULL, category TEXT, title TEXT, details TEXT,
  created_at TEXT, deadline TEXT, status TEXT, closed_at TEXT, preset TEXT, PRIMARY KEY (slug, id));
CREATE TABLE IF NOT EXISTS votes (slug TEXT NOT NULL, proposal TEXT NOT NULL, team INTEGER NOT NULL, choice TEXT NOT NULL, at TEXT NOT NULL, PRIMARY KEY (slug, proposal, team));
CREATE TABLE IF NOT EXISTS bets (slug TEXT NOT NULL, seq INTEGER NOT NULL, id TEXT NOT NULL, week INTEGER, team INTEGER, stake REAL, legs TEXT, dec REAL, win REAL,
  placed_at TEXT, status TEXT, PRIMARY KEY (slug, id));
CREATE TABLE IF NOT EXISTS office_log (slug TEXT NOT NULL, at TEXT NOT NULL, action TEXT, team INTEGER, detail TEXT);
-- ESPN links from the browser extension: a short-lived, single-use token between "signed in on ESPN" and "back on the site"
CREATE TABLE IF NOT EXISTS espn_links (token_hash TEXT PRIMARY KEY, uid TEXT NOT NULL, leagues TEXT, created_at TEXT NOT NULL,
  synced INTEGER NOT NULL DEFAULT 0, done_hash TEXT, done_used INTEGER NOT NULL DEFAULT 0);
-- ESPN sign-in on the server: a sign-in waiting for the one-time code ESPN emailed (browser kept open up to 10 minutes)
CREATE TABLE IF NOT EXISTS espn_logins (token_hash TEXT PRIMARY KEY, session_id TEXT NOT NULL, created_at TEXT NOT NULL, tries INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS login_attempts (ip TEXT NOT NULL, at TEXT NOT NULL);
-- what each sign-in did, for fixing it when ESPN changes its login page (step names only: no emails, passwords or codes)
CREATE TABLE IF NOT EXISTS login_traces (at TEXT NOT NULL, ok INTEGER NOT NULL, steps TEXT);
