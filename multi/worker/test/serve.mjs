// Serve the site on http://127.0.0.1:8787 with the data repo faked in memory, as run.mjs does (for the printer test).
import http from 'node:http';
import worker from '../src/index.js';
import { fakeGitHub } from './fake_github.mjs';
const gh = fakeGitHub('me/data');
const env = { DATA_REPO: 'me/data', GITHUB_TOKEN: 'gh',
  SITE_URL: 'http://127.0.0.1:8787', SESSION_SECRET: 'x'.repeat(32), ENC_KEY: 'y'.repeat(32), BUILD_TOKEN: 'build-tok' };
// seed: one ESPN league with both tabs on
gh.write('leagues/testleague1.json', JSON.stringify({ slug: 'testleague1', platform: 'espn', league_id: '1196354715', season: 2026, name: 'Men Fantasizing', teams: 12,
  commissioner_uid: 'espn:X', feat_rules: 1, feat_bets: 1, accent: '#8a3b12', status: 'queued', created_at: '2026-11-01' }));
gh.write('index/leagues.json', JSON.stringify({ 'espn:1196354715:2026': 'testleague1' }));
const realFetch = globalThis.fetch;
globalThis.fetch = async (url, init = {}) => (String(url).includes('api.github.com') ? (await gh.handle(String(url), init)) || new Response(null, { status: 204 }) : realFetch(url, init));
http.createServer(async (req, res) => {
  const chunks = []; for await (const c of req) chunks.push(c);
  const r = await worker.fetch(new Request('http://127.0.0.1:8787' + req.url, { method: req.method, headers: req.headers, body: chunks.length ? Buffer.concat(chunks) : undefined }), env, { waitUntil() {} });
  res.writeHead(r.status, Object.fromEntries(r.headers)); res.end(Buffer.from(await r.arrayBuffer()));
}).listen(8787, () => console.log('listening'));
