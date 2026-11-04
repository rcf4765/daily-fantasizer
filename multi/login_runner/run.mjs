// The free ESPN sign-in, run by .github/workflows/espn-login.yml for one queued login (no Cloudflare browser needed).
//  1. gets the login inside its own start request (input LOGIN, encrypted with LOGIN_KEY; never stored or printed)
//  2. signs in on ESPN's real login page with the same code the paid plan uses (multi/worker/src/espn_login.js)
//  3. if ESPN emails a code, tells the site, waits up to 9 minutes for the user to type it, and tries it (4 tries)
//  4. sends ESPN's session (espn_s2 + SWID) back to the site, which stores it encrypted and sets up every league.
// node multi/login_runner/run.mjs   with env SITE, JOB, SIG, LOGIN, BUILD_TOKEN, LOGIN_KEY (PW_PKG optional: a Playwright path)
import { createRequire } from 'node:module';
import { createHmac, timingSafeEqual } from 'node:crypto';
import { open } from '../worker/src/crypto.js';
import { espnLoginStart, espnLoginCode } from '../worker/src/espn_login.js';
import { makeLib } from './pw_shim.mjs';
import { discoverLeagues } from './discover.mjs';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PW_PKG || 'playwright');

const { SITE, JOB, BUILD_TOKEN, LOGIN_KEY } = process.env;
const ok = /^https:\/\/[a-z0-9.-]+\.workers\.dev$/.test(SITE || '') || process.env.FZ_LOCAL_TEST === '1';
if (!ok || !/^[a-z0-9]{16}$/.test(JOB || '') || !BUILD_TOKEN || !LOGIN_KEY) { console.error('missing or bad SITE/JOB/BUILD_TOKEN/LOGIN_KEY'); process.exit(2); }
// The site signs (site|job) with BUILD_TOKEN; a dispatch naming any other site is refused before anything is sent.
const want = createHmac('sha256', BUILD_TOKEN).update(`${SITE}|${JOB}`).digest();
const got = Buffer.from(String(process.env.SIG || ''), 'hex');
if (got.length !== want.length || !timingSafeEqual(got, want)) { console.error('site signature does not match; not contacting it'); process.exit(2); }
const api = `${SITE}/api/build/login/${JOB}`;
const H = { Authorization: `Bearer ${BUILD_TOKEN}`, 'Content-Type': 'application/json' };
const decrypt = (sealed) => open({ ENC_KEY: LOGIN_KEY }, sealed);
const mask = (v) => { if (process.env.GITHUB_ACTIONS) console.log(`::add-mask::${v}`); };
const get = async () => (await fetch(api, { headers: H })).json();
const report = async (body) => { const r = await fetch(api, { method: 'POST', headers: H, body: JSON.stringify(body) }); return r.json().catch(() => ({})); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const lib = makeLib(chromium, process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH, args: ['--no-sandbox'] } : {});
const env = { BROWSER: {}, __browserLib: lib, ESPN_LOGIN_URL: process.env.ESPN_LOGIN_URL || undefined };
let exitCode = 0;
try {
  const j = await get();
  if (j.error) throw new Error('login expired before the job started');
  if (!process.env.LOGIN) throw new Error('no login in the start request');
  const { email, password } = JSON.parse(await decrypt(process.env.LOGIN));
  mask(email); mask(password);
  await report({ status: 'running' });
  let r = await espnLoginStart(env, email, password);
  const trace = [...(r.trace || [])];
  let tries = 0;
  while (r.status === 'code' && tries < 4) {
    await report({ status: tries ? 'code_wrong' : 'code' });
    let code = null;
    const until = Date.now() + 9 * 60000;
    while (!code && Date.now() < until) {
      await sleep(3000);
      const s = await get();
      if (s.error) break;
      if (s.code_enc) { code = await decrypt(s.code_enc); mask(code); }
    }
    if (!code) { r = { status: 'error', error: 'No code came in time. Log in again.' }; trace.push('no code typed in 9 minutes'); break; }
    tries++;
    r = await espnLoginCode(env, r.sessionId, code);
    trace.push(...(r.trace || []));
  }
  if (r.status === 'code') r = { status: 'error', error: 'Too many wrong codes. Log in again.' };
  if (r.status === 'ok') {
    mask(r.s2);
    // find the account's leagues from a signed-in browser (ESPN may answer a server with nothing)
    const d = new Date(), season = d.getUTCFullYear() - (d.getUTCMonth() < 2 ? 1 : 0);
    const found = await discoverLeagues(chromium, process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH, args: ['--no-sandbox'] } : {},
      { s2: r.s2, swid: r.swid, season, startUrl: process.env.ESPN_API_MOCK || '' });
    trace.push(...found.notes);
    const a = await report({ status: 'ok', s2: r.s2, swid: r.swid, leagues: found.leagues, trace });
    console.log(a.ok ? 'signed in; leagues set up' : `site refused: ${a.error}`);
  } else {
    await report({ status: 'error', msg: r.error || 'Signing in to ESPN failed. Try again in a minute.', trace });
    console.log(`sign-in failed: ${r.error}`);
  }
  console.log('trace:\n  ' + trace.join('\n  '));
} catch (e) {
  console.log(`job failed: ${e.message}`);
  await report({ status: 'error', msg: 'Signing in to ESPN failed. Try again in a minute.', trace: [`job failed: ${String(e.message).slice(0, 160)}`] }).catch(() => {});
  exitCode = 1;
} finally {
  await lib.shutdown();
}
process.exit(exitCode);
