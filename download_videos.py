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
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VDIR = os.path.join(HERE, "videos")
ARCHIVE = os.path.join(VDIR, "downloaded.txt")
EXTS = (".mp4", ".webm", ".m4v")


def run(cmd, env=None):
    return subprocess.run(cmd, cwd=HERE, env=env).returncode


def read_sources(urls_file):
    if not urls_file:
        return []
    with open(urls_file, encoding="utf-8") as fp:
        return [ln.strip() for ln in fp if ln.strip() and not ln.startswith("#")]


def main():
    ap = argparse.ArgumentParser(
        description="Auto-download N short videos per source into videos/ and refresh the manifest.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("sources", nargs="*", help="TikTok profile or single-video URLs")
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
    if not sources:
        ap.error("provide at least one TikTok URL (profile or video) or --urls <file>")

    env = os.environ.copy()
    if args.no_proxy:
        for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
                  "all_proxy", "ALL_PROXY"):
            env.pop(k, None)

    sort = f"res:{args.max_resolution}" if args.max_resolution > 0 else "res:1080"
    base = [
        "yt-dlp",
        "--download-archive", ARCHIVE,          # skip already-downloaded videos
        "-S", f"{sort},ext:mp4:m4a",            # H.264/AAC, capped resolution
        "-o", "videos/%(id)s.%(ext)s",          # numeric TikTok id as filename
        "--restrict-filenames",
        "--max-downloads", str(args.count),
    ]
    if args.max_duration > 0:
        base += ["--match-filter", f"duration <= {args.max_duration}"]
    if args.proxy:
        base += ["--proxy", args.proxy]
    if args.cookies_from_browser:
        base += ["--cookies-from-browser", args.cookies_from_browser]

    failed = []
    for src in sources:
        print(f"\n=== {src} ===", flush=True)
        if run(base + [src], env=env) != 0:
            failed.append(src)

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
