import os, json, requests, time
S=requests.Session()
S.headers["User-Agent"]="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
os.makedirs("out2",exist_ok=True)
def save(name,r):
    open(f"out2/{name}","wb").write(r.content)
    print(name,r.status_code,r.headers.get("content-type"),len(r.content),r.url[:120])
def g(name,u,**kw):
    try: save(name,S.get(u,timeout=60,**kw))
    except Exception as e: print(name,"ERR",e)
    time.sleep(1.2)
fp="https://www.fantasypros.com/nfl/"
for wk in (3,5):
    for pos in ("qb","ppr-rb","ppr-wr","ppr-te"):
        g(f"fp_ecr_{pos}_w{wk}.html",fp+f"rankings/{pos}.php?week={wk}")
for pos in ("qb","rb","wr","te"):
    g(f"fp_proj_{pos}_w5.html",fp+f"projections/{pos}.php?scoring=PPR&week=5")
g("fp_ros_ppr_rb.html",fp+"rankings/ros-ppr-rb.php")
g("yahoo_smyth_w6.html","https://sports.yahoo.com/fantasy/article/fantasy-football-rankings-week-6-joel-smyth-181922431.html")
g("yahoo_smyth_author.html","https://sports.yahoo.com/author/joel-smythff/")
nv="https://github.com/nflverse/nflverse-data/releases/download/"
g("nv_stats_week_2026.csv",nv+"stats_player/stats_player_week_2026.csv")
g("nv_snaps_2026.csv",nv+"snap_counts/snap_counts_2026.csv")
g("nv_ff_opp_2026.csv",nv+"ff_opportunity/ff_opportunity_weekly_2026.csv")
LEAGUE,SEASON=1196354715,2026
E=requests.Session(); E.headers["User-Agent"]=S.headers["User-Agent"]
E.cookies.set("espn_s2",os.environ.get("ESPN_S2","").strip(),domain=".espn.com")
E.cookies.set("SWID",os.environ.get("ESPN_SWID","").strip(),domain=".espn.com")
base=f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{SEASON}/segments/0/leagues/{LEAGUE}"
flt={"players":{"filterSlotIds":{"value":[0,2,4,6,23]},"limit":500,"sortPercOwned":{"sortPriority":1,"sortAsc":False},
     "filterStatsForTopScoringPeriodIds":{"value":18,"additionalValue":[f"00{SEASON}",f"10{SEASON}",f"11{SEASON}"]}}}
save("espn_kona_all.json",E.get(base,params={"view":"kona_player_info","scoringPeriodId":7},headers={"X-Fantasy-Filter":json.dumps(flt)},timeout=90))
save("espn_status.json",E.get(base,params={"view":"mStatus"},timeout=30))
