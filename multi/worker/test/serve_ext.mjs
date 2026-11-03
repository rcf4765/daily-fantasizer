// Local site for the extension end-to-end test: the Worker on http://127.0.0.1:8787 with ESPN and GitHub faked.
// One ESPN account ({CCCC…}) is in two football leagues (4001 as commissioner, 4002).
import http from 'node:http';
import worker from '../src/index.js';
import { fakeGitHub } from './fake_github.mjs';
const gh = fakeGitHub('me/data');
const env = { DATA_REPO: 'me/data',
  SITE_URL: 'http://127.0.0.1:8787', SESSION_SECRET: 'x'.repeat(32), ENC_KEY: 'y'.repeat(32), BUILD_TOKEN: 'build-tok', GITHUB_TOKEN: 'gh' };
const ME = '{CCCCCCCC-1111-2222-3333-444444444444}';
const realFetch = globalThis.fetch;
globalThis.fetch = async (url, init = {}) => {
  url = String(url);
  if (url.includes('api.github.com')) return (await gh.handle(url, init)) || new Response(null, { status: 204 });
  const ck = init.headers?.Cookie || '';
  if (url.includes('fan.api.espn.com')) {
    if (!ck.includes('espn_s2=')) return new Response('no', { status: 401 });
    return Response.json({ preferences: [4001, 4002].map((g) => ({ metaData: { entry: { abbrev: 'FFL', gameId: 1, seasonId: 2026, groups: [{ groupId: g }] } } })) });
  }
  if (url.includes('lm-api-reads.fantasy.espn.com')) {
    const id = url.match(/leagues\/(\d+)/)[1];
    const names = { 4001: 'Office League', 4002: 'Family League', 4003: 'Old College League' };
    if (!names[id]) return new Response('no', { status: 404 });
    return Response.json({ settings: { name: names[id] }, teams: Array.from({ length: 10 }, (_, i) => ({ id: i + 1, name: i === 2 ? 'Taco Tuesday' : 'T' + i, owners: i === 2 ? [ME] : ['{X}'] })),
      members: [{ id: ME, isLeagueManager: id === '4001' }, { id: '{X}' }] });
  }
  return realFetch(url, init);
};
http.createServer(async (req, res) => {
  const chunks = []; for await (const c of req) chunks.push(c);
  const r = await worker.fetch(new Request('http://127.0.0.1:8787' + req.url, { method: req.method, headers: req.headers, body: chunks.length ? Buffer.concat(chunks) : undefined }), env, { waitUntil() {} });
  console.log(req.method, req.url.replace(/t=\w+/, 't=…'), r.status);
  res.writeHead(r.status, Object.fromEntries(r.headers)); res.end(Buffer.from(await r.arrayBuffer()));
}).listen(8787, '127.0.0.1', () => console.log('listening'));
