"""Offline test of multi/platforms/yahoo.py: a fake 4-team Yahoo league, 3 regular-season weeks, 2 final."""
import os, sys, json, xml.etree.ElementTree as ET
import tempfile
HOME = tempfile.mkdtemp(prefix="fz-yahoo-"); os.makedirs(HOME + "/data/players", exist_ok=True)
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.update(FZ_HOME=HOME, FZ_LEAGUE_KEY="461.l.777", YAHOO_TOKEN="x")
sys.path.insert(0, os.path.join(REPO, "multi", "platforms")); sys.path.insert(0, REPO)
import yahoo as Y
NSU = Y.NS["y"]
def wrap(inner): return ET.fromstring(f'<fantasy_content xmlns="{NSU}">{inner}</fantasy_content>')
TEAMS = {1: "Gridiron Goblins", 2: "Taco Tuesday All-Stars", 3: "The Waiver Wire Warriors", 4: "Saquon Deez"}
def team_xml(i, extra=""):
    return (f'<team><team_key>461.l.777.t.{i}</team_key><team_id>{i}</team_id><name>{TEAMS[i]}</name>'
            f'<team_logos><team_logo><size>large</size><url>https://example.invalid/{i}.png</url></team_logo></team_logos>'
            f'<managers><manager><nickname>Mgr{i}</nickname><is_commissioner>{1 if i == 1 else 0}</is_commissioner></manager></managers>{extra}</team>')
SCORES = {1: [(1, 2, 120.5, 98.2), (3, 4, 101.0, 101.0)], 2: [(1, 3, 88.1, 130.4), (2, 4, 110.0, 95.5)], 3: [(1, 4, 0, 0), (2, 3, 0, 0)]}
PLAYERS = {  # name, primary pos, selected, pts, nfl full team
 1: [("Josh Allen", "QB", "QB", 25.1, "Buffalo Bills"), ("Bijan Robinson", "RB", "RB", 18.2, "Atlanta Falcons"), ("Kyren Williams", "RB", "RB", 9.0, "Los Angeles Rams"),
     ("CeeDee Lamb", "WR", "WR", 22.0, "Dallas Cowboys"), ("Garrett Wilson", "WR", "WR", 4.1, "New York Jets"), ("Sam LaPorta", "TE", "TE", 7.7, "Detroit Lions"),
     ("Tony Pollard", "RB", "W/R/T", 12.4, "Tennessee Titans"), ("Pittsburgh", "DEF", "DEF", 8.0, "Pittsburgh Steelers"), ("Justin Tucker", "K", "K", 9.0, "Baltimore Ravens"),
     ("Tee Higgins", "WR", "BN", 26.8, "Cincinnati Bengals")],
}
def players_for(t, w):
    base = PLAYERS[1]
    out = ""
    for k, (n, pos, sel, pts, nfl) in enumerate(base):
        pts = round(pts * (0.6 + 0.2 * ((t + w + k) % 4)), 2)
        name = n if t == 1 else f"{n} {chr(64 + t)}" if pos not in ("DEF",) else ["Pittsburgh", "Detroit", "Chicago", "Denver"][t - 1]
        nflf = nfl if pos != "DEF" else ["Pittsburgh Steelers", "Detroit Lions", "Chicago Bears", "Denver Broncos"][t - 1]
        out += (f'<player><name><full>{name}</full></name><editorial_team_abbr>X</editorial_team_abbr><editorial_team_full_name>{nflf}</editorial_team_full_name>'
                f'<display_position>{pos}</display_position><primary_position>{pos}</primary_position>'
                f'<selected_position><position>{sel}</position></selected_position><player_points><total>{pts}</total></player_points></player>')
    return out
