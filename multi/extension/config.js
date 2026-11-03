// The only sites this extension will link ESPN leagues to. Put your SITE_URL here (from multi/worker/wrangler.toml),
// keep the 127.0.0.1 line for local testing, then reload the extension.
export const SITES = [
  'https://fantasizer.YOUR-SUBDOMAIN.workers.dev',
  'http://127.0.0.1:8787',
];
// The ESPN page the sync opens. The extension's panel appears on it; ESPN's own Log In button handles the sign-in.
export const ESPN_START = 'https://fantasy.espn.com/football/';
