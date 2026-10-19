"""One-time: turn the under-construction Player Stats tab into the live one.
python3 migrate_ps.py template.html            -> leaves <!--PLAYERSTATS--> for render.py
python3 migrate_ps.py --fill page.html ...     -> also fills the pane with players.build()"""
import json, os, re, sys
import players

HERE = os.path.dirname(os.path.abspath(__file__))

OLD_HASH = """  function fromHash(){
    var h=(location.hash||'').slice(1);
    if(h==='player-stats')show('player-stats');
    else if(h)show('paper');
  }"""
NEW_HASH = """  function fromHash(){
    var h=(location.hash||'').slice(1);if(!h)return;
    var el=document.getElementById(h),pane=el&&(el.classList.contains('tab-pane')?el:el.closest('.tab-pane'));
    show(pane?pane.id:'paper');
    if(el&&pane&&el!==pane)el.scrollIntoView();
  }"""


def migrate(path, fill=None):
    s = open(path, encoding="utf-8").read()
    a = s.find("/* player stats: under construction */")
    if a >= 0:
        b = s.find(".desk .kicker{font-size:.62rem}\n", a)
        s = s[:a] + s[b + len(".desk .kicker{font-size:.62rem}\n"):]
    if "/* player stats */" not in s:
        i = s.rfind("</style>")
        s = s[:i] + players.CSS + s[i:]
    s = s.replace(' <span class="tab-tag">Soon</span>', "")
    s = s.replace("@media (max-width:400px){.tab-tag{display:none}}\n", "")
    if OLD_HASH in s:
        s = s.replace(OLD_HASH, NEW_HASH)
    start = s.find('<div class="tab-pane" id="player-stats"')
    end = s.rfind("<footer>")
    assert start > 0 and end > start, path
    pane = ('<div class="tab-pane" id="player-stats" role="tabpanel" aria-labelledby="tab-stats" hidden>\n'
            + (fill if fill is not None else "<!--PLAYERSTATS-->") + "\n</div>\n\n")
    s = s[:start] + pane + s[end:]
    open(path, "w", encoding="utf-8").write(s)
    print("migrated", path)


if __name__ == "__main__":
    args = sys.argv[1:]
    fill = None
    if args and args[0] == "--fill":
        args = args[1:]
        fill = players.build(json.load(open(os.path.join(HERE, "league.json")))["short_names"])
    for f in args:
        migrate(f, fill)
