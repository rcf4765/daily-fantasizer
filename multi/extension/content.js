// Runs on the Daily Fantasizer site. Tells the page the extension is installed and relays the "link ESPN" request to the
// extension. The ESPN cookies never pass through here or the page: the extension sends them straight to the site's server.
(() => {
  const post = (msg) => window.postMessage({ fz: 'espn-link-result', ...msg }, location.origin);
  const mark = () => { document.documentElement.dataset.fzExt = chrome.runtime.getManifest().version; };
  if (document.documentElement) mark(); else document.addEventListener('readystatechange', mark, { once: true });
  window.addEventListener('message', (e) => {
    if (e.source !== window || !e.data || e.data.fz !== 'espn-link') return;
    chrome.runtime.sendMessage({ type: 'espn-link' }, (res) => {
      if (chrome.runtime.lastError || !res) post({ ok: false, error: 'The extension didn’t answer. Reload this page and try again.' });
      else post(res);   // { ok:true, pending:true } now; the final answer arrives below
    });
  });
  chrome.runtime.onMessage.addListener((msg) => { if (msg && msg.type === 'espn-link-result') post(msg.result); });
})();
