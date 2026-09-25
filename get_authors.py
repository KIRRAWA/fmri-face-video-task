#!/usr/bin/env python3
"""Rebuild videos/authors.json — TikTok video ID -> {author, nick, desc}.

Two sources, in order:
  1. the logged-in For You feed (same crawl download_videos.py --feed uses)
     — also carries the caption (desc);
  2. the embed page https://www.tiktok.com/embed/v2/{id} for everything the
     feed misses — carries author + nickname but no caption.
Videos matched by neither get empty fields so the UI can fall back to @unknown.
Future downloads update this file automatically (download_videos.py records
the author at download time).

Run:  python3 get_authors.py --cookies-from-browser edge --pages 10
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VDIR = os.path.join(HERE, "videos")
AUTHORS = os.path.join(VDIR, "authors.json")
EXTS = (".mp4", ".webm", ".m4v")

sys.path.insert(0, HERE)
from download_videos import export_cookies, FEED_COOKIES, FEED_API, UA

# The embed page puts the main video's author in an "authorInfos" block with a
# fixed key order; the viewer block never uses that exact shape, so this regex
# cannot accidentally pick up the logged-in account.
AUTHOR_RE = re.compile(
    r'"authorInfos":\{"secUid":"[^"]*","userId":"[^"]*",'
    r'"uniqueId":"([^"]+)","nickName":"([^"]+)"')


def crawl_feed(pages, env):
    """Page through the logged-in For You feed; return {video_id: {author, nick, desc}}."""
    ids = {}
    cursor = 0
    for _ in range(pages):
        url = f"{FEED_API}?aid=1988&count=30&cursor={cursor}"
        proc = subprocess.run(
            ["curl", "-s", "-b", FEED_COOKIES, "-A", UA,
             "-H", "Referer: https://www.tiktok.com/", url],
            capture_output=True, text=True, env=env)
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            print(f"  feed page at cursor={cursor} returned no JSON — stopping", flush=True)
            break
        items = data.get("itemList") or []
        if not items:
            break
        cursor += len(items)
        for it in items:
            vid = it.get("id")
            author = (it.get("author") or {})
            if vid and author.get("uniqueId"):
                ids[vid] = {"author": author["uniqueId"],
                            "nick": author.get("nickname") or "",
                            "desc": it.get("desc") or ""}
        print(f"  cursor={cursor:>4}  collected={len(ids)}", flush=True)
        if not data.get("hasMore", False):
            break
    return ids


def fetch_embed(vid, env):
    """Get {author, nick} for one video from the embed page ("" on failure)."""
    proc = subprocess.run(
        ["curl", "-sL", "-b", FEED_COOKIES, "-A", UA,
         "https://www.tiktok.com/embed/v2/" + vid],
        capture_output=True, text=True, env=env)
    m = AUTHOR_RE.search(proc.stdout or "")
    if not m:
        return {"author": "", "nick": "", "desc": ""}
    return {"author": m.group(1), "nick": m.group(2), "desc": ""}


def pool_ids():
    return sorted(
        os.path.splitext(f)[0]
        for f in os.listdir(VDIR)
        if f.lower().endswith(EXTS) and not f.startswith(".")
    )


def main():
    ap = argparse.ArgumentParser(description="Rebuild videos/authors.json.")
    ap.add_argument("--cookies-from-browser", default="edge",
                    help="browser holding a logged-in TikTok session (default: edge)")
    ap.add_argument("--pages", type=int, default=10,
                    help="max feed pages to crawl (~30 items per page)")
    ap.add_argument("--no-embed", action="store_true",
                    help="skip the per-video embed lookups")
    args = ap.parse_args()

    env = os.environ.copy()
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
              "all_proxy", "ALL_PROXY"):
        env.pop(k, None)

    print("=== exporting cookies ===", flush=True)
    export_cookies(args.cookies_from_browser, env=env)
    print("=== crawling For You feed ===", flush=True)
    feed = crawl_feed(args.pages, env)

    ids = pool_ids()
    authors = {}
    missing = [vid for vid in ids if vid not in feed]
    for vid in ids:
        if vid in feed:
            authors[vid] = feed[vid]
    if missing and not args.no_embed:
        print(f"=== embed lookup for {len(missing)} unmatched videos ===", flush=True)
        for n, vid in enumerate(missing, 1):
            authors[vid] = fetch_embed(vid, env)
            a = authors[vid]["author"] or "unknown"
            print(f"  {n:>3}/{len(missing)}  {vid}  @{a}", flush=True)
            time.sleep(0.4)
    elif missing:
        for vid in missing:
            authors[vid] = {"author": "", "nick": "", "desc": ""}

    with open(AUTHORS, "w", encoding="utf-8") as fp:
        json.dump(authors, fp, ensure_ascii=False, indent=1)

    ok = sum(1 for v in authors.values() if v["author"])
    print(f"\nWrote videos/authors.json — {ok}/{len(ids)} pool videos have an author.", flush=True)
    for vid in ids:
        a = authors[vid]
        flag = "  " if a["author"] else "??"
        print(f"  {flag} {vid}  @{a['author'] or 'unknown'}  {a['desc'][:45]}", flush=True)


if __name__ == "__main__":
    main()
