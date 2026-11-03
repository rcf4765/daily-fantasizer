// A stand-in for the parts of GitHub's API the site uses: the contents API on the private data repo (read, write with
// version check, delete, folder listing, raw bytes) and workflow starts. Files live in a Map; tests read them directly.
import { createHash } from 'node:crypto';
export function fakeGitHub(repo = 'me/data') {
  const files = new Map();   // path → Buffer
  const sha = (b) => createHash('sha1').update(b).digest('hex');
  const starts = [];         // { workflow, inputs }
  const base = `https://api.github.com/repos/${repo}/contents/`;
  async function handle(url, init = {}) {
    if (url.includes('/actions/workflows/') && url.endsWith('/dispatches')) {
      starts.push({ workflow: url.split('/actions/workflows/')[1].split('/')[0], inputs: JSON.parse(init.body).inputs });
      return new Response(null, { status: 204 });
    }
    if (!url.startsWith(base)) return null;
    const p = decodeURIComponent(url.slice(base.length).split('?')[0]);
    const method = init.method || 'GET', accept = (init.headers && (init.headers.Accept || init.headers.accept)) || '';
    if (method === 'GET') {
      if (files.has(p)) {
        const b = files.get(p);
        if (accept.includes('raw')) return new Response(b, { status: 200 });
        return Response.json({ path: p, sha: sha(b), content: b.toString('base64') });
      }
      const kids = [...files.keys()].filter((k) => k.startsWith(p + '/'));
      if (kids.length) {
        const names = [...new Set(kids.map((k) => k.slice(p.length + 1).split('/')[0]))];
        return Response.json(names.map((n) => ({ name: n, sha: files.has(`${p}/${n}`) ? sha(files.get(`${p}/${n}`)) : 'dir' })));
      }
      return new Response('{"message":"Not Found"}', { status: 404 });
    }
    const b = JSON.parse(init.body);
    if (method === 'PUT') {
      if (files.has(p) && b.sha !== sha(files.get(p))) return new Response('{"message":"conflict"}', { status: 409 });
      if (!files.has(p) && b.sha) return new Response('{"message":"conflict"}', { status: 409 });
      const buf = Buffer.from(b.content, 'base64'); files.set(p, buf);
      return Response.json({ content: { sha: sha(buf) } }, { status: 201 });
    }
    if (method === 'DELETE') {
      if (!files.has(p)) return new Response('{}', { status: 404 });
      if (b.sha !== sha(files.get(p))) return new Response('{"message":"conflict"}', { status: 409 });
      files.delete(p); return Response.json({});
    }
    return new Response('{}', { status: 405 });
  }
  return {
    files, starts, handle,
    json: (p) => (files.has(p) ? JSON.parse(files.get(p).toString()) : null),
    write: (p, text) => files.set(p, Buffer.from(text)),
    slugOf: (id, platform = 'espn') => { const ix = files.has('index/leagues.json') ? JSON.parse(files.get('index/leagues.json')) : {}; return Object.entries(ix).find(([k]) => k.startsWith(`${platform}:${id}:`))?.[1] || null; },
    dump: () => [...files.entries()].filter(([k]) => !k.startsWith('papers/')).map(([k, v]) => k + '\n' + v.toString()).join('\n'),
  };
}