def fake_get(path):
    if path.endswith("/settings"):
        rp = "".join(f'<roster_position><position>{p}</position><count>{c}</count></roster_position>' for p, c in
                     [("QB", 1), ("WR", 2), ("RB", 2), ("TE", 1), ("W/R/T", 1), ("K", 1), ("DEF", 1), ("BN", 6), ("IR", 1)])
        mods = "".join(f'<stat><stat_id>{i}</stat_id><value>{v}</value></stat>' for i, v in [(4, .04), (5, 4), (6, -1), (9, .1), (10, 6), (11, 0.5), (12, .1), (13, 6), (18, -2)])
        return wrap(f'<league><league_key>461.l.777</league_key><name>Sunday Funday</name><season>2026</season><num_teams>4</num_teams>'
                    f'<current_week>3</current_week><start_week>1</start_week><end_week>17</end_week>'
                    f'<settings><uses_playoff>1</uses_playoff><playoff_start_week>4</playoff_start_week><num_playoff_teams>2</num_playoff_teams>'
                    f'<roster_positions>{rp}</roster_positions><stat_modifiers><stats>{mods}</stats></stat_modifiers></settings></league>')
    if path.endswith("/teams"):
        return wrap(f'<league><teams>{"".join(team_xml(i) for i in TEAMS)}</teams></league>')
    if "/scoreboard;week=" in path:
        w = int(path.split("=")[-1]); ms = ""
        for a, b, pa, pb in SCORES[w]:
            st = "postevent" if w < 3 else "preevent"
            win = "" if pa == pb else f"<winner_team_key>461.l.777.t.{a if pa > pb else b}</winner_team_key>"
            ms += (f'<matchup><week>{w}</week><status>{st}</status><is_tied>{1 if pa == pb and st == "postevent" else 0}</is_tied>{win}<teams>'
                   f'{team_xml(a, f"<team_points><total>{pa}</total></team_points>")}{team_xml(b, f"<team_points><total>{pb}</total></team_points>")}</teams></matchup>')
        return wrap(f'<league><scoreboard><matchups>{ms}</matchups></scoreboard></league>')
    if "/roster" in path:
        t = int(path.split(".t.")[1].split("/")[0]); w = int(path.split("week=")[1].split("/")[0]) if "week=" in path else 3
        return wrap(f'<team><roster><players>{players_for(t, w)}</players></roster></team>')
    if "game_weeks" in path:
        return wrap('<game><game_weeks>' + "".join(f'<game_week><week>{w}</week><start>2026-09-{(w-1)*7+10:02d}</start><end>2026-09-{(w-1)*7+16:02d}</end></game_week>' for w in (1, 2, 3)) + '</game_weeks></game>')
    if "transactions" in path:
        tx = ('<transaction><transaction_key>461.l.777.tr.5</transaction_key><type>trade</type><status>successful</status><timestamp>1758200000</timestamp><players>'
              '<player><name><full>Tony Pollard</full></name><primary_position>RB</primary_position><transaction_data><type>trade</type><source_team_key>461.l.777.t.1</source_team_key><destination_team_key>461.l.777.t.2</destination_team_key></transaction_data></player>'
              '<player><name><full>Kyren Williams B</full></name><primary_position>RB</primary_position><transaction_data><type>trade</type><source_team_key>461.l.777.t.2</source_team_key><destination_team_key>461.l.777.t.1</destination_team_key></transaction_data></player>'
              '</players></transaction>'
              '<transaction><transaction_key>461.l.777.tr.4</transaction_key><type>add/drop</type><status>successful</status><timestamp>1757700000</timestamp><players>'
              '<player><name><full>Jaylen Warren</full></name><primary_position>RB</primary_position><transaction_data><type>add</type><source_type>waivers</source_type><destination_team_key>461.l.777.t.3</destination_team_key></transaction_data></player>'
              '<player><name><full>Rico Dowdle</full></name><primary_position>RB</primary_position><transaction_data><type>drop</type><source_type>team</source_type><source_team_key>461.l.777.t.3</source_team_key></transaction_data></player>'
              '</players></transaction>'
              '<transaction><transaction_key>461.l.777.tr.6</transaction_key><type>trade</type><status>proposed</status><timestamp>1758300000</timestamp><players></players></transaction>')
        return wrap(f'<league><transactions>{tx}</transactions></league>')
    raise SystemExit("unexpected path " + path)
Y.get = fake_get
import fetch_espn
fetch_espn.crest = lambda url: "data:image/webp;base64,AAAA"
Y.main()
raw = open(HOME + "/data/week2_raw.txt").read()
assert "SLOTS|QB:1,WR:2,RB:2,TE:1,FLEX:1,K:1,D/ST:1" in raw, raw[:300]
assert "Steelers D/ST|D/ST|D/ST|" in raw and "|FLEX|" in raw and "|BE|" in raw
assert "1|3|101|4|101|TIE" in raw, "week 1 tie"
assert "3|1|0|4|0|UNDECIDED" in raw, "next week listed, unplayed"
tr = json.load(open(HOME + "/data/trades.json"))["trades"]
assert len(tr) == 1 and tr[0]["teams"] == [1, 2], tr  # the proposed (not accepted) trade is not stored
sched = json.load(open(HOME + "/data/schedule.json")); assert sched["regweeks"] == 3 and len(sched["games"]) == 6
print("yahoo adapter: all checks passed")
