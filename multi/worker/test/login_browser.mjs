// Runs the real ESPN sign-in code (src/espn_login.js) in a real Chrome against a mock of ESPN's login: the page
// embeds Disney's OneID form in an iframe; email → Continue → password → Log In; sometimes a 6-box code.
// The browser comes from the Playwright bundled with Python Playwright, behind a tiny puppeteer-style shim.
// node --no-warnings test/login_browser.mjs
import http from 'node:http';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { espnLoginStart, espnLoginCode } from '../src/espn_login.js';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PW_PKG || '/usr/local/lib/python3.13/site-packages/playwright/driver/package');

// ---- mock ESPN (main site on :9101, Disney's form on :9102) ----
const ONEID = (step, msg = '') => `<!doctype html><body><iframe id="arkose-preload" src="about:blank" style="position:absolute;width:1px;height:1px;opacity:0"></iframe><form method="post" action="/oneid/${step}">
${msg ? `<div role="alert">${msg}</div>` : ''}
${step === 'email' ? '<input type="email" id="InputIdentityFlowValue" name="email"><button id="BtnSubmit" type="submit">Continue</button>' : ''}
${step === 'password' ? '<input type="password" id="InputPassword" name="password"><button id="BtnSubmit" type="submit">Log In</button>' : ''}
${step === 'code' ? [0,1,2,3,4,5].map((i) => `<input inputmode="numeric" maxlength="1" name="c${i}" autocomplete="one-time-code">`).join('') + '<button id="BtnSubmit" type="submit">Continue</button>' : ''}
${step === 'bot' ? '<iframe src="about:blank" id="arkose"></iframe>' : ''}
${step === 'done' ? '<script>parent.postMessage("ok","*")</script>Signed in' : ''}
</form></body>`;
let who = '';
const body = async (req) => { let b = ''; for await (const c of req) b += c; return new URLSearchParams(b); };
http.createServer(async (req, res) => {
  const u = req.url;
  if (u.startsWith('/oneid/')) {
    const step = u.split('/')[2], f = req.method === 'POST' ? await body(req) : null;
    let next = 'email', msg = '', setCk = false;
    if (step === 'email' && f) { who = f.get('email'); next = who.startsWith('bot') ? 'bot' : 'password'; }
    else if (step === 'password' && f) {
      if (f.get('password') !== 'right') { next = 'password'; msg = 'The credentials you entered are incorrect.'; }
      else if (who.startsWith('otp')) next = 'code'; else { next = 'done'; setCk = true; }
    } else if (step === 'code' && f) {
      const code = [0,1,2,3,4,5].map((i) => f.get('c' + i)).join('');
      if (code === '246810') { next = 'done'; setCk = true; } else { next = 'code'; msg = 'That code is incorrect.'; }
    }
    // the real flow sets ESPN's cookies on the espn site; here the parent page sets them when told
    res.writeHead(200, { 'Content-Type': 'text/html' });
    return res.end(ONEID(next, msg).replace('parent.postMessage("ok","*")', setCk ? 'parent.postMessage("ok","*")' : ''));
  }
}).listen(9102, '127.0.0.1');
http.createServer((req, res) => {
  if (req.url === '/set') { res.writeHead(204, { 'Set-Cookie': ['espn_s2=AEBfake%2Bs2value; Path=/', 'SWID={ABCDEF12-3456-7890-ABCD-EF1234567890}; Path=/'] }); return res.end(); }
  if (req.url.startsWith('/login/responder/')) { res.writeHead(200, { 'Content-Type': 'text/html' }); return res.end('<!doctype html><body></body>'); }
  res.writeHead(200, { 'Content-Type': 'text/html' });
  // like ESPN (2026-11-11): a 0x0 helper frame on ESPN's own site whose address looks like the login loads first, and
  // Disney's real form arrives a moment later
  res.end(`<!doctype html><title>ESPN</title><body><h1>ESPN mock</h1>
<iframe name="disneyid-secure-responder" src="/login/responder/?clientId=ESPN-ONESITE.WEB-PROD&oneid=1" width="0" height="0"></iframe>
<div id="slot"></div>
<script>setTimeout(function(){document.getElementById('slot').innerHTML='<iframe id="oneid-iframe" src="http://127.0.0.1:9102/oneid/email" width="400" height="400"></iframe>'},${process.env.FORM_DELAY || 1500});
addEventListener('message',function(e){if(e.data==='ok')fetch('/set')})</script></body>`);
}).listen(9101, '127.0.0.1');

