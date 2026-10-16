#!/usr/bin/env python3
"""ig_collector.py -- "cold account" Instagram Reels collector (Plan A).

Auto-scrolls the Reels feed on a logged-in Instagram account with a fixed,
content-independent dwell time, and captures each reel's link + labels from
the JSON the page loads (network interception, no DOM scraping). Optionally
downloads the captured reels with yt-dlp using the session cookies.

Cold-account rules (so the algorithm learns nothing about taste):
  * never like, follow, comment, save, or open profiles
  * fixed dwell per reel; the only jitter is content-independent timing noise
  * skip every interest prompt at signup; following list stays empty

Labels captured per reel (all from feed JSON payloads):
  url, shortcode, username, user_pk, caption, hashtags, music (title/artist),
  taken_at, video urls, alt text (when present).
  --account-categories additionally records each author's business category
  and follower count via web_profile_info; this performs profile lookups,
  which are a (mild) preference signal, so it is OFF by default for cold runs.

Setup:  pip install playwright    # no browser download: uses your installed Edge
First run (log in manually once; session persists in ig_profile/):
  python3 ig_collector.py --login
Collect ~100 reels with 5 s dwell:
  python3 ig_collector.py --reels 100 --dwell 5
Collect and download every captured reel:
  python3 ig_collector.py --reels 100 --download
Download the already-captured pool (no browser needed):
  python3 ig_collector.py --download-only

Output: videos/ig_captured.jsonl (one JSON per reel, append-resumable).
"""

import argparse
import json
import os
import random
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

REEL_URL = "https://www.instagram.com/reel/{sc}/"
HASHTAG_RE = re.compile(r"#([A-Za-z0-9_À-￿]+)")
# Remove automation markers: Instagram loops login verification for
# browsers it flags as automation.
STEALTH_INIT = "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
STEALTH_ARGS = ["--disable-blink-features=AutomationControlled"]
STEALTH_IGNORE = ["--enable-automation"]
# Web app id Instagram's own web client sends; required for /api/v1 calls.
IG_APP_ID = "936619743392459"


def load_existing(out_path: Path) -> dict:
    """Existing jsonl rows keyed by shortcode (resume support)."""
    seen = {}
    if out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("shortcode"):
                    seen[row["shortcode"]] = row
    return seen


def append_row(out_path: Path, row: dict):
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()


def is_logged_in(context) -> bool:
    return any(c["name"] == "sessionid" for c in context.cookies("https://www.instagram.com/"))


