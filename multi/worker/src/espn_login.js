// Signs in to ESPN for a user, the way FantasyPros' app does: the user types their ESPN email and password on our
// site, a real browser (Cloudflare Browser Rendering) fills ESPN's own login (Disney's OneID form), and we keep only
// the two ESPN session cookies (espn_s2, SWID). The password is used once and never stored or logged.
// ESPN sometimes emails a 6-digit code instead of (or after) the password: the browser is then kept open for up to
// 10 minutes and the user types the code on our site.
//
// ESPN changes this login page from time to time. Everything that depends on its layout is in SEL below, and every
// step is written to a trace (step names and page addresses only, never what was typed), so a failed sign-in can be
// fixed from the trace. Untested against the live ESPN page at the time of writing.
// Loaded only when a real sign-in runs (wrangler bundles it), so the local tests run without it.
const browserLib = async () => (await import('@cloudflare/puppeteer')).default;

export const LOGIN_URL = 'https://www.espn.com/login';
export const SEL = {
  oneidFrame: /registerdisney\.go\.com|oneid|disneyid/i,             // the login form lives in an iframe from Disney
  email: 'input[type="email"], #InputIdentityFlowValue, input[name="email"], input[autocomplete="username"]',
  password: 'input[type="password"], #InputPassword',
  submit: '#BtnSubmit, button[type="submit"], button[data-testid="BtnSubmit"]',
  code: 'input[autocomplete="one-time-code"], input[name*="code" i], input[id*="otp" i], input[id*="Code"], input[inputmode="numeric"]',
  error: '[role="alert"], .message-error, .error-message, [data-testid*="error" i], .field-error',
  challenge: 'iframe[src*="captcha" i], iframe[src*="arkose" i], #arkose, [id*="captcha" i]',
};
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36';
const COOKIE_URLS = ['https://www.espn.com', 'https://fantasy.espn.com', 'https://espn.com'];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function tracer() {
  const t0 = Date.now(), steps = [];
  return { steps, add: (s) => steps.push(`${((Date.now() - t0) / 1000).toFixed(1)}s ${s}`) };
}

let extraCookieUrl = null;   // tests point the login at a mock ESPN; read its cookies too
async function sessionCookies(page) {
  const all = await page.cookies(...COOKIE_URLS, ...(extraCookieUrl ? [extraCookieUrl] : []));
  const s2 = all.find((c) => c.name === 'espn_s2'), swid = all.find((c) => c.name === 'SWID');
  return s2 && swid ? { s2: decodeURIComponent(s2.value), swid: swid.value } : null;
}

async function loginFrame(page, tr, ms = 20000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    const f = page.frames().find((x) => SEL.oneidFrame.test(x.url()));
    if (f) { tr.add(`login form found (${new URL(f.url()).host})`); return f; }
    if (await page.$(SEL.email)) { tr.add('login form found (on the page itself)'); return page.mainFrame(); }
    await sleep(500);
  }
  tr.add(`login form not found; frames: ${page.frames().map((x) => { try { return new URL(x.url()).host; } catch (e) { return '?'; } }).join(', ')}`);
  return null;
}

async function find(frame, sel, ms) {
  try { return await frame.waitForSelector(sel, { visible: true, timeout: ms }); } catch (e) { return null; }
}

async function textOf(frame, sel) {
  try { return (await frame.$$eval(sel, (els) => els.map((e) => e.textContent.trim()).filter(Boolean).join(' '))).slice(0, 200); } catch (e) { return ''; }
}

/** After a submit: wait for the session cookies, a code prompt, an error, or a bot check. */
/** A bot check that is really on screen (Disney's login page also loads an invisible one in the background,
 *  which must not count). Returns a short description of what matched, or ''. */
async function visibleChallenge(f) {
  try {
    return await f.$$eval(SEL.challenge, (els) => {
      for (const e of els) {
        const r = e.getBoundingClientRect(), st = getComputedStyle(e);
        if (r.width >= 40 && r.height >= 40 && st.visibility !== 'hidden' && st.display !== 'none' && +st.opacity !== 0) {
          return `${e.tagName.toLowerCase()}${e.id ? '#' + e.id : ''} ${Math.round(r.width)}x${Math.round(r.height)}`;
        }
      }
      return '';
    });
  } catch (e) { return ''; }
}

async function outcome(page, frame, tr, ms = 25000, { codeGrace = 0 } = {}) {
  const t0 = Date.now(), end = t0 + ms;
  let seenChallenge = 0;
  while (Date.now() < end) {
    try {   // ESPN's form reloads between steps; a check that lands mid-reload just tries again
      const c = await sessionCookies(page);
      if (c) { tr.add('signed in: ESPN session received'); return { status: 'ok', ...c }; }
      const f = page.frames().find((x) => SEL.oneidFrame.test(x.url())) || frame;
      // right after a code is submitted the old boxes are still on screen; give ESPN a moment before calling it wrong
      if (f && Date.now() - t0 >= codeGrace && await f.$(SEL.code)) { tr.add('ESPN asked for a one-time code'); return { status: 'code' }; }
      // a bot check only counts when it is really on screen and stays there (no session after 12 seconds)
      const ch = f ? await visibleChallenge(f) : '';
      if (ch && !seenChallenge) { seenChallenge = Date.now(); tr.add(`bot check on screen (${ch}); waiting`); }
      if (!ch) seenChallenge = 0;
      if (seenChallenge && Date.now() - seenChallenge > 12000) { tr.add('ESPN kept the bot check up'); return { status: 'error', error: 'ESPN asked for an extra security check we can’t do from here. Try again in a few minutes.', retry: true }; }
      const err = f ? await textOf(f, SEL.error) : '';
      if (err && await f.$(SEL.code)) { tr.add('ESPN rejected the code'); return { status: 'code' }; }
      if (err) { tr.add(`ESPN error shown (${err.length} chars)`); return { status: 'error', error: /password|credential|match|incorrect|invalid/i.test(err) ? 'ESPN didn’t accept that email and password.' : `ESPN said: ${err}` }; }
    } catch (e) { /* mid-reload */ }
    await sleep(700);
  }
  tr.add('no answer from ESPN in time');
  return { status: 'error', error: 'ESPN didn’t finish signing in. Try again in a minute.', retry: true };
}

