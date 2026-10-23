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

1. Put reels in `videos/` (MP4, H.264+AAC recommended) and run:
   ```bash
   python3 generate_manifest.py
   ```
2. Open `index.html`, adjust saturation / volume sliders, left/right pop-up
   percentage, center video, etc., and press **Start experiment**.
3. Keys during a run: **A** open/close the pop-up reel · **B** next reel ·
   **1/2** forwarded to the task page · **Esc** end early · trigger key
   (default **5**) starts the run from the black screen.

## Quick start (CLI mode)

```bash
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
| `python3 task.py serve [--port 8000] [--no-open]` | Start the local server (static files + folder-scan APIs + run-log archive). |
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
| `--center PATH\|URL` | Center documentary (local file or YouTube link) | `center/center.mp4` |
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
| `--port N` / `--no-open` | Server port / don't open the browser | 8000 / opens |

Settings set here or via `config set` are applied on **every** load of the
page while `config.js` exists (delete `config.js` to go back to interactive
defaults).

---

## Importing the collector's video pool (reel-crawler integration)

The task page and the video collector share folders — no copying:

```bash
# after the collector downloaded its pool into review_videos/:
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

Metadata is read from, in order of preference:

1. `pool.json` — the review-team merged pool (`{url: {username, likes, ...}}`)
2. `feed_collection.sqlite` — crawler stores (`feed_items` table)
3. `meta.json` — `review_frames/<code>/meta.json` capture files
4. `authors.json` — legacy TikTok metadata
5. `*.csv` — exports with `url` / `username` / `like_count` columns

The match key is the video's file name (the Instagram shortcode or TikTok
video id). Files with no matching metadata still play — they just show
`@unknown` and no like count.

---

## Where things live

| Path | Contents |
|---|---|
| `config.json` | CLI settings + registered folders + active pool (created by `task.py`) |
| `config.js` | What the page loads — CLI settings override localStorage |
| `videos/manifest.js` | The active video pool (built-in videos/ or an imported folder) |
| `data/events.jsonl` | One JSON line per finished run (server mode) |
| `data/<subject>_<stamp>.csv` | Per-run CSV, same columns as the browser download |

## Troubleshooting

- **Video doesn't play after import** — the `/media/...` URLs only work while
  `task.py serve` is running; in browser mode the manifest falls back to the
  built-in `videos/` pool. Re-run `generate_manifest.py` to rebuild it.
- **Pop-up volume resets** — browsers block unmuted autoplay; a volume of 0
  mutes the video, which is also the scanner-friendly default.
- **`run` auto-starts with the wrong settings** — the page merges
  `config.js` over localStorage; delete `config.js` (or re-run
  `task.py config set ...`) to change CLI settings.
- **Folder path rejected** — the path must exist and be an absolute,
  readable directory; the server only serves files inside registered folders.
