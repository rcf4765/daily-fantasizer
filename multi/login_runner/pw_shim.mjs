// A puppeteer-style face on Playwright, covering exactly what multi/worker/src/espn_login.js uses, so the same sign-in
// code runs on Cloudflare's browser (paid plan) and on a free GitHub Actions runner with Playwright.
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36';
const wrapEl = (h) => ({
  click: (o) => h.click(o && o.clickCount === 3 ? { clickCount: 3 } : {}),
  type: (t, o) => h.type(t, { delay: (o && o.delay) || 0 }),
  press: (k) => h.press(k),
  isIntersectingViewport: async () => h.isVisible(),
});
const wrapFrame = (f) => ({
  url: () => f.url(),
  $: async (s) => { const h = await f.$(s); return h && wrapEl(h); },
  $$: async (s) => (await f.$$(s)).map(wrapEl),
  waitForSelector: async (s, o) => wrapEl(await f.waitForSelector(s, { state: 'visible', timeout: o.timeout })),
  $$eval: (s, fn) => f.$$eval(s, fn),
});
const wrapPage = (p) => ({
  setUserAgent: async () => {},
  setViewport: (v) => p.setViewportSize(v),
  goto: (u, o) => p.goto(u, { waitUntil: 'networkidle', timeout: o.timeout }),
  cookies: async (...urls) => p.context().cookies(urls.length ? urls : undefined),
  frames: () => p.frames().map(wrapFrame),
  mainFrame: () => wrapFrame(p.mainFrame()),
  $: (s) => p.$(s),
});

/** lib.launch / lib.connect as espn_login.js calls them; sessions live in this process (one job = one process). */
export function makeLib(chromium, launchOptions = {}) {
  let browser = null;
  const sessions = new Map();
  const handle = (id, ctx) => ({
    newPage: async () => wrapPage(await ctx.newPage()),
    pages: async () => ctx.pages().map(wrapPage),
    sessionId: () => id,
    disconnect: async () => {},
    close: async () => { sessions.delete(id); await ctx.close(); },
  });
  return {
    launch: async () => {
      browser = browser || await chromium.launch(launchOptions);
      const ctx = await browser.newContext({ userAgent: UA, locale: 'en-US', viewport: { width: 1280, height: 900 } });
      const id = 'S' + (sessions.size + 1) + Date.now();
      sessions.set(id, ctx);
      return handle(id, ctx);
    },
    connect: async (b, id) => {
      const ctx = sessions.get(id);
      if (!ctx) throw new Error('sign-in session ended');
      return handle(id, ctx);
    },
    shutdown: async () => { if (browser) await browser.close(); },
  };
}
