#!/usr/bin/env python3
"""Local server + command-line control for the face-recognition video task.

Two ways to run the task:
  1. Browser mode: open index.html directly (file://) — everything works
     except folder scanning (browsers cannot list local directories) and
     timeline thumbnails (they are served from /frames/...).
  2. Server mode (this script): a tiny stdlib-only server lets the settings
     page scan REAL folder paths, import a video pool from anywhere on disk
     (e.g. a reel-crawler review_videos folder, with author + like counts),
     serve run-timeline thumbnails, and archive run logs server-side. The
     CLI can also start a run without touching the settings page.

Every run end (countdown or Q key) archives server-side under data/:
    data/<subject>_<stamp>.csv          millisecond event table
    data/events.jsonl                   full payload per run (timeline HTML
                                        stored as its own file, see below)
    data/timeline_<subject>_<stamp>.html  self-contained zoomable run timeline

Commands (run from this directory):
    python3 task.py serve [--port 8000] [--fullscreen] [--no-open]
        Start the local server (static files + folder-scan APIs). With
        --fullscreen the browser window opens fullscreen; on the page, Esc
        exits fullscreen (the run is unaffected), F4 re-enters it.

    python3 task.py run [options]
        Set options, write config.js (auto-start), then serve. The browser
        opens fullscreen by default.
        Options:
          --center PATH|URL      center documentary (default: center/center.mp4)
          --subject P01          subject id
          --duration MIN         run length in minutes (default 10)
          --trigger wait|immediate   wait for the trigger key, or start at once
          --trigger-key 5        trigger key (default 5)
          --left-pct N           % chance a random pop-up opens on the LEFT
          --sat-center N         center saturation % (0-200, default 100)
          --vol-center N         center volume % (0-100, default 0)
          --sat-reel N           reel saturation % (0-200, default 100)
          --vol-reel N           reel volume % (0-100, default 0)
          --pop-trigger manual|auto
          --pop-interval SEC     auto pop-up interval (seconds)
          --seek / --no-seek     allow / forbid dragging progress bars
          --fullscreen           start the browser fullscreen (default)
          --no-fullscreen        start the browser in a normal window
          --no-open              do not open the browser

    python3 task.py folders add|list|remove <path>
        Register / list / unregister folder paths for scanning and import.

    python3 task.py pools
        List discovered video pools (registered folders + built-in videos/).

    python3 task.py import <path>
        Import a folder as the active pool: rewrites videos/manifest.js so the
        page plays /media/... URLs served from that folder (no copying).

    python3 task.py reels-sync [--no-download] [--include-excluded]
            [--crawler PATH] [--cookies FILE] [--max N] [--delay SEC]
        Pull the reel-crawler review-team pool (Instagram reels) into the
        built-in videos/ pool: downloads missing videos with yt-dlp and
        rewrites videos/manifest.js from the pool metadata (author, likes,
        caption). Only pool shortcodes ever enter the manifest.

    python3 task.py config show|set KEY=VALUE [KEY=VALUE ...]
        Show or update the CLI settings stored in config.json.

Settings set via `run` or `config set` are written to config.js, which
index.html loads on top of its saved settings (CLI wins). `run` additionally
sets autoStart so the experiment starts without any clicks.
See CLI-GUIDE.md for the full walkthrough.

Timeline thumbnails: /frames/<shortcode>/fNNN.jpg is served read-only from
FRAMES_ROOT (default: the sibling reel-crawler/review_frames folder; override
with the FMRI_FRAMES_ROOT environment variable).

Metadata import: video files are matched to author + like counts from, in
order of preference:
    pool.json                review_team.py merged pool ({url: {username, likes, ...}})
    feed_collection.sqlite   crawler stores (feed_items: url, username, like_count)
    meta.json                review_capture per-item files (review_frames/<code>/meta.json)
    authors.json             legacy TikTok metadata ({id: {author, nick, desc}})
    *.csv                    exports with url / username / like_count columns
"""
import argparse
import csv
import datetime as _dt
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
CONFIG_JS = os.path.join(HERE, "config.js")
MANIFEST = os.path.join(HERE, "videos", "manifest.js")
DATA_DIR = os.path.join(HERE, "data")
VIDEO_EXTS = (".mp4", ".webm", ".m4v", ".mov")
MAX_SCAN_DEPTH = 3          # how deep import scans under the chosen folder
# First-frame thumbnails for the run timeline tooltips come from the sibling
# reel-crawler's review_frames/<shortcode>/f000.jpg store (served read-only
# at /frames/...). Override with the FMRI_FRAMES_ROOT environment variable.
FRAMES_ROOT = os.environ.get("FMRI_FRAMES_ROOT") or os.path.join(
    os.path.dirname(HERE), "reel-crawler", "review_frames")
