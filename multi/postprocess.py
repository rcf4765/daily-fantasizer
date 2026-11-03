"""The Daily Fantasizer, any league: finishing touches on a rendered edition.

Usage: python3 postprocess.py IN.html OUT.html config.json
config keys used: platform ("espn" | "yahoo"), features {"rules": bool, "bets": bool}, accent ("#rrggbb"),
teams (count, for the Rule Changes wording).

What it does (the Men Fantasizing paper never goes through this file):
- Rule Changes and Betting tabs are optional and OFF unless the commissioner turned them on.
  Betting needs a team sign-in, which lives on the Rule Changes tab, so Betting alone keeps that tab
  as a slim "Your Team" sign-in page with the voting sections removed.
- Optimal Lineup (Compare Players) is the Men Fantasizing owner's private tool: removed.
- The Detroit Lions accent becomes the league's own accent color.
- Wording that names ESPN as the league host follows the league's platform; votes need a majority of
  this league, and passed changes are set by the commissioner (no auto-apply outside Men Fantasizing).
"""
import json, re, sys


def find_block(html, start):
    """Return the end index of the element that starts at `start` (handles nesting of the same tag)."""
    m = re.match(r"<([a-zA-Z0-9]+)", html[start:])
    tag = m.group(1)
    pat = re.compile(rf"<{tag}\b|</{tag}>")
    depth, i = 0, start
    for x in pat.finditer(html, start):
        if x.group(0).startswith("</"):
            depth -= 1
            if depth == 0:
                return x.end()
        else:
            depth += 1
    raise ValueError(f"unbalanced <{tag}> at {start}")


def remove(html, opening_regex, all_=True):
    while True:
        m = re.search(opening_regex, html)
        if not m:
            return html
        end = find_block(html, m.start())
        html = html[:m.start()] + html[end:]
        if not all_:
            return html


def mix(hexc, other, pct):
    h = hexc.lstrip("#")
    a = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(other.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x * pct + y * (1 - pct)):02x}" for x, y in zip(a, b))


def main(src, dst, cfg_path):
    cfg = json.load(open(cfg_path))
    html = open(src, encoding="utf-8").read()
    feats = cfg.get("features") or {}
    rules, bets = bool(feats.get("rules")), bool(feats.get("bets"))
    host = {"espn": "ESPN", "yahoo": "Yahoo"}.get(cfg.get("platform", "espn"), "ESPN")
    nteams = int(cfg.get("teams") or 12)
    need = nteams // 2 + 1

    # ---- optional tabs ----
    if not bets:
        html = remove(html, r'<button class="tab"[^>]*id="tab-bets"')
        html = remove(html, r'<div class="tab-pane" id="betting"')
    if not rules and not bets:
        html = remove(html, r'<button class="tab"[^>]*id="tab-props"')
        html = remove(html, r'<div class="tab-pane" id="proposals"')
        html = remove(html, r'<a class="to-league" href="#proposals"')
    elif not rules:  # Betting on its own: keep the tab as the team sign-in page
        html = re.sub(r'(<button class="tab"[^>]*id="tab-props"[^>]*>)<span class="tab-t">Rule Changes</span><span class="tab-s">[^<]*</span>',
                      r'\1<span class="tab-t">Your Team</span><span class="tab-s">Sign in to bet</span>', html)
        # the voting sections stay in the page (its script expects them) but are never shown
        html = html.replace("</title>", '</title><style id="fz-signin-only">#rc-floor,#rc-ideas,#rc-book-sec,.rc-stats{display:none!important}</style>', 1)
        html = html.replace("proposals:'Rules'", "proposals:'Team'")
        html = re.sub(r'(<section class="lg-hero rc-hero"[^>]*>)<span class="kicker">The league office[^<]*</span><h2>Rule <span>Changes</span></h2>\s*<p>[^<]*</p>',
                      r'\1<span class="kicker">The league office</span><h2>Your <span>Team</span></h2><p>Claim your team once on this phone. Betting uses the same sign-in.</p>', html)
        html = remove(html, r'<ol class="rc-steps"')
        html = re.sub(r'<a class="to-league" href="#proposals" data-tab="proposals">.*?</a>',
                      '<a class="to-league" href="#betting" data-tab="betting"><span class="kicker">Side game</span><b>Bet points on props, league matchups and NFL games</b><em>Betting →</em></a>',
                      html, count=1, flags=re.S)
    if rules:
        html = html.replace("Seven yes votes and it goes live on ESPN the next Tuesday, between weeks.",
                            f"{need} yes votes passes it, and the commissioner sets it in {host}.")
        html = html.replace("7 of 12 vote yes: live on ESPN Tuesday", f"{need} of {nteams} vote yes: the commissioner sets it")
        html = html.replace("the commissioner sets them in ESPN.", f"the commissioner sets them in {host}.")
        html = html.replace("What passed, and whether it&rsquo;s live on ESPN", f"What passed, and whether it&rsquo;s live on {host}")
        html = html.replace("'Live on ESPN'", f"'Live on {host}'").replace("'Commissioner sets in ESPN'", f"'Commissioner sets in {host}'")

    # ---- owner-only Optimal Lineup ----
    html = re.sub(r'<button type="button" role="tab" data-k="ps-lineup"[^>]*>Optimal Lineup</button>', "", html)
    html = remove(html, r'<div class="cmb-p[^"]*" id="ps-lineup"')

    # ---- platform wording ----
    html = html.replace("Every number computed from ESPN league data", f"Every number computed from {host} league data")
    html = html.replace("Crests from each team's ESPN profile.", f"Crests from each team's {host} profile.")
    html = html.replace("The Daily Fantasizer · printed in the <b>313</b>", "The Daily Fantasizer · <b>printed every Tuesday</b>")  # 313 = Detroit
    if host != "ESPN":
        html = html.replace('"ESPN":"ESPN, the league\'s host and one of the projection sources"', '"ESPN":"ESPN, one of the projection sources"')

    # ---- accent color (replaces the Lions' Honolulu blue) ----
    acc = cfg.get("accent") or "#33658a"
    if re.fullmatch(r"#[0-9a-fA-F]{6}", acc):
        light2, dark1, dark2 = mix(acc, "#ffffff", .5), mix(acc, "#ffffff", .8), mix(acc, "#ffffff", .62)
        style = (f'<style id="fz-accent">:root:root:root{{--honolulu:{acc};--honolulu-2:{light2}}}'
                 f'@media (prefers-color-scheme:dark){{:root:root:root:not([data-theme="light"]){{--honolulu:{dark1};--honolulu-2:{dark2}}}}}'
                 f':root:root:root[data-theme="dark"]{{--honolulu:{dark1};--honolulu-2:{dark2}}}'
                 f'.ps-7{{background:var(--blue-2);opacity:.7}}.ps-8{{background:var(--muted);opacity:.7}}</style>')
        html = html.replace("</title>", "</title>" + style, 1)  # the template has no <head> tag

    open(dst, "w", encoding="utf-8").write(html)
    left = [k for k in ('id="tab-bets"', 'id="tab-props"', 'id="ps-lineup"') if k in html]
    print(f"postprocess: rules={'on' if rules else 'off'} bets={'on' if bets else 'off'} host={host} accent={acc}; tabs present: {left}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