def export_cookies(context, path: Path):
    """Write cookies in Netscape format so yt-dlp can reuse this session."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Netscape HTTP Cookie File"]
    for c in context.cookies():
        if "instagram.com" not in (c.get("domain") or ""):
            continue
        domain = c.get("domain", "")
        flag = "TRUE" if domain.startswith(".") else "FALSE"
        secure = "TRUE" if c.get("secure") else "FALSE"
        expires = c.get("expires")
        expiry = str(int(expires)) if expires is not None and expires > 0 else "0"
        lines.append("\t".join([
            domain, flag, c.get("path", "/"), secure, expiry,
            c.get("name", ""), c.get("value", ""),
        ]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _get(d: dict, *paths):
    for keys in paths:
        cur = d
        ok = True
        for k in keys:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                ok = False
                break
        if ok:
            return cur
    return None


def _walk(obj, depth, seen_ids, out):
    """Recursively find dicts that look like reel entries."""
    if depth > 12:
        return
    if isinstance(obj, dict):
        oid = id(obj)
        if oid in seen_ids:
            return
        seen_ids.add(oid)
        sc = obj.get("shortcode") or obj.get("code")
        if sc and ("video_versions" in obj or "video_url" in obj) and ("caption" in obj or "user" in obj):
            out.append(obj)
        for v in obj.values():
            _walk(v, depth + 1, seen_ids, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, depth + 1, seen_ids, out)


def extract_reels(payload) -> list:
    out = []
    _walk(payload, 0, set(), out)
    return out


def reel_to_row(r: dict) -> dict:
    user = r.get("user") or {}
    cap = r.get("caption")
    cap_text = ""
    if isinstance(cap, dict):
        cap_text = cap.get("text") or ""
    elif isinstance(cap, str):
        cap_text = cap

    # Music track: several payload shapes across IG web versions.
    music = _get(r,
                 ("music_metadata", "music_info", "music_asset_info"),
                 ("music_metadata", "music_asset_info"),
                 ("clips_metadata", "music_info", "music_asset_info")) or {}
    orig_sound = _get(r, ("clips_metadata", "original_sound_info"),
                      ("music_metadata", "original_sound_info")) or {}

    videos = r.get("video_versions") or []
    videos_sorted = sorted(videos, key=lambda v: v.get("width") or 0, reverse=True)
    urls = [v["url"] for v in videos_sorted if v.get("url")]
    if not urls and r.get("video_url"):
        urls = [r["video_url"]]

    hashtags = list(dict.fromkeys(HASHTAG_RE.findall(cap_text)))

    music_info = None
    title = music.get("title")
    artist = music.get("display_artist") or music.get("artist_name")
    if not title and orig_sound.get("original_audio_title"):
        title = orig_sound["original_audio_title"]
        artist = None
    if title:
        music_info = {"title": title, "artist": artist}

    return {
        "shortcode": r.get("shortcode") or r.get("code"),
        "url": REEL_URL.format(sc=r.get("shortcode") or r.get("code")),
        "username": user.get("username"),
        "user_pk": user.get("pk") or user.get("id"),
        "caption": cap_text,
        "hashtags": hashtags,
        "music": music_info,
        "taken_at": r.get("taken_at"),
        "media_urls": urls,
        "accessibility_caption": _get(r, ("accessibility_caption",),
                                      ("media", "accessibility_caption")),
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }


def current_username(page):
    """Best-effort: which account is logged in right now."""
    script = """
    async () => {
      try {
        const res = await fetch('/api/v1/accounts/current_user/', {
          headers: {'x-ig-app-id': '%s'}
        });
        if (res.status !== 200) return null;
        const j = await res.json();
        return (j && j.user && j.user.username) || null;
      } catch (e) { return null; }
    }
    """ % IG_APP_ID
    try:
        return page.evaluate(script)
    except Exception:
        return None


def login_mode(args):
    from playwright.sync_api import sync_playwright

    print("Opening browser... log in to Instagram manually (handle 2FA yourself).")
    print("Wrong account? Log out in the browser window and log in with the")
    print("intended account -- the script keeps waiting either way.")
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(args.profile),
            channel=args.channel,
            headless=False,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            args=STEALTH_ARGS,
            ignore_default_args=STEALTH_IGNORE,
        )
        context.add_init_script(STEALTH_INIT)
        page = context.new_page()
        for extra in list(context.pages):
            if extra is not page:
                extra.close()
        page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
        deadline = time.time() + 1800
        while time.time() < deadline:
            time.sleep(2)
            if not is_logged_in(context):
                continue
            username = current_username(page)
            label = f" (@{username})" if username else ""
            ans = input(f"Logged in{label} -- save THIS session? [y/N] ").strip().lower()
            if ans in ("y", "yes"):
                export_cookies(context, args.cookies)
                print(f"Cookies exported to {args.cookies}")
                print("You can close the browser; the session persists in ig_profile/.")
                return
            print("OK -- switch accounts in the browser; still waiting...")
        print("Timed out after 30 minutes: no confirmed session.")


def collect_mode(args):
    from playwright.sync_api import sync_playwright

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seen = load_existing(out_path)
    new_rows = []

    def on_response(resp):
        try:
            ctype = resp.headers.get("content-type") or ""
            if "json" not in ctype:
                return
            payload = resp.json()
        except Exception:
            return
        for r in extract_reels(payload):
            row = reel_to_row(r)
            sc = row.get("shortcode")
            if not sc or sc in seen:
                continue
            seen[sc] = row
            new_rows.append(row)
            append_row(out_path, row)
            tags = " ".join("#" + t for t in row["hashtags"][:6])
            print(f"[{len(seen)}] {sc}  @{row['username']}  {tags}")

    print(f"Target: {args.reels} reels, dwell {args.dwell}s "
          f"(+/-{args.jitter}s content-independent jitter). Ctrl-C to stop early.")
    start = time.time()
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(args.profile),
            channel=args.channel,
            headless=args.headless,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            args=STEALTH_ARGS,
            ignore_default_args=STEALTH_IGNORE,
        )
        context.add_init_script(STEALTH_INIT)
        page = context.new_page()
        for extra in list(context.pages):
            if extra is not page:
                extra.close()
        page.on("response", on_response)
        page.goto(args.start_url, wait_until="domcontentloaded")
        time.sleep(5)  # let the viewer load and the first reel start playing

        try:
            while len(seen) < args.reels:
                if args.minutes and (time.time() - start) > args.minutes * 60:
                    print("Time cap reached.")
                    break
                if "accounts/login" in page.url:
                    print("WARNING: Instagram shows a login wall. "
                          "Re-run `--login` and try again.")
                    break
                page.keyboard.press("ArrowDown")
                dwell = args.dwell
                if args.jitter > 0:
                    dwell += random.uniform(-args.jitter, args.jitter)
                time.sleep(max(0.5, dwell))
        except KeyboardInterrupt:
            print("\nInterrupted.")

        export_cookies(context, args.cookies)

        if args.account_categories:
            enrich_authors(page, new_rows, seen)

        # Rewrite the jsonl with any enriched fields.
        with open(out_path, "w", encoding="utf-8") as f:
            for row in seen.values():
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    summarize(seen, new_rows)

    if args.download:
        download_rows(new_rows, args.cookies)


def enrich_authors(page, new_rows, seen):
    """Fetch each author's business category + follower count.

    NOTE: these profile lookups are a mild preference signal to Instagram's
    algorithm -- only use this on a run where that tradeoff is accepted.
    """
    from playwright.sync_api import sync_playwright  # noqa: F401  (context check only)

    by_author = {}
    for sc in seen:
        u = seen[sc].get("username")
        if u:
            by_author.setdefault(u, []).append(sc)

    script = """
    async (username) => {
      try {
        const res = await fetch(
          '/api/v1/users/web_profile_info/?username=' + encodeURIComponent(username),
          {headers: {'x-ig-app-id': '%s'}}
        );
        if (res.status !== 200) return null;
        const j = await res.json();
        const u = (j && j.data && j.data.user) || {};
        return {
          category: u.category_name || null,
          followers: u.follower_count
            || (u.edge_followed_by && u.edge_followed_by.count) || null
        };
      } catch (e) { return null; }
    }
    """ % IG_APP_ID

    done = 0
    for username, scs in by_author.items():
        info = page.evaluate(script, username)
        if info:
            for sc in scs:
                seen[sc]["account_category"] = info.get("category")
                seen[sc]["author_followers"] = info.get("followers")
        done += 1
        if done % 10 == 0:
            print(f"Enriched {done}/{len(by_author)} authors...")
        time.sleep(1.0)


def download_rows(rows, cookies_path):
    """Download reel mp4s with yt-dlp using the exported session cookies."""
    if not rows:
        print("Nothing new to download.")
        return
    # Strip dead proxy vars (this machine's 127.0.0.1:10887) from the child env.
    env = {k: v for k, v in os.environ.items()
           if k.lower() not in ("http_proxy", "https_proxy", "all_proxy", "no_proxy")}
    archive = Path(__file__).parent / "videos" / "ig_downloaded.txt"
    ok = fail = 0
    for row in rows:
        cmd = ["yt-dlp", "--no-update", "--no-warnings", "--no-playlist",
               "--cookies", str(cookies_path),
               "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
               "-o", str(Path(__file__).parent / "videos" / "ig_%(id)s.%(ext)s"),
               "--download-archive", str(archive),
               "--print", "after_move:filepath",
               row["url"]]
        try:
            r = subprocess.run(cmd, env=env, capture_output=True, text=True,
                               timeout=600)
            if r.returncode == 0 and r.stdout.strip():
                ok += 1
                print(f"downloaded {row['shortcode']} -> {r.stdout.strip().splitlines()[-1]}")
            else:
                fail += 1
                print(f"FAILED {row['shortcode']}: "
                      f"{(r.stderr or '').strip().splitlines()[-1] if r.stderr else 'exit ' + str(r.returncode)}")
        except subprocess.TimeoutExpired:
            fail += 1
            print(f"TIMEOUT {row['shortcode']}")
    print(f"Download summary: {ok} ok, {fail} failed.")


def summarize(seen, new_rows):
    hashtags = Counter(t for r in seen.values() for t in r["hashtags"])
    authors = {r["username"] for r in seen.values() if r.get("username")}
    with_music = sum(1 for r in seen.values() if r.get("music"))
    print("\n=== Session summary ===")
    print(f"reels in pool: {len(seen)}  (new this run: {len(new_rows)})")
    print(f"unique authors: {len(authors)}")
    print(f"reels with music track: {with_music}/{len(seen)}")
    print(f"top hashtags: {', '.join('#' + t + ':' + str(n) for t, n in hashtags.most_common(10)) or '(none)'}")


def main():
    ap = argparse.ArgumentParser(description="Cold-account Instagram Reels collector (Plan A).")
    ap.add_argument("--login", action="store_true",
                    help="open browser, log in manually, save the session, exit")
    ap.add_argument("--reels", type=int, default=50, help="stop after N unique reels (default 50)")
    ap.add_argument("--dwell", type=float, default=5.0, help="fixed dwell per reel in seconds (default 5)")
    ap.add_argument("--jitter", type=float, default=0.4,
                    help="content-independent +/- jitter on dwell (default 0.4; 0 = strict)")
    ap.add_argument("--minutes", type=float, default=None, help="hard time cap in minutes")
    ap.add_argument("--profile", type=Path, default=Path("ig_profile"),
                    help="persistent browser profile dir (default ig_profile/)")
    ap.add_argument("--out", type=Path, default=Path("videos/ig_captured.jsonl"),
                    help="capture output (default videos/ig_captured.jsonl)")
    ap.add_argument("--cookies", type=Path, default=None,
                    help="Netscape cookie export path (default <profile>/cookies.txt)")
    ap.add_argument("--channel", default="msedge", choices=["msedge", "chrome", "chromium"],
                    help="browser to drive (default msedge = installed Edge, no download)")
    ap.add_argument("--headless", action="store_true", help="run headless (less stealthy)")
    ap.add_argument("--start-url", default="https://www.instagram.com/reels/",
                    help="feed start page (default the Reels tab)")
    ap.add_argument("--account-categories", action="store_true",
                    help="enrich authors with business category/followers "
                         "(profile lookups = mild preference signal, off for cold runs)")
    ap.add_argument("--download", action="store_true",
                    help="yt-dlp download every reel captured this run")
    ap.add_argument("--download-only", action="store_true",
                    help="skip the browser: download all reels in the existing jsonl")
    args = ap.parse_args()

    if args.cookies is None:
        args.cookies = args.profile / "cookies.txt"
    args.profile.mkdir(parents=True, exist_ok=True)

    if args.download_only:
        rows = list(load_existing(Path(args.out)).values())
        download_rows(rows, args.cookies)
        return

    try:
        import playwright  # noqa: F401
    except ImportError:
        print("playwright is not installed. Run:  pip install playwright")
        print("(No browser download needed: --channel msedge uses your installed Edge.)")
        sys.exit(1)

    if args.login:
        login_mode(args)
    else:
        collect_mode(args)


if __name__ == "__main__":
    main()
