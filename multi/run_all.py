"""The printer: build every league's paper (or one) and upload it to the website. Run by
.github/workflows/fantasizer-leagues.yml.

  BUILD_TOKEN=... python3 multi/run_all.py https://fantasizer.example.workers.dev [slug]

1. asks the website for the leagues (with decrypted ESPN cookies / a fresh Yahoo token, never stored here);
2. fetches the shared player data once;
3. per league: restores its saved data, builds the paper (multi/build_league.py), uploads the edition, the
   betting board and the data back, and reports ok / waiting / error so the website can show it.
One league failing never stops the others.
"""
import io, json, os, subprocess, sys, tarfile, tempfile, traceback
import requests

SITE = sys.argv[1].rstrip("/")
ONLY = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
TOK = os.environ["BUILD_TOKEN"]
# A site named by the dispatch (not the repo variable FZ_SITE_URL) must carry the website's signature of site|slug,
# so the build token and league data never go to a look-alike address.
if SITE != (os.environ.get("FZ_VAR_SITE") or "").rstrip("/"):
    import hmac, hashlib
    want = hmac.new(TOK.encode(), f"{SITE}|{ONLY or ''}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(want, os.environ.get("SIG", "")):
        sys.exit("site signature does not match; not contacting it")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = {"Authorization": f"Bearer {TOK}"}
ROOT = os.environ.get("FZ_RUN_DIR") or tempfile.mkdtemp(prefix="fz-")


def api(method, path, **kw):
    r = requests.request(method, f"{SITE}{path}", headers=H, timeout=120, **kw)
    if r.status_code >= 400 and not (method == "GET" and r.status_code == 404):
        raise RuntimeError(f"{method} {path} → {r.status_code} {r.text[:200]}")
    return r


def status(slug, st, message="", week=None):
    try:
        api("POST", f"/api/build/{slug}/status", json={"status": st, "message": message[-400:], "week": week})
    except Exception as e:
        print("status report failed:", e)


def upload(slug, path, local):
    with open(local, "rb") as f:
        api("PUT", f"/api/build/{slug}/file", params={"path": path}, data=f)


def restore(slug, work):
    r = api("GET", f"/api/build/{slug}/file", params={"path": "cache/data.tgz"})
    if r.status_code == 200:
        with tarfile.open(fileobj=io.BytesIO(r.content), mode="r:gz") as t:
            t.extractall(work, filter="data")
        print(f"[{slug}] restored saved data")


def save(slug, work):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        def keep(ti):  # league data only; shared player files are fetched fresh every run
            return None if ti.name.startswith("data/players") and not ti.name.endswith("inj_log.json") else ti
        t.add(os.path.join(work, "data"), arcname="data", filter=keep)
        if os.path.exists(os.path.join(work, "league.json")):
            t.add(os.path.join(work, "league.json"), arcname="league.json")
    p = os.path.join(work, "cache.tgz")
    open(p, "wb").write(buf.getvalue())
    upload(slug, "cache/data.tgz", p)


def main():
    leagues = api("GET", "/api/build/leagues", params={"slug": ONLY} if ONLY else None).json()["leagues"]
    for c in leagues:  # keep secrets out of the Actions log
        for k in ("espn_s2", "swid", "yahoo_token"):
            if c.get(k):
                print(f"::add-mask::{c[k]}")
    print(f"{len(leagues)} league(s) to print")
    shared = os.path.join(ROOT, "shared")
    nofetch = os.environ.get("FZ_NO_FETCH") == "1"  # local tests: build from the restored data only
    rc = 0 if nofetch else subprocess.run([sys.executable, os.path.join(REPO, "multi", "shared_players.py"), shared]).returncode
    if rc:
        print("WARNING: shared player data failed; Player Stats may be thin this week")
    bad = 0
    for c in leagues:
        slug = c["slug"]
        if c.get("error"):
            status(slug, "error", c["error"]); bad += 1; continue
        work, out = os.path.join(ROOT, "leagues", slug), os.path.join(ROOT, "out", slug)
        os.makedirs(work, exist_ok=True); os.makedirs(out, exist_ok=True)
        cfg = os.path.join(ROOT, f"{slug}.cfg.json")
        with open(cfg, "w") as f:
            json.dump(c, f)
        try:
            status(slug, "building")
            restore(slug, work)
            log = os.path.join(ROOT, f"{slug}.log")
            with open(log, "w") as lf:
                rc = subprocess.run([sys.executable, os.path.join(REPO, "multi", "build_league.py"), "--config", cfg, "--work", work,
                                     "--out", out] + (["--no-fetch"] if nofetch else ["--shared", shared]), stdout=lf, stderr=subprocess.STDOUT).returncode
            text = open(log).read()
            for k in ("espn_s2", "swid", "yahoo_token"):
                if c.get(k):
                    text = text.replace(c[k], "***")
            print(f"----- {slug} -----\n{text[-6000:]}")
            if rc == 3:
                status(slug, "waiting", "No completed week yet."); save(slug, work); continue
            if rc != 0:
                last = [l for l in text.strip().splitlines() if l.strip()][-1:] or ["build failed"]
                status(slug, "error", last[0]); bad += 1; continue
            meta = json.load(open(os.path.join(out, "meta.json")))
            W = meta["week"]
            for name in (f"week{W}.html", "index.html"):  # the week first, so the homepage never points at a missing file
                upload(slug, name, os.path.join(out, name))
            lines = os.path.join(out, "bets", f"lines{W + 1}.json")
            if os.path.exists(lines):
                upload(slug, f"bets/lines{W + 1}.json", lines)
            upload(slug, "meta.json", os.path.join(out, "meta.json"))
            save(slug, work)
            status(slug, "ok", f"Week {W} printed.", W)
            print(f"[{slug}] week {W} published")
        except Exception as e:
            traceback.print_exc()
            status(slug, "error", str(e)); bad += 1
        finally:
            os.remove(cfg)
    print(f"done: {len(leagues) - bad} ok, {bad} failed")


if __name__ == "__main__":
    main()