// ---- puppeteer-style shim over Playwright (only what espn_login.js uses) ----
const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
const sessions = new Map();
const wrapEl = (h) => ({ click: (o) => h.click(o && o.clickCount === 3 ? { clickCount: 3 } : {}), type: (t, o) => h.type(t, { delay: (o && o.delay) || 0 }),
  press: (k) => h.press(k), isIntersectingViewport: async () => h.isVisible() });
const wrapFrame = (f) => ({ url: () => f.url(), $: async (s) => { const h = await f.$(s); return h && wrapEl(h); }, $$: async (s) => (await f.$$(s)).map(wrapEl),
  waitForSelector: async (s, o) => wrapEl(await f.waitForSelector(s, { state: 'visible', timeout: o.timeout })), $$eval: (s, fn) => f.$$eval(s, fn) });
const wrapPage = (p) => ({ setUserAgent: async () => {}, setViewport: (v) => p.setViewportSize(v), goto: (u, o) => p.goto(u, { waitUntil: 'networkidle', timeout: o.timeout }),
  cookies: async () => p.context().cookies(), frames: () => p.frames().map(wrapFrame), mainFrame: () => wrapFrame(p.mainFrame()), $: (s) => p.$(s) });
const lib = {
  launch: async () => { const ctx = await browser.newContext(); const id = 'S' + sessions.size; sessions.set(id, ctx);
    return { newPage: async () => wrapPage(await ctx.newPage()), sessionId: () => id, disconnect: async () => {}, close: () => ctx.close(), pages: async () => ctx.pages().map(wrapPage) }; },
  connect: async (b, id) => { const ctx = sessions.get(id); return { pages: async () => ctx.pages().map(wrapPage), disconnect: async () => {}, close: () => ctx.close() }; },
};
const env = { BROWSER: {}, __browserLib: lib, ESPN_LOGIN_URL: 'http://127.0.0.1:9101/login' };
const ok = (n) => console.log('  ✓', n);

console.log('ESPN sign-in script in a real browser (mock ESPN)');
let r = await espnLoginStart(env, 'fan@example.com', 'right');
assert.equal(r.status, 'ok', JSON.stringify(r)); assert.equal(r.s2, 'AEBfake+s2value');
assert.ok(!r.trace.join(' ').includes('bot check')); ok('Disney’s invisible background check is ignored (was a false alarm)'); assert.match(r.swid, /^\{ABCDEF12/); ok('email → continue → password → signed in, session captured');
assert.ok(!r.trace.join(' ').includes('fan@example.com') && !r.trace.join(' ').includes('right')); ok('trace holds no email or password');
console.log('    trace:', r.trace.join(' | '));
r = await espnLoginStart(env, 'fan@example.com', 'wrong');
assert.equal(r.status, 'error'); assert.match(r.error, /didn’t accept/); ok('wrong password → clear message');
r = await espnLoginStart(env, 'otp@example.com', 'right');
assert.equal(r.status, 'code'); ok('ESPN asks for a code → browser kept for the code step');
const sid = r.sessionId;
r = await espnLoginCode(env, sid, '111111'); assert.equal(r.status, 'code'); ok('wrong code → asked again');
r = await espnLoginCode(env, sid, '246810'); assert.equal(r.status, 'ok', JSON.stringify(r)); ok('six one-digit boxes filled → signed in');
r = await espnLoginStart(env, 'bot@example.com', 'right');
assert.equal(r.status, 'error'); assert.match(r.error, /security check/); ok('bot check → "try again in a few minutes"');
await browser.close();
console.log('\nall passed'); process.exit(0);
