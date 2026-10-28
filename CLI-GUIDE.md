# CLI Guide — face-recognition video task

This task has two usage modes:

1. **Browser mode** — double-click `index.html` (or open it with any browser).
   Everything works except folder scanning, which browsers cannot do from
   `file://` (the Video folders card shows a hint instead).
2. **Server + CLI mode** — `task.py` (Python 3, stdlib only) starts a tiny
   local server. The same settings page then gains folder scanning and pool
   import, run logs are also archived server-side, and the whole experiment
   can be launched from the command line with no clicks at all.

All commands below run from this folder.

---

## Quick start (browser mode)

1. Sync the Instagram pool from the review team's `pool.json` (downloads the
   reels into `videos/` and rebuilds the manifest):
   ```bash
   python3 task.py reels-sync
   ```
2. Open `index.html`, adjust saturation / volume sliders, left/right pop-up
   percentage, center video, etc., and press **Start experiment**.
3. Keys during a run: **A** open/close the pop-up reel (reopening continues
   with the **next** video) · **B** next reel · **1/2** forwarded to the task
   page · **Esc** exit fullscreen (the run continues) · **F4** re-enter
   fullscreen · **Q** end the run early · trigger key (default **5**) starts
   the run from the black screen.

## Quick start (CLI mode)

```bash
# 0. sync the video pool (first time; rerun whenever the pool gains reels):
python3 task.py reels-sync

# 1. one fully-configured run, no clicks:
python3 task.py run --subject P01 --duration 10 --trigger immediate \
    --left-pct 50 --sat-center 100 --vol-center 0 --sat-reel 100 --vol-reel 0

# 2. or just the server + the normal settings page:
python3 task.py serve
#    -> http://127.0.0.1:8000/ (opened automatically; --no-open to suppress)
```

`run` writes a `config.js` that the page loads on top of its saved settings
(CLI wins) and sets **autoStart**, so the experiment starts by itself. With
`--trigger wait` the run still waits for the trigger key after auto-start.

---

## Command reference

| Command | What it does |
|---|---|
| `python3 task.py reels-sync [options]` | **Sync the Instagram pool** from the review team's `pool.json`: downloads missing reels into `videos/` and rebuilds `videos/manifest.js`. The canonical way to fill the pool. |
| `python3 task.py serve [--port 8000] [--no-open] [--fullscreen]` | Start the local server (static files + folder-scan APIs + run-log archive). `--fullscreen` opens Edge fullscreen and auto-enters fullscreen on the first key press. |
| `python3 task.py run [options]` | Set options, write `config.js` with autoStart, then serve. |
| `python3 task.py folders add <path>` | Register a folder path; prints how many videos a scan finds inside. |
| `python3 task.py folders list` | List registered folder paths. |
| `python3 task.py folders remove <path>` | Unregister a folder path. |
| `python3 task.py pools` | List all discoverable pools (registered folders + built-in `videos/`). |
| `python3 task.py import <path>` | Import a folder as the **active pool** — rewrites `videos/manifest.js` to serve `/media/...` URLs from that folder (nothing is copied). |
| `python3 task.py config show` | Print the stored CLI settings. |
| `python3 task.py config set KEY=VALUE ...` | Update settings, e.g. `config set subject=P02 popleft=30 satreel=0`. |

### `run` options

| Option | Meaning | Default |
|---|---|---|
| `--center X` | Center documentary: `lawn` \| `rocky` \| `original` (built-in presets), a local path, or a URL | `original` (`center/center.mp4`) |
| `--subject ID` | Subject id in logs / CSV filename | `P01` |
| `--duration MIN` | Run length in minutes | 10 |
| `--trigger wait\|immediate` | Wait for the trigger key, or start at once | wait |
| `--trigger-key K` | Trigger key | `5` |
| `--left-pct N` | % chance a random pop-up opens on the **left** (right = 100 − N) | 50 |
| `--sat-center N` | Center documentary saturation % (0 = black & white, 200 = vivid) | 100 |
| `--vol-center N` | Center documentary volume % (local files only; YouTube embeds stay muted) | 0 |
| `--sat-reel N` | Reel saturation % | 100 |
| `--vol-reel N` | Reel volume % | 0 |
| `--pop-trigger manual\|auto` | Reels pop up on A-key, or on a timer | manual |
| `--pop-interval SEC` | Auto pop-up interval in seconds | 10 |
| `--seek` / `--no-seek` | Allow (or forbid) dragging the reel + local center progress bars. Seek actions are never logged. | unchanged |
| `--fullscreen` / `--no-fullscreen` | Launch the browser fullscreen + auto-enter fullscreen on the first key press (Esc exits fullscreen but the run continues, F4 re-enters, Q ends early) | on |
| `--port N` / `--no-open` | Server port / don't open the browser | 8000 / opens |

