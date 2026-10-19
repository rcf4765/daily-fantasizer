import os, json, requests, time
S=requests.Session()
S.headers["User-Agent"]="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
os.makedirs("out",exist_ok=True)
def save(name,r):
    open(f"out/{name}","wb").write(r.content)
    print(name,r.status_code,r.headers.get("content-type"),len(r.content))
fp="https://www.fantasypros.com/nfl/"
urls={
 "fp_wk_ppr_flex.html":fp+"rankings/ppr-flex.php",
 "fp_wk_qb.html":fp+"rankings/qb.php",
 "fp_wk_ppr_rb_w6.html":fp+"rankings/ppr-rb.php?week=6",
 "fp_ros_ppr.html":fp+"rankings/ros-ppr-overall.php",
 "fp_proj_wr.html":fp+"projections/wr.php?scoring=PPR",
 "fp_proj_wr_w7.html":fp+"projections/wr.php?scoring=PPR&week=7",
 "fp_snaps.html":fp+"reports/snap-counts/?year=2026",
 "fp_targets.html":fp+"reports/targets/?year=2026",
 "fp_adv_wr.html":fp+"advanced-stats-wr.php?year=2026",
 "fp_smyth.html":fp+"rankings/joel-smyth-consensus-rankings.php",
 "fp_smyth_rb.html":fp+"rankings/joel-smyth-consensus-rankings.php?position=RB",
}
for k,u in urls.items():
    try: save(k,S.get(u,timeout=40))
    except Exception as e: print(k,"ERR",e)
    time.sleep(1.5)
# ESPN
LEAGUE,SEASON=1196354715,2026
E=requests.Session(); E.headers["User-Agent"]=S.headers["User-Agent"]
E.cookies.set("espn_s2",os.environ.get("ESPN_S2","").strip(),domain=".espn.com")
E.cookies.set("SWID",os.environ.get("ESPN_SWID","").strip(),domain=".espn.com")
base=f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{SEASON}"
for wk in (6,7):
    flt={"players":{"filterSlotIds":{"value":[0,2,4,6,23]},"limit":400,"sortPercOwned":{"sortPriority":1,"sortAsc":False},
         "filterStatsForTopScoringPeriodIds":{"value":2,"additionalValue":[f"00{SEASON}",f"10{SEASON}"]}}}
    r=E.get(f"{base}/segments/0/leagues/{LEAGUE}",params={"view":"kona_player_info","scoringPeriodId":wk},headers={"X-Fantasy-Filter":json.dumps(flt)},timeout=60)
    save(f"espn_kona_w{wk}.json",r)
r=E.get(f"{base}/players",params={"scoringPeriodId":0,"view":"players_wl"},headers={"X-Fantasy-Filter":json.dumps({"filterActive":{"value":True}})},timeout=60); save("espn_players_wl.json",r)
r=E.get(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",params={"week":6,"seasontype":2},timeout=30); save("espn_scoreboard_w6.json",r)
