#!/usr/bin/env python3
"""Batch-download short videos for the experiment into videos/, then refresh the manifest.

Wraps yt-dlp (which does the actual crawling/pagination/downloading) with
experiment-friendly defaults:

  - fetches up to --count videos per source
  - skips clips longer than --max-duration seconds (default 90) to keep
    the stimulus stream short-form
  - caps resolution at 1080p, keeps H.264/AAC so the scanner browser can play
  - remembers what was already downloaded (videos/downloaded.txt) so reruns
    only fetch new clips
  - regenerates videos/manifest.js at the end

Examples:
  python3 download_videos.py "https://www.tiktok.com/@account" --count 50
  python3 download_videos.py --urls urls.txt --count 20
  python3 download_videos.py URL1 URL2 --count 30 --max-duration 60
  python3 download_videos.py --feed 50 --cookies-from-browser edge
      (crawls the logged-in For You feed — videos from many authors)
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
VDIR = os.path.join(HERE, "videos")
ARCHIVE = os.path.join(VDIR, "downloaded.txt")
EXTS = (".mp4", ".webm", ".m4v")


def run(cmd, env=None):
    """Run a command, streaming its output. Returns True on success.

    yt-dlp exits non-zero when --max-downloads stops the crawl early, even
    though every download up to the cap succeeded, so treat that marker as
    success too.
    """
    proc = subprocess.Popen(
        cmd, cwd=HERE, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    reached_cap = False
    for line in proc.stdout:
        print(line, end="", flush=True)
        if "Maximum number of downloads reached" in line:
            reached_cap = True
    proc.wait()
    return proc.returncode == 0 or reached_cap


def read_sources(urls_file):
    if not urls_file:
        return []
    with open(urls_file, encoding="utf-8") as fp:
        return [ln.strip() for ln in fp if ln.strip() and not ln.startswith("#")]


# --- For You feed crawling ------------------------------------------------
# With a logged-in session, TikTok's web API serves the personalized feed
# (videos from many different authors). We page through it, collect
# single-video URLs, and hand them to yt-dlp in one batch.
FEED_API = "https://www.tiktok.com/api/recommend/item_list/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
FEED_COOKIES = os.path.join(tempfile.gettempdir(), "tt_feed_cookies.txt")


def export_cookies(browser, env=None):
    """Export the browser's TikTok cookies to a Netscape file for the feed API.

    Uses --flat-playlist + --playlist-items so extraction touches only the
    first profile item and finishes in seconds (otherwise yt-dlp would page
    through the whole @tiktok profile before writing the cookie file).
    """
    subprocess.run(
        ["yt-dlp", "--cookies-from-browser", browser, "--cookies", FEED_COOKIES,
         "--skip-download", "--flat-playlist", "--playlist-items", "1",
         "-O", "%(id)s", "https://www.tiktok.com/@tiktok"],
        cwd=HERE, env=env, capture_output=True)


def collect_feed_videos(count, max_duration, per_author=3, env=None):
    """Page through the logged-in For You feed, collecting single-video URLs.

    Returns up to `count` + 15 items (margin for clips that fail to download),
    each a dict {url, author, nick, desc}; at most `per_author` clips from any
    one author, skipping photo/live items and clips longer than `max_duration`
    (0 = no limit). Author metadata is recorded to videos/authors.json so the
    manifest can show @author labels.
    """
    items_out, seen_ids, seen_authors = [], set(), {}
    cursor = 0
    while len(items_out) < count + 15 and cursor <= 330:
        url = f"{FEED_API}?aid=1988&count=30&cursor={cursor}"
        proc = subprocess.run(
            ["curl", "-s", "-b", FEED_COOKIES, "-A", UA,
             "-H", "Referer: https://www.tiktok.com/", url],
            capture_output=True, text=True, env=env)
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            break
        items = data.get("itemList") or []
        if not items:
            break
        cursor += len(items)
        for it in items:
            vid = it.get("id")
            author = (it.get("author") or {})
            uname = author.get("uniqueId")
            duration = (it.get("video") or {}).get("duration")
            if not vid or not uname or not duration:
                continue  # photo/live/ads have no video duration
            if vid in seen_ids or seen_authors.get(uname, 0) >= per_author:
                continue
            if max_duration > 0 and duration > max_duration:
                continue
            seen_ids.add(vid)
            seen_authors[uname] = seen_authors.get(uname, 0) + 1
            items_out.append({
                "url": f"https://www.tiktok.com/@{uname}/video/{vid}",
                "author": uname,
                "nick": author.get("nickname") or "",
                "desc": it.get("desc") or "",
            })
    return items_out


def record_authors(source_items, feed_mode=False):
    """Merge per-video author metadata into videos/authors.json.

    In feed mode `source_items` are the dicts from collect_feed_videos (with
    author/nick/desc). Otherwise they are plain URLs and the author is parsed
    from the @username path segment. Existing entries are kept.
    """
    path = os.path.join(VDIR, "authors.json")
    try:
        with open(path, encoding="utf-8") as fp:
            meta = json.load(fp)
    except (OSError, json.JSONDecodeError):
        meta = {}
    if feed_mode:
        for d in source_items:
            vid = d["url"].rstrip("/").split("/")[-1]
            meta[vid] = {"author": d["author"], "nick": d["nick"], "desc": d["desc"]}
    else:
        for u in source_items:
            m = re.match(r"https?://(?:www\.)?tiktok\.com/@([^/]+)/video/(\d+)", u)
            if m:
                meta[m.group(2)] = {"author": m.group(1), "nick": "", "desc": ""}
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(meta, fp, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser(
        description="Auto-download N short videos per source into videos/ and refresh the manifest.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("sources", nargs="*", help="TikTok profile or single-video URLs")
    ap.add_argument("--feed", type=int, default=0,
                    help="crawl the logged-in For You feed for N videos from many "
                         "authors (requires --cookies-from-browser)")
    ap.add_argument("--urls", help="text file with one URL per line (# = comment)")
    ap.add_argument("--count", type=int, default=50, help="max videos to download per source")
    ap.add_argument("--max-duration", type=int, default=90,
                    help="skip clips longer than N seconds (0 = no limit)")
    ap.add_argument("--max-resolution", type=int, default=1080,
                    help="cap video height (0 = no cap)")
    ap.add_argument("--proxy", default=None,
                    help="e.g. http://127.0.0.1:7890 (default: use environment vars)")
    ap.add_argument("--no-proxy", action="store_true",
                    help="ignore http_proxy/https_proxy environment vars (use direct connection)")
    ap.add_argument("--cookies-from-browser", default=None,
                    help="browser name (e.g. chrome) for videos that require login")
    ap.add_argument("--skip-manifest", action="store_true",
                    help="do not regenerate videos/manifest.js afterwards")
    args = ap.parse_args()

    sources = list(args.sources) + read_sources(args.urls)

    env = os.environ.copy()
    if args.no_proxy:
        for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
                  "all_proxy", "ALL_PROXY"):
            env.pop(k, None)

    if args.feed > 0:
        if not args.cookies_from_browser:
            ap.error("--feed needs a logged-in session: pass --cookies-from-browser")
        print(f"=== For You feed (collecting {args.feed} videos) ===", flush=True)
        export_cookies(args.cookies_from_browser, env=env)
        sources = collect_feed_videos(args.feed, args.max_duration, env=env)
        if not sources:
            print("Feed returned no videos (session expired? sign in again).", flush=True)
            sys.exit(1)
        n_authors = len({d["author"] for d in sources})
        print(f"Collected {len(sources)} video URLs from {n_authors} authors.", flush=True)

    if not sources:
        ap.error("provide at least one TikTok URL (profile or video), --urls <file>, "
                 "or --feed N")

    sort = f"res:{args.max_resolution}" if args.max_resolution > 0 else "res:1080"
    # In feed mode the cap is --feed itself; otherwise --count per source.
    max_downloads = args.feed if args.feed > 0 else args.count
    base = [
        "yt-dlp",
        "--download-archive", ARCHIVE,          # skip already-downloaded videos
        "-S", f"{sort},vcodec:h264,ext:mp4:m4a",  # H.264/AAC, capped resolution
        "-o", "videos/%(id)s.%(ext)s",          # numeric TikTok id as filename
        "--restrict-filenames",
        "--max-downloads", str(max_downloads),
    ]
    if args.max_duration > 0:
        base += ["--match-filter", f"duration <= {args.max_duration}"]
    if args.proxy:
        base += ["--proxy", args.proxy]
    if args.cookies_from_browser:
        base += ["--cookies-from-browser", args.cookies_from_browser]

    failed = []
    if args.feed > 0:
        # One batch invocation with the logged-in session:
        # --max-downloads caps it at args.count.
        batch = base + ["--cookies-from-browser", args.cookies_from_browser] + [d["url"] for d in sources]
        if not run(batch, env=env):
            failed.append("For You feed")
        record_authors(sources, feed_mode=True)
    else:
        for src in sources:
            print(f"\n=== {src} ===", flush=True)
            if not run(base + [src], env=env):
                failed.append(src)
        record_authors(sources, feed_mode=False)

    if not args.skip_manifest:
        print("\n=== regenerating manifest ===", flush=True)
        run([sys.executable, os.path.join(HERE, "generate_manifest.py")])

    n = sum(
        1 for f in os.listdir(VDIR)
        if f.lower().endswith(EXTS) and not f.startswith(".")
    )
    print(f"\nDone. {n} video file(s) in videos/.")
    if failed:
        print(f"Failed sources: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