Settings set here or via `config set` are applied on **every** load of the
page while `config.js` exists (delete `config.js` to go back to interactive
defaults).

---

## Syncing the Instagram pool (reel-crawler integration)

**`reels-sync` is the canonical way to fill the pool.** It reads the
review-team pool (the reel-crawler's `sync_repo/pool.json`, falling back to
`pool.json`), downloads every reel into this project's own `videos/` via
yt-dlp (no Instagram login needed), and rebuilds `videos/manifest.js` — the
manifest only ever lists pool shortcodes found on disk, so nothing else can
enter the pool:

```bash
python3 task.py reels-sync              # download missing reels + rebuild manifest
python3 task.py reels-sync --max 10     # cap the download count (test pools)
python3 task.py reels-sync --no-download   # manifest only, from files on disk
python3 task.py reels-sync --include-excluded  # also add model-excluded items
python3 task.py reels-sync --crawler /path/to/reel-crawler  # override the location
python3 task.py reels-sync --cookies /path/to/cookies.txt  # logged-in downloads
python3 task.py reels-sync --delay 2    # pause between downloads (default)
```

Without a reel-crawler checkout (e.g. right after downloading the GitHub
zip), `reels-sync` falls back to the `pool.json` snapshot bundled in this
repository — refresh that file from the review-team repo to pick up newly
approved reels.

`reels-sync` options:

| Option | Meaning | Default |
|---|---|---|
| `--crawler PATH` | Reel-crawler checkout to read the pool from | sibling `reel-crawler/` (or `$FMRI_REELCRAWLER_ROOT`) |
| `--no-download` | Skip downloading; rebuild the manifest from files already in `videos/` | downloads missing reels |
| `--include-excluded` | Also download items the review team's model flagged as excluded (political / sensitive / language) | excluded items are skipped and listed |
| `--max N` | Download at most N reels (quick test pools) | unlimited |
| `--cookies PATH` | Cookie jar for downloads that need a login | `reel-crawler/instagram-session/cookies.txt` if present, else anonymous |
| `--delay SEC` | Pause between download attempts | 2 |

