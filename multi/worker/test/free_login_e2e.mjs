// End to end, free plan: a user logs in on the site → the site queues an encrypted job and "dispatches" the GitHub
// workflow (here: runs multi/login_runner/run.mjs locally) → the job signs in on a mock ESPN with a real browser →
// the site sets up every league on the account → the user lands on My leagues. Also: ESPN's emailed code, a wrong
// code, a wrong password, and a dispatch naming a look-alike site.
// node --no-warnings test/free_login_e2e.mjs
import http from 'node:http';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';

import { fakeGitHub } from './fake_github.mjs';
import { createRequire } from 'node:module';
import worker from '../src/index.js';
const require = createRequire(import.meta.url);
const PW = process.env.PW_PKG || '/usr/local/lib/python3.13/site-packages/playwright/driver/package';
const { chromium } = require(PW);
const ME = '{CCCCCCCC-1111-2222-3333-444444444444}';
const ok = (n) => console.log('  ✓', n);

// ---- mock ESPN login (as in login_browser.mjs) ----
const FORM = (step, msg = '') => `<!doctype html><body><form method="post" action="/oneid/${step}">${msg ? `<div role="alert">${msg}</div>` : ''}
${step === 'email' ? '<input type="email" id="InputIdentityFlowValue" name="email"><button id="BtnSubmit" type="submit">Continue</button>' : ''}
${step === 'password' ? '<input type="password" id="InputPassword" name="password"><button id="BtnSubmit" type="submit">Log In</button>' : ''}
${step === 'code' ? '<input name="c" autocomplete="one-time-code" inputmode="numeric"><button id="BtnSubmit" type="submit">Continue</button>' : ''}
${step === 'done' ? '<script>parent.postMessage("ok","*")</script>' : ''}</form></body>`;
let who = '';
const body = async (req) => { let b = ''; for await (const c of req) b += c; return new URLSearchParams(b); };
http.createServer(async (req, res) => {
  const step = req.url.split('/')[2], f = req.method === 'POST' ? await body(req) : null;
  let next = 'email', msg = '';
  if (step === 'email' && f) { who = f.get('email'); next = 'password'; }
  else if (step === 'password' && f) next = f.get('password') !== 'right' ? (msg = 'The credentials you entered are incorrect.', 'password') : who.startsWith('otp') ? 'code' : 'done';
  else if (step === 'code' && f) next = f.get('c') === '246810' ? 'done' : (msg = 'That code is incorrect.', 'code');
  res.writeHead(200, { 'Content-Type': 'text/html' }); res.end(FORM(next, msg));
}).listen(9102, '127.0.0.1');
http.createServer((req, res) => {
  if (req.url === '/set') { res.writeHead(204, { 'Set-Cookie': ['espn_s2=AEBfake%2Bs2value' + 'x'.repeat(50) + '; Path=/', `SWID=${ME}; Path=/`] }); return res.end(); }
  res.writeHead(200, { 'Content-Type': 'text/html' });
  res.end(`<!doctype html><title>ESPN</title><iframe src="http://127.0.0.1:9102/oneid/email" width="400" height="400"></iframe><script>addEventListener('message',function(e){if(e.data==='ok')fetch('/set')})</script>`);
}).listen(9101, '127.0.0.1');

// ---- the site, free plan: no BROWSER binding, LOGIN_KEY set, data in the (fake) GitHub data repo ----
const LOGIN_KEY = 'login-key-' + 'z'.repeat(40);
const gh = fakeGitHub('me/data');
const SITE = 'http://127.0.0.1:8787';
const env = { DATA_REPO: 'me/data', SITE_URL: SITE, SESSION_SECRET: 'x'.repeat(32), ENC_KEY: 'y'.repeat(32), BUILD_TOKEN: 'build-tok', GITHUB_TOKEN: 'gh', LOGIN_KEY };
const jobs = [];
const realFetch = globalThis.fetch;
globalThis.fetch = async (url, init = {}) => {
  url = String(url);
  if (url.includes('espn-login.yml/dispatches')) {   // "GitHub" (the data repo's workflow) runs the real job script
    const { inputs } = JSON.parse(init.body);
    await gh.handle(url, init);
    const p = spawn(process.execPath, ['--no-warnings', new URL('../../login_runner/run.mjs', import.meta.url).pathname], {
      env: { ...process.env, SITE: inputs.site, JOB: inputs.job, LOGIN: inputs.login, SIG: process.env.TAMPER ? 'bad' : inputs.sig, BUILD_TOKEN: 'build-tok', LOGIN_KEY,
        FZ_LOCAL_TEST: '1', PW_PKG: PW, CHROME_PATH: '/usr/bin/google-chrome', ESPN_LOGIN_URL: 'http://127.0.0.1:9101/login' }, stdio: ['ignore', 'pipe', 'pipe'] });
    let out = ''; p.stdout.on('data', (d) => (out += d)); p.stderr.on('data', (d) => (out += d));
    jobs.push(new Promise((res) => p.on('exit', (c) => res({ code: c, out }))));
    return new Response(null, { status: 204 });
  }
  if (url.includes('api.github.com')) return (await gh.handle(url, init)) || new Response(null, { status: 204 });
  const ck = init.headers?.Cookie || '';
  if (url.includes('fan.api.espn.com')) {
    if (!ck.includes('espn_s2=AEB')) return new Response('no', { status: 401 });
    return Response.json({ preferences: [4001, 4002].map((g) => ({ metaData: { entry: { abbrev: 'FFL', gameId: 1, seasonId: 2026, groups: [{ groupId: g }] } } })) });
  }
  if (url.includes('lm-api-reads.fantasy.espn.com')) {
    const id = url.match(/leagues\/(\d+)/)[1], names = { 4001: 'Office League', 4002: 'Family League' };
    return Response.json({ settings: { name: names[id] }, teams: Array.from({ length: 10 }, (_, i) => ({ id: i + 1, name: 'T' + i, owners: i === 2 ? [ME] : ['{X}'] })),
      members: [{ id: ME, isLeagueManager: id === '4001' }, { id: '{X}' }] });
  }
  return realFetch(url, init);
};
http.createServer(async (req, res) => {
  const chunks = []; for await (const c of req) chunks.push(c);
  const r = await worker.fetch(new Request(SITE + req.url, { method: req.method, headers: req.headers, body: chunks.length ? Buffer.concat(chunks) : undefined }), env, { waitUntil() {} });
  const h = new Headers(r.headers); const sc = r.headers.getSetCookie?.() || [];
  res.writeHead(r.status, { ...Object.fromEntries([...h].filter(([k]) => k !== 'set-cookie')), ...(sc.length ? { 'set-cookie': sc } : {}) });
  res.end(Buffer.from(await r.arrayBuffer()));
}).listen(8787, '127.0.0.1');