MAX_TIMELINE_BYTES = 20 * 1024 * 1024   # sanity cap for archived timeline HTML
_events_lock = threading.Lock()

SETTING_KEYS = (
    "centervideo", "subject", "note", "durationMin", "trigger", "triggerkey",
    "keya", "keyb", "decor", "popleft", "popside", "poptrigger", "popinterval",
    "satcenter", "volcenter", "satreel", "volreel", "allowseek",
)


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
def load_config():
    cfg = {"folders": [], "active_pool": None, "settings": {}, "autoStart": False}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as fp:
            saved = json.load(fp)
        for k in cfg:
            if k in saved:
                cfg[k] = saved[k]
    except (OSError, json.JSONDecodeError):
        pass
    return cfg


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as fp:
        json.dump(cfg, fp, ensure_ascii=False, indent=2)


def write_config_js(cfg, auto_fullscreen=False):
    """config.js is loaded by index.html via a <script> tag; its settings
    override whatever is saved in localStorage (CLI has the last word).
    auto_fullscreen makes the page request DOM fullscreen on the first user
    gesture (key press or Start click) after the browser opens."""
    payload = {
        "autoStart": bool(cfg.get("autoStart")),
        "autoFullscreen": bool(auto_fullscreen),
        "settings": {k: v for k, v in (cfg.get("settings") or {}).items()
                     if v is not None},
    }
    js = ("// Auto-generated by task.py — loaded by index.html on top of its\n"
          "// own saved settings (CLI wins). Regenerate: python3 task.py config set ...\n"
          "window.TASK_CONFIG = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";\n")
    with open(CONFIG_JS, "w", encoding="utf-8") as fp:
        fp.write(js)


def launch_browser(url, fullscreen=False):
    """Open the task page. fullscreen=True starts the browser window with
    --start-fullscreen; the page then takes over (Esc exits fullscreen
    without ending the run, F4 re-enters). macOS prefers `open -na` with
    args so an already-running Edge hands the URL off cleanly."""
    flag = ["--start-fullscreen"] if fullscreen else []
    if sys.platform == "darwin":
        try:
            subprocess.Popen(["open", "-na", "Microsoft Edge", "--args"] + flag + [url],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except OSError:
            pass
    for name, binary in (("Microsoft Edge", "msedge"),
                         ("Google Chrome", "google-chrome"),
                         ("Chromium", "chromium")):
        path = shutil.which(binary) or shutil.which(name)
        if path:
            try:
                subprocess.Popen([path] + flag + [url],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except OSError:
                continue
    webbrowser.open(url)


# --------------------------------------------------------------------------
# Pool scanning and metadata matching
# --------------------------------------------------------------------------
def shortcode_from_url(url):
    if not url:
        return ""
    return url.rstrip("/").split("/")[-1].split("?")[0]


def load_meta_sources(root):
    """Return a dict mapping a shortcode/video-id to {author, likes, desc}
    collected from every metadata source under root."""
    by_id = {}
    root = os.path.abspath(root)

    def merge(key, meta):
        if not key:
            return
        slot = by_id.setdefault(key, {})
        if meta.get("author") and not slot.get("author"):
            slot["author"] = meta["author"]
        if meta.get("likes") is not None and slot.get("likes") is None:
            slot["likes"] = int(meta["likes"])
        if meta.get("desc") and not slot.get("desc"):
            slot["desc"] = meta["desc"]

    # 1. review_team pool.json — {url: {code, username, likes, caption, ...}}
    for pj in [os.path.join(root, "pool.json"),
               os.path.join(os.path.dirname(root), "pool.json")]:
        try:
            with open(pj, encoding="utf-8") as fp:
                pool = json.load(fp)
            if isinstance(pool, dict):
                for url, item in pool.items():
                    if isinstance(item, dict):
                        merge(shortcode_from_url(url), {
                            "author": item.get("username"),
                            "likes": item.get("likes"),
                            "desc": item.get("caption"),
                        })
        except (OSError, json.JSONDecodeError):
            pass

    # 2. crawler stores — feed_collection.sqlite (feed_items table)
    for dbp in [os.path.join(root, "feed_collection.sqlite"),
                os.path.join(os.path.dirname(root), "feed_collection.sqlite")]:
        try:
            con = sqlite3.connect(dbp)
            cur = con.execute(
                "SELECT url, username, like_count, caption FROM feed_items")
            for url, username, likes, caption in cur.fetchall():
                merge(shortcode_from_url(url), {
                    "author": username, "likes": likes, "desc": caption})
            con.close()
        except (sqlite3.Error, OSError):
            pass

    # 3. review_capture meta.json files — review_frames/<code>/meta.json
    for base, dirs, _ in os.walk(root):
        depth = base[len(root):].count(os.sep)
        if depth >= MAX_SCAN_DEPTH:
            dirs[:] = []
            continue
        mp = os.path.join(base, "meta.json")
        try:
            with open(mp, encoding="utf-8") as fp:
                item = json.load(fp)
            if isinstance(item, dict):
                merge(shortcode_from_url(item.get("url") or ""), {
                    "author": item.get("username"),
                    "likes": item.get("likes"),
                    "desc": item.get("caption"),
                })
        except (OSError, json.JSONDecodeError):
            pass

    # 4. legacy TikTok metadata — authors.json ({video_id: {author, nick, desc}})
    aj = os.path.join(root, "authors.json")
    try:
        with open(aj, encoding="utf-8") as fp:
            authors = json.load(fp)
        if isinstance(authors, dict):
            for vid, meta in authors.items():
                if isinstance(meta, dict):
                    merge(str(vid), {
                        "author": meta.get("author"),
                        "likes": meta.get("likes"),
                        "desc": meta.get("desc") or meta.get("nick"),
                    })
    except (OSError, json.JSONDecodeError):
        pass

    # 5. CSV exports — columns url / username / like_count / caption
    for base, dirs, files in os.walk(root):
        depth = base[len(root):].count(os.sep)
        if depth >= MAX_SCAN_DEPTH:
            dirs[:] = []
        for fn in files:
            if not fn.lower().endswith(".csv"):
                continue
            try:
                with open(os.path.join(base, fn), newline="", encoding="utf-8") as fp:
                    for row in csv.DictReader(fp):
                        merge(shortcode_from_url(row.get("url") or ""), {
                            "author": row.get("username"),
                            "likes": _to_int(row.get("like_count") or row.get("likes")),
                            "desc": row.get("caption"),
                        })
            except (OSError, csv.Error, UnicodeDecodeError):
                pass

    return by_id


def _to_int(v):
    try:
        return int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return None


def scan_folder(path):
    """Find video files + matching metadata under path. Returns
    (name, videos) where videos is [{src_rel, author, likes, desc}]."""
    path = os.path.abspath(path)
    by_id = load_meta_sources(path)
    rel_files = []
    for base, dirs, files in os.walk(path):
        depth = base[len(path):].count(os.sep)
        if depth >= MAX_SCAN_DEPTH:
            dirs[:] = []
        for fn in sorted(files):
            if fn.lower().endswith(VIDEO_EXTS) and not fn.startswith("."):
                rel_files.append(os.path.relpath(os.path.join(base, fn), path))
    videos = []
    for rel in rel_files:
        stem = os.path.splitext(os.path.basename(rel))[0]
        meta = by_id.get(stem, {})
        videos.append({
            "src": rel.replace(os.sep, "/"),
            "author": meta.get("author", ""),
            "likes": meta.get("likes"),
            "desc": meta.get("desc", ""),
        })
    return os.path.basename(path.rstrip(os.sep)) or "pool", videos


def pool_slug(name, used):
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-") or "pool"
    i, cand = 2, slug
    while cand in used:
        cand = f"{slug}-{i}"
        i += 1
    return cand


def write_manifest(pool_name, videos, base_path):
    """Rewrite videos/manifest.js with /media/<pool>/... URLs served by
    task.py from the source folder (nothing is copied)."""
    entries = []
    for v in videos:
        e = {
            "src": f"/media/{pool_name}/{v['src']}",
            "author": v["author"],
            "nick": v["author"],
            "desc": v["desc"],
        }
        if v["likes"] is not None:
            e["likes"] = v["likes"]
        entries.append(e)
    header = (
        "// Video manifest (auto-generated by task.py — do not edit by hand;\n"
        f"// pool \"{pool_name}\" imported from {base_path}).\n"
        "// Served over HTTP by task.py; run python3 generate_manifest.py to\n"
        "// switch back to the built-in videos/ folder.\n"
        "// Each entry: { src, author, nick, desc[, likes] } — likes is shown\n"
        "// Instagram-style on the right side of the screen.\n"
    )
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as fp:
        fp.write(header + "window.VIDEO_MANIFEST = " +
                 json.dumps(entries, ensure_ascii=False, indent=1) + ";\n")
    return entries


def import_folder(path):
    cfg = load_config()
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        raise SystemExit(f"Not a directory: {path}")
    if path not in cfg["folders"]:
        cfg["folders"].append(path)
    name = pool_slug(os.path.basename(path.rstrip(os.sep)), set())
    pool_name, videos = scan_folder(path)
    if not videos:
        raise SystemExit(f"No video files found under {path}")
    write_manifest(pool_name, videos, path)
    cfg["active_pool"] = {"name": pool_name, "path": path}
    save_config(cfg)
    return pool_name, len(videos)


def list_pools():
    """All pools the page can import: registered folders + built-in videos/."""
    cfg = load_config()
    pools = []
    active = (cfg.get("active_pool") or {}).get("name")
    builtin = [f for f in os.listdir(os.path.join(HERE, "videos"))
               if f.lower().endswith(VIDEO_EXTS)] if os.path.isdir(
                   os.path.join(HERE, "videos")) else []
    pools.append({
        "name": "videos (built-in)", "path": os.path.join(HERE, "videos"),
        "videos": len(builtin),
        "active": active is None, "imported": False,
    })
    seen = set()
    for folder in cfg.get("folders", []):
        if not os.path.isdir(folder):
            continue
        raw_name, vids = scan_folder(folder)
        name = pool_slug(raw_name, set())
        if not vids or name in seen:
            continue
        seen.add(name)
        pools.append({
            "name": name, "path": folder, "videos": len(vids),
            "active": active == name, "imported": active == name,
        })
    return pools


# --------------------------------------------------------------------------
# HTTP server
# --------------------------------------------------------------------------
MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".m4v": "video/x-m4v",
    ".mov": "video/quicktime",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
}


def _inside(base, target):
    base = os.path.realpath(base)
    target = os.path.realpath(target)
    return target == base or target.startswith(base + os.sep)


def _safe_name(s):
    """Filesystem-safe subject slug; the original subject is still stored in
    the archived payload and inside the CSV rows."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(s or "subject")).strip("._")[:80] or "subject"


def _unique_base(subject):
    """data/<safe>_<microsecond-stamp> base name, unique even when two runs
    POST in the same second. Caller must hold _events_lock."""
    safe = _safe_name(subject)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    base = f"{safe}_{stamp}"
    n = 2
    while (os.path.exists(os.path.join(DATA_DIR, base + ".csv"))
           or os.path.exists(os.path.join(DATA_DIR, "timeline_" + base + ".html"))):
        base = f"{safe}_{stamp}-{n}"
        n += 1
    return base


def _json(handler, obj, code=200):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    return body


class Handler(BaseHTTPRequestHandler):
    server_version = "face-task/1.0"

    def log_message(self, fmt, *args):  # quieter than the default
        sys.stderr.write("[task.py] %s\n" % (fmt % args))

    def _serve_bytes(self, body, ctype, path):
        fsize = len(body)
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m:
                start = int(m.group(1) or 0)
                end = min(int(m.group(2) or fsize - 1), fsize - 1)
                if start <= end < fsize:
                    self.send_response(206)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{fsize}")
                    self.send_header("Content-Length", str(end - start + 1))
                    self.send_header("Content-Type", ctype)
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()
                    self.wfile.write(body[start:end + 1])
                    return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(fsize))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path):
        if not os.path.isfile(path):
            self.send_error(404)
            return
        with open(path, "rb") as fp:
            self._serve_bytes(fp.read(), MIME.get(os.path.splitext(path)[1].lower(),
                                                  "application/octet-stream"), path)

    def do_GET(self):
        cfg = load_config()
        url = self.path.split("?")[0]

        if url == "/" or url == "":
            self._serve_file(os.path.join(HERE, "index.html"))
        elif url == "/config.js":
            if not os.path.exists(CONFIG_JS):
                write_config_js(cfg)
            self._serve_file(CONFIG_JS)
        elif url.startswith("/media/"):
            # /media/<pool>/<relpath> — only the ACTIVE pool is referenced by
            # the manifest, so match against it exactly.
            rest = url[len("/media/"):]
            pool, _, rel = rest.partition("/")
            active = cfg.get("active_pool") or {}
            if active.get("name") != pool:
                self.send_error(404)
                return
            folder = active.get("path")
            if not folder:
                self.send_error(404)
                return
            target = os.path.join(folder, rel)
            if not _inside(folder, target) or not os.path.isfile(target):
                self.send_error(404)
                return
            self._serve_file(target)
        elif url.startswith("/frames/"):
            # Run-timeline thumbnails: /frames/<shortcode>/fNNN.jpg served
            # read-only from FRAMES_ROOT. Strict regex — no traversal.
            m = re.fullmatch(r"/frames/([A-Za-z0-9_-]{6,})/(f[0-9]{3}\.jpg)", url)
            if not m:
                self.send_error(404)
                return
            target = os.path.join(FRAMES_ROOT, m.group(1), m.group(2))
            if not _inside(FRAMES_ROOT, target) or not os.path.isfile(target):
                self.send_error(404)
                return
            self._serve_file(target)
        elif url == "/api/folders":
            body = _json(self, {
                "folders": [f for f in cfg.get("folders", []) if os.path.isdir(f)],
            })
            self.end_headers(); self.wfile.write(body)
        elif url == "/api/pools":
            body = _json(self, {"pools": list_pools()})
            self.end_headers(); self.wfile.write(body)
        elif url.startswith("/api/"):
            self.send_error(404)
        else:
            # static files inside the task folder only (index.html assets)
            target = os.path.normpath(os.path.join(HERE, url.lstrip("/")))
            if not _inside(HERE, target):
                self.send_error(403)
                return
            self._serve_file(target)

    def do_POST(self):
        cfg = load_config()
        url = self.path.split("?")[0]
        try:
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except (ValueError, json.JSONDecodeError):
            data = {}

        if url == "/api/folders":
            action = data.get("action")
            path = os.path.abspath(os.path.expanduser(str(data.get("path") or "")))
            err = None
            if action == "add":
                if not os.path.isdir(path):
                    err = f"Not a directory: {path}"
                else:
                    if path not in cfg["folders"]:
                        cfg["folders"].append(path)
                        save_config(cfg)
            elif action == "remove":
                cfg["folders"] = [f for f in cfg["folders"] if f != path]
                save_config(cfg)
            body = _json(self, {
                "error": err, "folders": cfg["folders"], "pools": list_pools(),
            })
            self.end_headers(); self.wfile.write(body)
        elif url == "/api/import":
            try:
                name, n = import_folder(str(data.get("path") or ""))
                body = _json(self, {"name": name, "videos": n})
            except SystemExit as exc:
                body = _json(self, {"error": str(exc)})
            self.end_headers(); self.wfile.write(body)
        elif url == "/api/events":
            with _events_lock:
                os.makedirs(DATA_DIR, exist_ok=True)
                rows = data.get("rows") or []
                subject = str(data.get("subject") or "subject")
                base = _unique_base(subject)
                # Optional self-contained timeline HTML: validated loosely
                # (looks like a document, sane size) then archived verbatim.
                timeline_html = data.get("timelineHtml")
                timeline_rel = None
                if (isinstance(timeline_html, str)
                        and len(timeline_html.encode("utf-8")) <= MAX_TIMELINE_BYTES
                        and timeline_html.lstrip().startswith("<!DOCTYPE html")):
                    timeline_rel = f"data/timeline_{base}.html"
                    with open(os.path.join(DATA_DIR, "timeline_" + base + ".html"),
                              "w", encoding="utf-8") as fp:
                        fp.write(timeline_html)
                archive = dict(data)
                archive.pop("timelineHtml", None)   # archived as its own file
                if timeline_rel:
                    archive["timelineFile"] = timeline_rel
                with open(os.path.join(DATA_DIR, "events.jsonl"), "a", encoding="utf-8") as fp:
                    fp.write(json.dumps(archive, ensure_ascii=False) + "\n")
                with open(os.path.join(DATA_DIR, base + ".csv"), "w",
                          newline="", encoding="utf-8-sig") as fp:
                    w = csv.writer(fp)
                    w.writerow(["t_ms", "subject", "type", "key", "value", "note"])
                    for r in rows:
                        w.writerow([r.get("t"), r.get("subject"), r.get("type"),
                                    r.get("key"), r.get("value"), r.get("note")])
            body = _json(self, {"saved": len(rows), "file": f"data/{base}.csv",
                                "timeline": timeline_rel})
            self.end_headers(); self.wfile.write(body)
        else:
            self.send_error(404)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def cmd_serve(args):
    cfg = load_config()
    fullscreen = bool(getattr(args, "fullscreen", False))
    write_config_js(cfg, auto_fullscreen=fullscreen)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Serving the face task at {url}  (Ctrl+C to stop)")
    print("Folder scanning is enabled — register paths on the Video folders card.")
    if not args.no_open:
        launch_browser(url, fullscreen)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


def _apply_settings(cfg, args):
    s = dict(cfg.get("settings") or {})
    mapping = [
        ("centervideo", args.center), ("subject", args.subject),
        ("note", args.note), ("durationMin", args.duration),
        ("trigger", args.trigger), ("triggerkey", args.trigger_key),
        ("popleft", args.left_pct), ("satcenter", args.sat_center),
        ("volcenter", args.vol_center), ("satreel", args.sat_reel),
        ("volreel", args.vol_reel), ("poptrigger", args.pop_trigger),
        ("popinterval", args.pop_interval), ("allowseek", args.allowseek),
    ]
    for key, val in mapping:
        if val is not None:
            s[key] = val
    cfg["settings"] = s
    return cfg


def cmd_run(args):
    cfg = load_config()
    cfg = _apply_settings(cfg, args)
    cfg["autoStart"] = True
    save_config(cfg)
    write_config_js(cfg, auto_fullscreen=bool(getattr(args, "fullscreen", True)))
    print("Run configured (auto-start on page load):")
    for k, v in (cfg["settings"] or {}).items():
        print(f"  {k} = {v}")
    cmd_serve(args)


def cmd_folders(args):
    cfg = load_config()
    if args.action == "list":
        if not cfg["folders"]:
            print("No folders registered.")
        for f in cfg["folders"]:
            print(f)
    elif args.action == "add":
        path = os.path.abspath(os.path.expanduser(args.path))
        if not os.path.isdir(path):
            raise SystemExit(f"Not a directory: {path}")
        if path not in cfg["folders"]:
            cfg["folders"].append(path)
            save_config(cfg)
            print(f"Registered: {path}")
        else:
            print(f"Already registered: {path}")
        name, vids = scan_folder(path)
        print(f"Scan: {len(vids)} video(s) found in '{name}'")
    elif args.action == "remove":
        path = os.path.abspath(os.path.expanduser(args.path))
        cfg["folders"] = [f for f in cfg["folders"] if f != path]
        save_config(cfg)
        print(f"Removed: {path}")
    else:
        raise SystemExit("folders: use add|list|remove <path>")


def cmd_pools(_):
    print(f"{'POOL':<24} {'VIDEOS':>7}  {'STATUS':<8} PATH")
    print("-" * 70)
    for p in list_pools():
        status = "active" if p["active"] else ("imported" if p["imported"] else "")
        print(f"{p['name']:<24} {p['videos']:>7}  {status:<8} {p['path']}")


def cmd_import(args):
    path = os.path.abspath(os.path.expanduser(args.path))
    name, n = import_folder(path)
    print(f"Imported pool '{name}' ({n} videos) from {path}")
    print("Start the server (python3 task.py serve) and reload the page.")


def cmd_config(args):
    cfg = load_config()
    if args.action == "show":
        print(json.dumps(cfg.get("settings", {}), ensure_ascii=False, indent=2))
    elif args.action == "set":
        if not args.values:
            raise SystemExit("config set needs KEY=VALUE pairs")
        s = dict(cfg.get("settings") or {})
        for pair in args.values:
            if "=" not in pair:
                raise SystemExit(f"Not KEY=VALUE: {pair}")
            k, v = pair.split("=", 1)
            if k not in SETTING_KEYS:
                raise SystemExit(f"Unknown setting '{k}'. Valid: "
                                 + ", ".join(SETTING_KEYS))
            if v.isdigit():
                v = int(v)
            elif v.lower() in ("true", "false"):
                v = v.lower() == "true"
            s[k] = v
        cfg["settings"] = s
        save_config(cfg)
        write_config_js(cfg)
        print("Saved:")
        for k, v in s.items():
            print(f"  {k} = {v}")
    else:
        raise SystemExit("config: use show|set KEY=VALUE ...")


# --------------------------------------------------------------------------
# reel-crawler pool sync (Instagram reels)
# --------------------------------------------------------------------------
REELCRAWLER_ROOT = os.environ.get("FMRI_REELCRAWLER_ROOT") or os.path.join(
    os.path.dirname(HERE), "reel-crawler")

SHORTCODE_RE = re.compile(r"^[A-Za-z0-9_-]{6,}$")


def load_reels_pool(crawler):
    """Load the review-team merged pool (sync_repo/pool.json preferred).
    Returns (items, path); items are dicts whose code is a valid Instagram
    shortcode, sorted by code. (None, None) when no pool is found."""
    for pj in [os.path.join(crawler, "sync_repo", "pool.json"),
               os.path.join(crawler, "pool.json")]:
        try:
            with open(pj, encoding="utf-8") as fp:
                pool = json.load(fp)
            if isinstance(pool, dict):
                items = [it for it in pool.values()
                         if isinstance(it, dict) and SHORTCODE_RE.fullmatch(
                             str(it.get("code") or ""))]
                items.sort(key=lambda it: str(it["code"]))
                return items, pj
        except (OSError, json.JSONDecodeError):
            continue
    return None, None


def download_reel(url, out_dir, archive, jar=None, timeout=600):
    """Download one Instagram reel into out_dir via yt-dlp (anonymously, or
    with a Netscape cookie jar when one exists). Returns (ok, message)."""
    cmd = ["yt-dlp", "--no-update", "--no-warnings", "--no-playlist"]
    if jar and os.path.isfile(jar):
        cmd += ["--cookies", jar]
    cmd += ["-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
            "-o", os.path.join(out_dir, "%(id)s.%(ext)s"),
            "--download-archive", archive, url]
    # Strip dead proxy env vars (this machine's 127.0.0.1:10887).
    env = {k: v for k, v in os.environ.items()
           if k.lower() not in ("http_proxy", "https_proxy", "all_proxy", "no_proxy")}
    try:
        r = subprocess.run(cmd, env=env, capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "timeout after %ds" % timeout
    except OSError as e:
        return False, "yt-dlp not runnable: %s" % e
    if r.returncode == 0:
        return True, "downloaded"
    last = (r.stderr or "").strip().splitlines()
    return False, (last[-1] if last else "exit %d" % r.returncode)


def cmd_reels_sync(args):
    """Pull the reel-crawler team pool into the built-in videos/ pool."""
    crawler = os.path.abspath(os.path.expanduser(args.crawler or REELCRAWLER_ROOT))
    items, pj = load_reels_pool(crawler)
    if not items:
        raise SystemExit(
            "No pool.json found under %s (expected <reel-crawler>/sync_repo/pool.json). "
            "Point --crawler at the reel-crawler checkout or set FMRI_REELCRAWLER_ROOT."
            % crawler)
    excluded = [it for it in items
                if str(it.get("model_status") or "") == "excluded"]
    if excluded and not args.include_excluded:
        print("Skipping %d model-excluded item(s) (--include-excluded adds them):"
              % len(excluded))
        for it in excluded:
            print("  %s  @%s" % (it["code"], it.get("username") or "?"))
    wanted = [it for it in items
              if args.include_excluded
              or str(it.get("model_status") or "") != "excluded"]
    if args.max and len(wanted) > args.max:
        wanted = wanted[:args.max]
    vdir = os.path.join(HERE, "videos")
    os.makedirs(vdir, exist_ok=True)
    archive = os.path.join(vdir, "ig_downloaded.txt")
    downloaded = existed = failed = 0
    if not args.no_download:
        jar = (os.path.abspath(os.path.expanduser(args.cookies))
               if args.cookies
               else os.path.join(crawler, "instagram-session", "cookies.txt"))
        if jar and not os.path.isfile(jar):
            jar = None  # no jar — yt-dlp downloads anonymously
        for it in wanted:
            code = str(it["code"])
            if any(os.path.isfile(os.path.join(vdir, code + ext))
                   for ext in VIDEO_EXTS):
                existed += 1
                continue
            url = str(it.get("url") or "https://www.instagram.com/reel/%s/" % code)
            ok, msg = download_reel(url, vdir, archive, jar)
            if ok:
                downloaded += 1
                print("%s: %s" % (code, msg))
            else:
                failed += 1
                print("%s: FAILED (%s)" % (code, msg))
            if args.delay:
                time.sleep(args.delay)
    # Rebuild the manifest strictly from pool shortcodes found on disk —
    # anything that is not a review-team Instagram shortcode never enters.
    entries = []
    missing = 0
    for it in wanted:
        code = str(it["code"])
        fn = None
        for ext in VIDEO_EXTS:
            if os.path.isfile(os.path.join(vdir, code + ext)):
                fn = code + ext
                break
        if not fn:
            missing += 1
            continue
        e = {"src": "videos/" + fn,
             "author": str(it.get("username") or ""),
             "nick": str(it.get("username") or ""),
             "desc": str(it.get("caption") or "")[:500]}
        likes = it.get("likes")
        if isinstance(likes, (int, float)):
            e["likes"] = int(likes)
        entries.append(e)
    header = (
        "// Video manifest (auto-generated by task.py reels-sync — do not edit by hand;\n"
        "// pool synced from the review-team reel-crawler pool.json).\n"
        "// Only Instagram shortcodes from the review-team pool enter this manifest.\n"
        "// Each entry: { src, author, nick, desc[, likes] } — likes is shown\n"
        "// Instagram-style on the right side of the screen.\n"
    )
    with open(MANIFEST, "w", encoding="utf-8") as fp:
        fp.write(header + "window.VIDEO_MANIFEST = " +
                 json.dumps(entries, ensure_ascii=False, indent=1) + ";\n")
    cfg = load_config()
    cfg["active_pool"] = None
    save_config(cfg)
    print("Manifest: %d video(s) (pool: %d, model-excluded: %d, downloaded: %d, "
          "already present: %d, failed: %d, missing from disk: %d)."
          % (len(entries), len(items), len(excluded), downloaded, existed,
             failed, missing))
    if failed:
        print("Re-run `python3 task.py reels-sync` to retry failed downloads "
              "(archived successes are skipped automatically).")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Local server + CLI control for the face-recognition task.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("serve", help="start the local server")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--fullscreen", action="store_true",
                   help="open the browser window fullscreen")
    p.add_argument("--no-open", action="store_true",
                   help="do not open the browser automatically")
    p.set_defaults(fn=cmd_serve)

    p = sub.add_parser("run", help="configure a run and start the server "
                                   "(auto-starts on page load)")
    p.add_argument("--center", help="center documentary path or URL")
    p.add_argument("--subject", help="subject id (default P01)")
    p.add_argument("--note", help="free-text note recorded in the log")
    p.add_argument("--duration", type=float, help="run length in minutes")
    p.add_argument("--trigger", choices=("wait", "immediate"))
    p.add_argument("--trigger-key")
    p.add_argument("--left-pct", type=float, help="left-side popup chance %% (0-100)")
    p.add_argument("--sat-center", type=int, help="center saturation %% (0-200)")
    p.add_argument("--vol-center", type=int, help="center volume %% (0-100)")
    p.add_argument("--sat-reel", type=int, help="reel saturation %% (0-200)")
    p.add_argument("--vol-reel", type=int, help="reel volume %% (0-100)")
    p.add_argument("--pop-trigger", choices=("manual", "auto"))
    p.add_argument("--pop-interval", type=float, help="auto pop-up interval (seconds)")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--no-open", action="store_true")
    p.add_argument("--fullscreen", dest="fullscreen", action="store_true", default=True,
                   help="open the browser fullscreen (the default; use --no-fullscreen for a window)")
    p.add_argument("--no-fullscreen", dest="fullscreen", action="store_false",
                   help="open the browser in a normal window")
    p.add_argument("--seek", dest="allowseek", action="store_true", default=None,
                   help="allow dragging progress bars (reels + center video)")
    p.add_argument("--no-seek", dest="allowseek", action="store_false",
                   help="disable progress-bar dragging")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("folders", help="register folder paths for scanning")
    p.add_argument("action", choices=("add", "list", "remove"))
    p.add_argument("path", nargs="?", default="")
    p.set_defaults(fn=cmd_folders)

    p = sub.add_parser("pools", help="list discovered video pools")
    p.set_defaults(fn=cmd_pools)

    p = sub.add_parser("import", help="import a folder as the active pool")
    p.add_argument("path")
    p.set_defaults(fn=cmd_import)

    p = sub.add_parser("reels-sync",
                       help="pull the reel-crawler team pool (Instagram reels) "
                            "into the built-in videos/ pool")
    p.add_argument("--crawler",
                   help="reel-crawler checkout (default: sibling reel-crawler/ "
                        "or FMRI_REELCRAWLER_ROOT)")
    p.add_argument("--no-download", action="store_true",
                   help="build the manifest from already-downloaded files only")
    p.add_argument("--include-excluded", action="store_true",
                   help="also add items the model excluded")
    p.add_argument("--max", type=int,
                   help="limit to the first N pool items (sorted by shortcode)")
    p.add_argument("--cookies",
                   help="Netscape cookie jar for yt-dlp (default: the crawler's "
                        "instagram-session/cookies.txt when present; anonymous "
                        "otherwise)")
    p.add_argument("--delay", type=float, default=2.0,
                   help="seconds between downloads (default 2; 0 = none)")
    p.set_defaults(fn=cmd_reels_sync)

    p = sub.add_parser("config", help="show or set CLI settings")
    p.add_argument("action", choices=("show", "set"))
    p.add_argument("values", nargs="*", help="KEY=VALUE pairs (set only)")
    p.set_defaults(fn=cmd_config)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