Per reel, **author, caption and like count** are baked into the manifest from
the pool metadata, together with **tags** (review category / model category /
audio status) kept for a future preference algorithm; the like count is shown
Instagram-style (e.g. `45.1K`) on the right side of the screen, and author +
likes are written into the CSV log (`video_next` rows' `note` field).
Already-downloaded reels are skipped via `videos/ig_downloaded.txt`, so
reruns are cheap.

**Pinned selection:** when `videos/pool_selection.json` exists (written by
the settings page's *Instagram pool · team review* card, or created by hand:
`{"codes": ["<shortcode>", ...]}`), `reels-sync` restricts the pool to
exactly those shortcodes instead of the whole team pool. Delete the file to
go back to "everything non-excluded".

**Server endpoints (used by the team-review card):**

| Endpoint | What it does |
|---|---|
| `GET /api/team/pool` | The review-team pool with per-video status (approved / awaiting review / rejected / excluded), tags, and whether each reel is in this experiment's pool or on disk. Reads `FMRI_TEAM_REPO` (default: reel-crawler's `sync_repo/`). |
| `GET /api/team/pool?refresh=1` | Same, but runs `git pull` in the team repo first (no credentials are handled by this project — the checkout's own remote does the work). |
| `POST /api/team/pool` `{"codes": [...]}` | Save the selection, download missing reels in the background, rebuild the manifest (tags intact). |
| `GET /api/team/status` | Progress of the background import: `running`, `log`, `added`, `failed`. |

### Importing a pool from an arbitrary folder (alternative)

For pools that don't come from the review team, the task page and the
collector can share folders — no copying:

```bash
python3 task.py folders add ~/reel-crawler/review_videos
python3 task.py import ~/reel-crawler/review_videos
python3 task.py serve
```

On the settings page, the **Video folders** card lists the same registered
folders; you can scan, import, and switch pools from there. Importing also
pulls **author name + like count** for every reel whose shortcode matches
local metadata; the like count is shown Instagram-style (e.g. `45.1K`) on the
right side of the screen, and author + likes are written into the CSV log
(`video_next` rows' `note` field).

With `reels-sync`, metadata is taken straight from each pool entry and baked
into the manifest. The folder-import path (above) instead resolves metadata
at import time, in order of preference:

1. `pool.json` — the review-team merged pool (`{url: {username, likes, ...}}`)
2. `feed_collection.sqlite` — crawler stores (`feed_items` table)
3. `meta.json` — `review_frames/<code>/meta.json` capture files
4. `authors.json` — legacy metadata file (no longer written)
5. `*.csv` — exports with `url` / `username` / `like_count` columns

The match key is the video's file name (the Instagram shortcode). Files with
no matching metadata still play — they just show `@unknown` and no like
count.

---

## Where things live

| Path | Contents |
|---|---|
| `config.json` | CLI settings + registered folders + active pool (created by `task.py`) |
| `config.js` | What the page loads — CLI settings override localStorage |
| `videos/manifest.js` | The active video pool — rebuilt by `reels-sync` (review-team shortcodes only) or by a folder import |
| `pool.json` | Bundled review-team pool snapshot — `reels-sync` falls back to it when no reel-crawler checkout exists (zip newcomers) |
| `videos/pool_selection.json` | Optional pinned selection (gitignored): when present, the pool is restricted to the listed shortcodes |
| `videos/ig_downloaded.txt` | `reels-sync` download archive (gitignored) |
| `data/events.jsonl` | One JSON line per finished run (server mode; includes the `timelineFile` pointer but not the HTML itself) |
| `data/<subject>_<stamp>.csv` | Per-run CSV, same columns as the browser download |
| `data/timeline_<subject>_<stamp>.html` | Per-run self-contained timeline visualization (zoomable / pannable; archived automatically in server mode) |

The timeline's hover thumbnails are served from the sibling
`reel-crawler/review_frames/` capture folder (same source the metadata chain
uses — see above) via the `/frames/<shortcode>/<fNNN>.jpg` endpoint. Point
`FMRI_FRAMES_ROOT` at another location if your frames live elsewhere; without
a matching frame the tooltip simply shows text.

## Troubleshooting

- **Video doesn't play after import** — the `/media/...` URLs only work while
  `task.py serve` is running; in browser mode the manifest falls back to the
  built-in `videos/` pool. Re-run `python3 task.py reels-sync --no-download`
  to rebuild it.
- **Pop-up volume resets** — browsers block unmuted autoplay; a volume of 0
  mutes the video, which is also the scanner-friendly default.
- **`run` auto-starts with the wrong settings** — the page merges
  `config.js` over localStorage; delete `config.js` (or re-run
  `task.py config set ...`) to change CLI settings.
- **Folder path rejected** — the path must exist and be an absolute,
  readable directory; the server only serves files inside registered folders.
- **Fullscreen didn't happen** — if Edge is already running, macOS `open` may
  reuse the existing window instead of launching fullscreen. Quit Edge first
  (`pgrep -f "instagram-session"` should show nothing), then re-run. In
  browser mode, fullscreen is entered on the first key press instead — the
  first key is consumed by that, so press it twice on a slow machine.
- **Timeline hover shows no thumbnail** — frames are only available when the
  task runs through `task.py serve`, the file name is a 6+ character
  Instagram shortcode, and `FMRI_FRAMES_ROOT` (default: sibling
  `reel-crawler/review_frames/`) contains that shortcode's capture folder.
  Built-in demo pools with TikTok-id names, and any `file://` timeline,
  intentionally show text-only tooltips.
- **Timeline file didn't download** — browsers may block the second automatic
  download at the end of a run. Use the **Download timeline** button on the
  end screen, or grab the archived copy from `data/` (server mode).
