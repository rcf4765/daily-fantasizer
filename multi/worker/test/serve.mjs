// Serve the Worker on http://127.0.0.1:8787 with the same SQLite/in-memory shims as run.mjs (for the printer test).
import http from 'node:http';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import worker from '../src/index.js';
const sql = new DatabaseSync(':memory:');
sql.exec(readFileSync(new URL('../schema.sql', import.meta.url), 'utf8'));
const stmt = (q, a = []) => ({ bind: (...b) => stmt(q, b), first: async () => sql.prepare(q).get(...a) ?? null,
  all: async () => ({ results: sql.prepare(q).all(...a) }), run: async () => ({ meta: { changes: sql.prepare(q).run(...a).changes } }) });
const store = new Map();
const env = { DB: { prepare: (q) => stmt(q), batch: async (l) => Promise.all(l.map((s) => s.run())) },
  PAPERS: { put: async (k, b) => store.set(k, Buffer.from(await new Response(b).arrayBuffer())), get: async (k) => store.has(k) ? { body: store.get(k), text: async () => store.get(k).toString(), json: async () => JSON.parse(store.get(k)) } : null,
    delete: async (k) => store.delete(k), list: async ({ prefix }) => ({ objects: [...store.keys()].filter((k) => k.startsWith(prefix)).map((key) => ({ key })) }) },
  SITE_URL: 'http://127.0.0.1:8787', SESSION_SECRET: 'x'.repeat(32), ENC_KEY: 'y'.repeat(32), BUILD_TOKEN: 'build-tok' };
// seed: one ESPN league with both tabs on
sql.prepare(`INSERT INTO leagues (slug, platform, league_id, season, name, teams, commissioner_uid, feat_rules, feat_bets, accent, status, created_at)
  VALUES ('testleague1','espn','1196354715',2026,'Men Fantasizing',12,'espn:X',1,1,'#8a3b12','queued','2026-11-01')`).run();
http.createServer(async (req, res) => {
  const chunks = []; for await (const c of req) chunks.push(c);
  const r = await worker.fetch(new Request('http://127.0.0.1:8787' + req.url, { method: req.method, headers: req.headers, body: chunks.length ? Buffer.concat(chunks) : undefined }), env, { waitUntil() {} });
  res.writeHead(r.status, Object.fromEntries(r.headers)); res.end(Buffer.from(await r.arrayBuffer()));
}).listen(8787, () => console.log('listening'));
