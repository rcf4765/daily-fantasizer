// First step of espn-login.yml: tell the site the job has started, seconds after GitHub picks it up, so the waiting
// page doesn't give up while the browser is still being set up. Node built-ins only (runs before setup-node / npm).
// Same rule as run.mjs: the site's signature of (site|job) must match before anything is sent to it.
import { createHmac, timingSafeEqual } from 'node:crypto';

const { SITE, JOB, BUILD_TOKEN } = process.env;
const ok = /^https:\/\/[a-z0-9.-]+\.[a-z]{2,}$/.test(SITE || '') && /^[a-z0-9]{16}$/.test(JOB || '') && BUILD_TOKEN;
if (!ok) { console.error('missing or bad SITE/JOB/BUILD_TOKEN'); process.exit(0); }
const want = createHmac('sha256', BUILD_TOKEN).update(`${SITE}|${JOB}`).digest();
const got = Buffer.from(String(process.env.SIG || ''), 'hex');
if (got.length !== want.length || !timingSafeEqual(got, want)) { console.error('site signature does not match; not contacting it'); process.exit(0); }
try {
  const r = await fetch(`${SITE}/api/build/login/${JOB}`, {
    method: 'POST', headers: { Authorization: `Bearer ${BUILD_TOKEN}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'starting' }),
  });
  console.log('told the site the sign-in started:', r.status);
} catch (e) {
  console.log('could not reach the site yet:', e.message);   // never fails the job: run.mjs reports again
}