/** Step 1: email + password. Returns {status:'ok', s2, swid} | {status:'code', sessionId} | {status:'error', error}. */
export async function espnLoginStart(env, email, password) {
  const tr = tracer();
  extraCookieUrl = env.ESPN_LOGIN_URL ? new URL(env.ESPN_LOGIN_URL).origin : null;
  if (!env.BROWSER) return { status: 'error', error: 'ESPN sign-in isn’t set up on this site yet.', trace: ['no BROWSER binding'] };
  let browser;
  try {
    browser = await (env.__browserLib || await browserLib()).launch(env.BROWSER, { keep_alive: 600000 });
    const page = await browser.newPage();
    await page.setUserAgent(UA);
    await page.setViewport({ width: 1280, height: 900 });
    tr.add('opening ESPN login');
    await page.goto(env.ESPN_LOGIN_URL || LOGIN_URL, { waitUntil: 'networkidle2', timeout: 30000 }).catch(() => tr.add('page still loading after 30s'));
    const already = await sessionCookies(page);
    if (already) { tr.add('unexpected: already signed in'); }
    const frame = await loginFrame(page, tr);
    if (!frame) return { status: 'error', error: 'ESPN’s login page didn’t load. Try again in a minute.', retry: true, trace: tr.steps };
    const em = await find(frame, SEL.email, 15000);
    if (!em) { tr.add('email box not found'); return { status: 'error', error: 'ESPN’s login page changed. We’ve been told; try again later.', trace: tr.steps }; }
    await em.click({ clickCount: 3 }); await em.type(email, { delay: 25 });
    tr.add('email entered');
    let pw = await frame.$(SEL.password);
    if (!pw || !(await pw.isIntersectingViewport().catch(() => true))) {
      const b = await frame.$(SEL.submit); if (b) await b.click(); else await em.press('Enter');
      tr.add('continue pressed');
      pw = await find(frame, SEL.password, 15000);
    }
    if (!pw) {
      const r = await outcome(page, frame, tr, 20000);   // passwordless accounts go straight to a code (or a bot check shows)
      if (r.status === 'code') { const sessionId = browser.sessionId(); await browser.disconnect(); browser = null; return { ...r, sessionId, trace: tr.steps }; }
      if (r.status === 'ok') return { ...r, trace: tr.steps };
      tr.add('password box not found');
      return { status: 'error', error: r.error || 'ESPN’s login page changed. We’ve been told; try again later.', trace: tr.steps };
    }
    await pw.type(password, { delay: 25 });
    tr.add('password entered');
    const b = await frame.$(SEL.submit); if (b) await b.click(); else await pw.press('Enter');
    tr.add('log in pressed');
    const r = await outcome(page, frame, tr);
    if (r.status === 'code') { const sessionId = browser.sessionId(); await browser.disconnect(); browser = null; return { ...r, sessionId, trace: tr.steps }; }
    return { ...r, trace: tr.steps };
  } catch (e) {
    tr.add(`browser error: ${String(e.message || e).slice(0, 160)}`);
    return { status: 'error', error: 'Signing in to ESPN failed. Try again in a minute.', retry: true, trace: tr.steps };
  } finally {
    if (browser) await browser.close().catch(() => {});
  }
}

/** Step 2 (only when ESPN asked): the one-time code ESPN emailed. */
export async function espnLoginCode(env, sessionId, code) {
  const tr = tracer();
  extraCookieUrl = env.ESPN_LOGIN_URL ? new URL(env.ESPN_LOGIN_URL).origin : null;
  let browser;
  try {
    browser = await (env.__browserLib || await browserLib()).connect(env.BROWSER, sessionId);
    const page = (await browser.pages())[0];
    if (!page) throw new Error('no page');
    const frame = page.frames().find((x) => SEL.oneidFrame.test(x.url())) || page.mainFrame();
    const boxes = await frame.$$(SEL.code);
    if (!boxes.length) { tr.add('code box gone'); return { status: 'error', error: 'That sign-in timed out. Start again.', trace: tr.steps }; }
    for (const bx of boxes) { await bx.click({ clickCount: 3 }); await bx.press('Backspace'); }   // clear a previous try
    if (boxes.length >= code.length) { for (let i = 0; i < code.length; i++) await boxes[i].type(code[i]); }   // one box per digit
    else await boxes[0].type(code, { delay: 30 });
    tr.add(`code entered (${boxes.length} box${boxes.length > 1 ? 'es' : ''})`);
    const b = await frame.$(SEL.submit); if (b) await b.click(); else await boxes[boxes.length - 1].press('Enter');
    const r = await outcome(page, frame, tr, 25000, { codeGrace: 4000 });
    if (r.status === 'code') { await browser.disconnect(); browser = null; return { status: 'code', again: true, sessionId, trace: tr.steps }; }
    return { ...r, trace: tr.steps };
  } catch (e) {
    tr.add(`browser error: ${String(e.message || e).slice(0, 160)}`);
    return { status: 'error', error: 'That sign-in timed out. Start again.', trace: tr.steps };
  } finally {
    if (browser) await browser.close().catch(() => {});
  }
}