// ---- the user ----
const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
async function login(email, password) {
  const ctx = await browser.newContext({ viewport: { width: 400, height: 860 } });
  const pg = await ctx.newPage();
  await pg.route(/fonts\.(googleapis|gstatic)\.com/, (r) => r.abort());
  await pg.goto(SITE + '/login');
  await pg.fill('input[name=email]', email); await pg.fill('input[name=password]', password);
  await pg.click('button[type=submit]');
  return { ctx, pg };
}
const until = async (pg, fn, ms = 60000) => { const end = Date.now() + ms; while (Date.now() < end) { try { if (await fn()) return true; } catch (e) { /* page changing */ } await pg.waitForTimeout(500); } return false; };

console.log('Free-plan ESPN sign-in, end to end');
{
  const { ctx, pg } = await login('fan@example.com', 'right');
  assert.match(await pg.textContent('body'), /about a minute/); ok('waiting page shown while the GitHub job signs in');
  assert.ok(!gh.dump().includes('right') && !gh.dump().includes('fan@example.com')); ok('the data repo never gets the password or email (job file holds progress only)');
  const reached = await until(pg, async () => pg.url().includes('/mine'));
  if (!reached) { const j0 = await jobs[0]; console.log('URL', pg.url(), '\nJOB', j0.code, j0.out); }
  assert.ok(reached, 'never reached My leagues'); ok('job signed in → user lands on My leagues by itself');
  const t = await pg.textContent('body');
  assert.ok(t.includes('Office League') && t.includes('Family League') && /2 papers set up/.test(t)); ok('both leagues on the account set up');
  assert.ok(gh.json(`users/espn_${ME.replace(/[{}]/g, '')}.json`).espn_s2); ok('ESPN session saved (encrypted) on the account in the data repo');
  assert.ok(!gh.dump().includes('AEBfake')); ok('ESPN session is never stored readable');
  const j = await jobs.shift(); assert.equal(j.code, 0, j.out); assert.ok(!j.out.includes('right')); ok('job log has no password');
  await ctx.close();
}
{
  const { ctx, pg } = await login('fan@example.com', 'wrong');
  assert.ok(await until(pg, async () => /didn’t accept that email and password/.test(await pg.textContent('body')))); ok('wrong password → back to the login with a clear message');
  await jobs.shift(); await ctx.close();
}
{
  const { ctx, pg } = await login('otp@example.com', 'right');
  assert.ok(await until(pg, async () => (await pg.$('input[name=code]')) !== null)); ok('ESPN emails a code → the code box appears');
  await pg.fill('input[name=code]', '111111'); await pg.click('button[type=submit]');
  assert.ok(await until(pg, async () => /code didn’t work/.test(await pg.textContent('body')))); ok('wrong code → asked again');
  await pg.fill('input[name=code]', '246810'); await pg.click('button[type=submit]');
  assert.ok(await until(pg, async () => pg.url().includes('/mine'))); ok('right code → My leagues');
  const j = await jobs.shift(); assert.equal(j.code, 0, j.out); assert.ok(!j.out.includes('246810')); ok('job log has no code');
  await ctx.close();
}
{
  process.env.TAMPER = '1';
  const { ctx } = await login('fan@example.com', 'right');
  const j = await jobs.shift(); assert.equal(j.code, 2); assert.match(j.out, /signature does not match/); ok('a dispatch naming a look-alike site is refused before anything is sent');
  delete process.env.TAMPER; await ctx.close();
}
await browser.close();
console.log('\nall passed'); process.exit(0);
