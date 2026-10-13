// The Daily Fantasizer: team crest extractor.
// Run with Claude in Chrome's javascript_tool on an ESPN fantasy tab for the league,
// ONLY when logos.txt is missing or a team's logo URL changed (compare the LOGOURLS
// block from extract.js with logo_urls.txt). Optionally set ONLY = [3, 7] to redo a few.
// Each crest is drawn to a 72x72 canvas and exported as a small webp data URI
// (~2-4 KB each). Output is written into the page body; read it with get_page_text,
// then save the "@<teamId> data:image/webp;base64,..." lines to logos.txt verbatim.
const ONLY = null;
const LEAGUE = 1196354715, SEASON = 2026;
const d = await (await fetch(`https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/${SEASON}/segments/0/leagues/${LEAGUE}?view=mTeam`, { credentials: 'include' })).json();
const lines = [], errs = [];
for (const t of d.teams) {
  if (ONLY && !ONLY.includes(t.id)) continue;
  try {
    const b = await (await fetch(t.logo, { credentials: t.logo.includes('mystique') ? 'include' : 'omit' })).blob();
    const im = new Image(); im.src = URL.createObjectURL(b); await im.decode();
    const c = document.createElement('canvas'); c.width = c.height = 72; const x = c.getContext('2d');
    const w0 = im.naturalWidth || 72, h0 = im.naturalHeight || 72, s = Math.min(72 / w0, 72 / h0);
    x.drawImage(im, (72 - w0 * s) / 2, (72 - h0 * s) / 2, w0 * s, h0 * s);
    lines.push('@' + t.id + ' ' + c.toDataURL('image/webp', 0.82));
  } catch (e) { errs.push(t.id + ': ' + e.message); }
}
document.body.innerHTML = '<article><pre id="cd-logos"></pre></article>';
document.getElementById('cd-logos').textContent = lines.join('\n');
`ok: ${lines.length} crests` + (errs.length ? ' | errors: ' + errs.join('; ') : '') + '. Now call get_page_text.'
