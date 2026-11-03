// The site's database is a private GitHub repo (DATA_REPO, e.g. rcf4765/daily-fantasizer-data): plain JSON files,
// read and written through GitHub's contents API with the site's token. Nothing is kept on the host, so the site can
// move to any host that runs JavaScript with fetch(); only this file talks to GitHub.
// Writes carry the file's last-seen version (sha); a write that lost a race is retried on fresh data (update()).
const GH = 'https://api.github.com';
const enc = new TextEncoder(), dec = new TextDecoder();
const b64enc = (s) => { const b = enc.encode(s); let o = ''; for (let i = 0; i < b.length; i += 0x8000) o += String.fromCharCode(...b.subarray(i, i + 0x8000)); return btoa(o); };
const b64dec = (s) => dec.decode(Uint8Array.from(atob(String(s).replace(/\s+/g, '')), (c) => c.charCodeAt(0)));

export class StoreError extends Error {}

export function makeStore(env) {
  const repo = env.DATA_REPO, token = env.DATA_TOKEN || env.GITHUB_TOKEN, branch = env.DATA_BRANCH || 'main';
  if (!repo || !token) throw new StoreError('The site has no data repo set up (DATA_REPO and its token).');
  const H = { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json', 'User-Agent': 'daily-fantasizer-site',
    'X-GitHub-Api-Version': '2022-11-28', 'Cache-Control': 'no-cache' };
  const url = (p) => `${GH}/repos/${repo}/contents/${p.split('/').map(encodeURIComponent).join('/')}`;
  const memo = new Map();   // per request: each file is read once

  async function get(p) {
    if (memo.has(p)) return memo.get(p);
    const r = await fetch(`${url(p)}?ref=${branch}`, { headers: H });
    if (r.status === 404) { memo.set(p, null); return null; }
    if (!r.ok) throw new StoreError(`GitHub answered ${r.status} reading ${p}`);
    const j = await r.json();
    const v = { data: JSON.parse(b64dec(j.content)), sha: j.sha };
    memo.set(p, v);
    return v;
  }
  async function put(p, data, sha, message) {
    const r = await fetch(url(p), { method: 'PUT', headers: H,
      body: JSON.stringify({ message: message || `site: ${p}`, branch, content: b64enc(JSON.stringify(data, null, 1) + '\n'), ...(sha ? { sha } : {}) }) });
    if (r.status === 409 || r.status === 422) { memo.delete(p); const e = new StoreError('conflict'); e.conflict = true; throw e; }
    if (!r.ok) throw new StoreError(`GitHub answered ${r.status} writing ${p}`);
    const j = await r.json();
    memo.set(p, { data, sha: j.content.sha });
    return j.content.sha;
  }
  async function del(p, sha) {
    const r = await fetch(url(p), { method: 'DELETE', headers: H, body: JSON.stringify({ message: `site: remove ${p}`, branch, sha }) });
    if (r.status === 409 || r.status === 422) { memo.delete(p); const e = new StoreError('conflict'); e.conflict = true; throw e; }
    if (!r.ok && r.status !== 404) throw new StoreError(`GitHub answered ${r.status} removing ${p}`);
    memo.set(p, null);
  }
  /** Read-modify-write. fn(currentData|null) returns the new data, null to delete, or undefined for "no change". */
  async function update(p, fn, message) {
    for (let i = 0; i < 5; i++) {
      const cur = await get(p);
      const next = await fn(cur ? structuredClone(cur.data) : null);
      if (next === undefined) return cur ? cur.data : null;
      try {
        if (next === null) { if (cur) await del(p, cur.sha); return null; }
        await put(p, next, cur && cur.sha, message);
        return next;
      } catch (e) {
        if (!e.conflict) throw e;
        await new Promise((r) => setTimeout(r, 150 * (i + 1) + Math.random() * 200));
      }
    }
    throw new StoreError('The site is busy. Try again in a moment.');
  }
  async function list(dir) {
    const r = await fetch(`${url(dir)}?ref=${branch}`, { headers: H });
    if (r.status === 404) return [];
    if (!r.ok) throw new StoreError(`GitHub answered ${r.status} listing ${dir}`);
    const j = await r.json();
    return Array.isArray(j) ? j.map((x) => x.name) : [];
  }
  /** A file's bytes as a stream (papers are larger than the JSON route allows). null when missing. */
  async function raw(p) {
    const r = await fetch(`${url(p)}?ref=${branch}`, { headers: { ...H, Accept: 'application/vnd.github.raw' } });
    if (r.status === 404) return null;
    if (!r.ok) throw new StoreError(`GitHub answered ${r.status} reading ${p}`);
    return r;
  }
  /** A file's version id without reading it (papers can be too large for get()). */
  async function sha(p) {
    const dir = p.split('/').slice(0, -1).join('/'), name = p.split('/').pop();
    const r = await fetch(`${url(dir)}?ref=${branch}`, { headers: H });
    if (!r.ok) return null;
    const j = await r.json();
    return (Array.isArray(j) ? j.find((x) => x.name === name) : null)?.sha || null;
  }
  return { get, put, del, update, list, raw, sha };
}
