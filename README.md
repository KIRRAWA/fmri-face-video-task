# fMRI · Face Task + Short-Form Video Browsing

A documentary plays in a **fixed centered stage** while short-form videos
(Instagram reels) **pop in from the left or right** on demand. Subjects do the
face task in the scanner and browse reels voluntarily. **Key A** = open/close
the pop-up, **Key B** = next reel. Saturation and volume are freely adjustable
per content type (documentary vs. reels) with sliders.

```
fmri-face-video-task/
  index.html              # main page (single file, double-click to open, works offline)
  task.py                 # local server + full CLI control (folder import, auto-start runs)
  CLI-GUIDE.md            # English walkthrough of the command-line workflow
  generate_manifest.py    # LEGACY: manual manifest rebuild — use `task.py reels-sync` instead
  get_authors.py          # LEGACY (TikTok): per-video author metadata — not used for the pool
  download_videos.py      # LEGACY (TikTok): batch auto-downloader — not used for the pool
  ig_collector.py         # Instagram cold-account collector (Plan A: scroll + links/labels)
  center/
    center.mp4            # shipped center documentary (plays offline)
  videos/
    manifest.js           # video manifest — rebuilt by `task.py reels-sync` from the review-team pool
    ig_downloaded.txt     # reels-sync download archive (gitignored)
    *.mp4                 # Instagram reels downloaded by reels-sync
  config.json / config.js # created by task.py (machine-specific, gitignored)
  data/                   # server-side run archives (gitignored)
  README.md
```

## Instagram cold-account collector (Plan A)

`ig_collector.py` auto-scrolls the Reels feed on a fresh, deliberately inert
Instagram account and captures every reel's link + labels (caption hashtags,
music track, author, video URLs) from the JSON the page loads — no API, no
DOM scraping.

**Cold-account rules** (so the algorithm learns nothing about taste): no
likes/follows/comments/profile visits; fixed dwell per reel (only
content-independent jitter); skip all interest prompts at signup.

```
pip install playwright          # uses your installed Edge, no browser download
python3 ig_collector.py --login # one-time manual login (session saved in ig_profile/)
python3 ig_collector.py --reels 100 --dwell 5   # collect
python3 ig_collector.py --reels 100 --download  # collect + download
python3 ig_collector.py --download-only         # download the pool later
```

Output: `videos/ig_captured.jsonl` — one JSON per reel (shortcode, url,
username, caption, hashtags, music, taken_at, media_urls, alt text).

## Quick start (browser mode)

1. Sync the Instagram pool once: `python3 task.py reels-sync` (downloads the
   review team's reels into `videos/` — see "Video pool" below)
2. Open `index.html` in Chrome (double-click — no server, no network needed)
3. Adjust the settings: center video, pop-up side / left-side chance,
   saturation & volume sliders, run duration → **Fullscreen** → **Start experiment**
4. (Trigger mode) The screen stays black until the trigger key (default `5`)
5. When the run ends, statistics are shown and the CSV is downloaded automatically

## Quick start (server + CLI mode)

`task.py` (Python 3, stdlib only) adds folder scanning to the settings page
and lets the whole experiment be launched from the command line:

```bash
python3 task.py reels-sync                 # sync the Instagram pool (download + manifest)
python3 task.py serve                       # server + the normal settings page
python3 task.py run --subject P01 --duration 10 --trigger immediate \
    --left-pct 50 --sat-center 100 --vol-center 0 --sat-reel 100 --vol-reel 0
#   -> one fully-configured run, no clicks at all
# `run` opens the browser fullscreen automatically (--no-fullscreen for a
# window). On the page: Esc exits fullscreen (the run continues), F4 restores
# it, Q ends the run early. --seek allows dragging the progress bars.
```

See **CLI-GUIDE.md** for the complete command reference and the reel-crawler
import workflow.

## Layout & pop-ups

The task (or center video) sits in a **fixed centered stage** surrounded by a
black border whose side strips are exactly one reel wide; videos **pop in from
the left or right** and fill that strip — the center stage never moves or
resizes. Both panels can be open at once (one per side).

| Setting | Options |
|---|---|
| Pop-up side | **Random** (default) / both / left only / right only |
| Left-side chance (%) | Random mode only: % of pop-ups that open on the **left** (right = 100 − this) |
| Pop-up trigger | **Manual** (A opens/closes a pop-up — "internally generated" browsing) / **Auto** (a pop-up opens on its own every N seconds and closes when its clip ends — "externally probed") |
| Pop-up interval | Auto mode only: seconds between auto pop-ups |
| Center video | URL of the documentary shown centered (YouTube links auto-convert to embeds; local/remote video files play in a built-in player). Defaults to `center/center.mp4`, a local clip that works offline — YouTube needs internet |

Key mapping: **A** = pop up / close (per the side setting; "both" opens both),
**B** = next clip in every open panel.

## Settings

| Setting | Description |
|---|---|
| Pop-up side | Random / both / left only / right only |
| Left-side chance (%) | Random mode only: left-side probability (0-100, default 50) |
| Pop-up trigger | Manual (A opens/closes) / Auto (opens every N seconds, closes when the clip ends) |
| Pop-up interval | Auto mode only: seconds between auto pop-ups |
| Center video | Documentary URL shown centered (YouTube links auto-converted to embeds; empty = built-in placeholder task). YouTube needs internet — use a local file for offline runs |
| Center saturation | Slider 0-200% for the documentary (0% = black & white) |
| Center volume | Slider 0-100% (local files only; YouTube embeds stay muted) |
| Reel saturation | Slider 0-200% for the pop-up reels (0% = black & white) |
| Reel volume | Slider 0-100% (0 = muted — also the browser-autoplay-safe default) |
| Video source | Auto / real videos only / placeholder clips only (debugging) |
| Run duration | Minutes, decimals allowed |
| Task page | Path to the face-task page (empty = built-in placeholder task). **Filling this in is the "integration"** |
| Start mode | Wait for trigger key (black screen — for scanner pulse) / start immediately |
| Trigger key | Default `5`; scanner pulse boxes usually map to 5 or t |
| Keys A / B | Remappable (button boxes send standard key codes, same as a keyboard) |
| Instagram-style decorations | Like count / @author on the reels. Placeholder clips show simulated values; **real videos show their real @author bottom-left and their real like count Instagram-style on the right side** (progress bar always shown) |
| Allow seeking | When enabled, subjects can **drag the progress bar** to scrub reels and the center video (local files). Dragging is never logged and never affects the session clock; viewing-time statistics measure on-screen dwell time, not content progress. YouTube embeds keep their native controls (unchanged) |
| Subject ID / Note | Written into the CSV |
| Video folders | Register real folder paths and import a pool from anywhere on disk (server mode only) |

Settings are remembered automatically (localStorage); CLI settings from
`task.py` (`config.js`) override them while present.

## Video pool

The pool contains **Instagram reels only** — the shortcodes the review team
collected with the reel-crawler (`pool.json`). TikTok videos are not part of
this experiment (IRB) and never enter the pool.

The canonical sync path is `task.py reels-sync`: it downloads every pool
reel into `videos/` (via yt-dlp — no Instagram login needed), skips
model-excluded items by default, and rebuilds `videos/manifest.js` — which
only ever lists pool shortcodes found on disk:

```bash
python3 task.py reels-sync                 # download missing reels + rebuild the manifest
python3 task.py reels-sync --no-download   # rebuild the manifest from files already on disk
python3 task.py reels-sync --max 5         # cap the count (quick test pools)
python3 task.py reels-sync --include-excluded   # also add the model-excluded items
```

Author, caption and like count for each reel come straight from the pool
metadata and are baked into the manifest. `FMRI_REELCRAWLER_ROOT` points at
the reel-crawler checkout (default: the sibling `reel-crawler/` folder).
Reopen index.html afterwards — the settings page shows "N real video(s)
detected".

Playback rules: randomized order, no immediate repeats, endless looping, B advances clip by clip — mimics a live feed.
Copyright note: real videos for the study must be provided by the lab (own account content or licensed content). This template ships no real videos — the placeholder clips are animated, not real.

### Video folders (import a pool from anywhere on disk)

`reels-sync` (above) is the canonical way to fill the built-in pool. The
**Video folders** card (server mode) is the generic alternative — it mirrors
real folders on disk:

1. Register a folder path (e.g. the reel-crawler's `review_videos/` output)
2. Scan finds the videos inside; **Import** makes it the active pool
3. Nothing is copied — `task.py` serves the files from their real location
   and rewrites `videos/manifest.js` with `/media/...` URLs

Importing also pulls **author name + like count** for every reel whose file
name (the Instagram shortcode) matches local metadata — from `pool.json`
(review-team merged pool), `feed_collection.sqlite` (crawler stores),
`review_frames/<code>/meta.json`, `authors.json`, or CSV exports. The like
count is displayed Instagram-style (e.g. `45.1K`) **on the right side of the
screen**, and author + likes are written into the CSV (`video_next` rows).
Files without metadata still play — they show `@unknown` and no like count.

### Author metadata (the @author label)

Every pool video shows **@author** bottom-left and its like count
Instagram-style on the right. With `reels-sync` the metadata comes from the
review-team `pool.json` and is baked directly into `videos/manifest.js` —
no separate metadata file is needed. If no author is known the UI falls
back to `@unknown`.

The legacy TikTok path (`videos/authors.json`, `get_authors.py`,
`download_videos.py`) is kept for historical reference only — TikTok videos
are not allowed in this experiment (IRB) and those scripts are not used for
the pool.

## Key reference

| Key | Action |
|---|---|
| A (remappable) | Open / close the pop-up video (per the side setting). Reopening a panel continues with the **next** video in the pool (position + 1, wraps around), so every open shows a fresh clip |
| B (remappable) | Next reel in every open panel |
| 1 / 2 | Forwarded to the task page (face-task responses) |
| Trigger (default 5) | Start the run from the black screen (the documentary only starts playing after this) |
| Esc | Exit fullscreen — the run continues unaffected. (On the trigger-wait screen, Esc exits fullscreen; if the page is not fullscreen it reloads) |
| F4 | Re-enter fullscreen |
| Q | End the run early (logged, CSV + timeline saved — same as a countdown end) |
| R | Back to settings (end screen) |

Button boxes act as standard keyboards; key codes match a normal keyboard, so just fill in the actual codes per your lab's convention. This page always owns the keyboard — the task page must never call `focus()`. Remappable A/B keys take priority over the fixed Q/F4/Esc keys; pick codes that do not collide.

## Language

The settings page has an **EN / 中文** toggle at the top right; the choice is remembered. All on-screen texts follow the selected language — settings, usage guide, integration protocol, trigger-wait screen, end screen, and the placeholder task inside the iframe. Data logs and CSV output stay in English regardless, for analysis consistency.

## Subject instructions (what the subject does)

A documentary plays in the center of the screen during the whole run (it starts when the run starts, never before). At any moment the subject can:

- press **A** to pop a short video up on the left or right (or both) — in auto mode pop-ups can also appear on their own
- press **B** to go to the next video
- press **A** again to close the pop-ups and return to the task — reopening them later continues with the next video, not the one they were watching

That is the entire video interaction — no mouse, no other keys. Whether and how long they browse is entirely up to them. Task responses use keys 1 / 2. The same instructions are available on the settings page under "Subject instructions (show before the run)".

## Data logging

Every event is one CSV row with millisecond timestamps (t=0 is the trigger/start moment); downloaded automatically at the end (and also archived server-side in `data/` when running through `task.py`):

`t_ms, subject, type, key, value, note`

| type | Meaning |
|---|---|
| session_start | Run start (note contains full config incl. saturations, volumes, left-side chance, allowseek) |
| trigger | Scanner trigger received |
| key | Every key this page receives (note: press/repeat) |
| popup_manual / popup_auto | A pop-up opened (value = side) |
| video_open / video_close | Video opened/closed (value = clip name) |
| video_next | Next clip (B key or auto-advance; note: author + likes of the new clip) |
| clip_start | A clip began playing — value = `side\|name`, note = JSON `{side, name, src, kind, author, likes, reason}` (reason: open_first / open_advance / next / switch / begin). Side is `left`, `right`, or `center` (the documentary) |
| clip_end | A clip stopped — value = `side\|name`, note = `reason duration_ms=N` (reason: close / switch / run_end / replaced / missing_end) |
| video_play / video_error | Clip loaded successfully / failed |
| task_event | Events reported by the task page (value = event type, note = JSON) |
| task_ready / warn_* | Integration status and warnings |
| run_end | Run finished (value = timeout / manual — manual = Q key) |

**Per-video viewing time**: pair the `clip_start` / `clip_end` rows by side
(a new `clip_start` implicitly closes the previous interval on that side).
The end-screen stats use the union of left/right intervals (both panels open
at once is never double-counted). All `t_ms` values are session-relative
milliseconds from a `performance.now()` clock — **video progress-bar
positions never participate in timing**, and seek-bar dragging produces no
log rows at all.

### Run timeline (visualization)

Every run end — countdown or Q — also produces a **self-contained zoomable
timeline** (single HTML file, no external dependencies):

- one lane each for the center documentary, the left and right reels, plus an
  actions lane (trigger, A, B, auto pop-ups, run end);
- spans show exactly when each video was on screen and for how long;
- **scroll to zoom** (anchored at the cursor) and **drag to pan** left/right,
  or use the **arrow keys** (← → pan, ↑ ↓ zoom) — long runs extend far beyond
  the screen width; **Fit** resets the view;
- **click a reel span** to open that video on Instagram (shortcodes are
  rebuilt into `instagram.com/reel/<code>/` URLs; spans without a link are
  not clickable);
- **hover a video** for its name, side, start/end, duration, author, likes,
  and end reason — plus the video's **first frame** (`/frames/<code>/f000.jpg`,
  served by task.py from the reel-crawler's `review_frames/`; videos whose
  name is not an Instagram shortcode, or file:// mode, show text only);
- **drag the strip above the chart** to float it anywhere on the screen (Pin
  back returns it to the page), and **Hide data** collapses the table below;
- a plain **data table** (`<details>`) at the bottom with the same intervals.

The file is downloaded automatically at the end (the end screen has a
"Download timeline" button in case the browser blocks the second automatic
download) and archived server-side as `data/timeline_<subject>_<stamp>.html`
when running through `task.py`.

## Integration protocol (for the face-task developer)

The task page is embedded as an **iframe** with the video layer floating above it — the task page's code is never modified by this template. Bidirectional postMessage:

### Minimal changes the task page must make

```html
<script>
// 1. NEVER call window.focus() — this template page owns the keyboard.
// 2. Replace keydown handling with forwarded-key messages:
window.addEventListener('message', function(ev){
  var m = ev.data;
  if(!m || m.source !== 'fmri-video') return;
  if(m.type === 'key') {
    // equivalent to the old keydown event: m.key is "1", "2", etc.
    handleTaskKey(m.key);
  } else if(m.type === 'resume') {
    // optional: the run has ended (sent when the end screen appears)
    resumeTask();
  }
});

// 3. Optional: report trial events (merged into the same CSV)
function report(event){  // any fields, e.g. {type:'trial', trial:3, rt:412, correct:1}
  window.parent.postMessage({source:'task', type:'event', event: event}, '*');
}

// 4. Optional: announce readiness on load
window.parent.postMessage({source:'task', type:'ready'}, '*');
</script>
```

### Message table

| Direction | Message | Description |
|---|---|---|
| Template → task | `{source:'fmri-video', type:'key', key}` | Forwarded key (the task page's response keys) |
| Template → task | `{source:'fmri-video', type:'resume'}` | The run ended (end screen shown) |
| Task → template | `{source:'task', type:'ready'}` | Task page loaded |
| Task → template | `{source:'task', type:'event', event:{...}}` | Trial events, logged into the CSV as-is |

The built-in placeholder task (settings left empty) is written against exactly this protocol — use it as the reference implementation.

## Scanner-room deployment checklist

- [ ] Open index.html in Chrome/Edge; F11 or the **Fullscreen** button (CLI runs open fullscreen automatically; Esc leaves fullscreen without ending the run, F4 restores it)
- [ ] Disable system notifications / update popups; enable Do Not Disturb
- [ ] Confirm button-box key codes → fill in A / B / trigger key on the settings page
- [ ] Set the saturation / volume sliders for the documentary and the reels (both default to muted — enable volume only with MR-compatible headphones)
- [ ] Decide whether seeking is allowed for this protocol (settings "Allow seeking"; CLI `--seek` / `--no-seek`) — if allowed, note that dragging is never logged
- [ ] Choose the left/right pop-up chance for this protocol
- [ ] Run one full pilot session (including the CSV **and the timeline HTML**) and check the data before booking subjects
- [ ] Screen brightness: `#taskArea` background is `#808080` (common projector gray), adjustable in the CSS

## FAQ

- **Page says manifest not found / videos don't play** → make sure videos/manifest.js exists with correct paths; rerun `python3 task.py reels-sync --no-download`
- **A video won't play** → transcode to H.264 + AAC MP4 (e.g. `ffmpeg -i in.mov -c:v libx264 -pix_fmt yuv420p -c:a aac out.mp4`)
- **Changed videos but the page doesn't update** → rerun the script + refresh (Ctrl/Cmd+R)
- **Why not embed live Instagram/TikTok directly** → no third-party feed API, iframe embeds can't be key-controlled, and a network dependency is risky mid-scan; a pre-downloaded pool is the controllable alternative
- **Center video stays black** → YouTube embeds need internet; for offline scanner runs download the clip (e.g. `yt-dlp URL -o center/center.mp4`) and enter its path instead, or leave it empty for the built-in placeholder task
- **Imported pool won't play** → imported pools are served as `/media/...` URLs by `task.py`; keep the server running (`python3 task.py serve`), or rerun `python3 task.py reels-sync --no-download` to switch back to the built-in `videos/` pool
- **file:// limitations** → this template works around most of them (manifests load via script tags); only folder scanning and timeline thumbnails need the server: `python3 task.py serve` then visit `http://127.0.0.1:8000/`
- **The timeline HTML did not download** → browsers may block two automatic downloads at once (CSV + timeline). Use the "Download timeline" button on the end screen, or grab the archived copy from `data/timeline_*.html` (server mode)
- **No thumbnail on timeline hover** → thumbnails exist only for videos whose filename is an Instagram shortcode, are served by `task.py` from the sibling `reel-crawler/review_frames/` (override: `FMRI_FRAMES_ROOT`), and require the timeline to be opened via the server (`http://127.0.0.1:8000/data/timeline_*.html`) — an offline copy degrades to text-only tooltips
- **Fullscreen did not engage on CLI start** → the browser window opens maximized via `--start-fullscreen`; the page additionally requests DOM fullscreen on the first key press/Start click. If the scanner OS window manager swallows Esc, use the browser's own fullscreen toggle instead — the run is unaffected either way

---

# fMRI · 人脸任务 + 短视频浏览

一部纪录片在**固定尺寸的居中舞台**播放，短视频（Instagram reels）随时从**左侧或右侧弹出**。受试者在扫描仪内做人脸任务，刷不刷、刷多久完全自愿。**A 键** = 打开/关闭弹出视频，**B 键** = 下一条。纪录片与 reels 的**饱和度、音量**分别用滑杆自由调节。

```
fmri-face-video-task/
  index.html              # 主页面（单文件，双击即开，离线可用）
  task.py                 # 本地服务器 + 完整命令行控制（文件夹导入、免点击启动）
  CLI-GUIDE.md            # 命令行工作流的英文指南
  generate_manifest.py    # 旧版：手动重建清单——请改用 `task.py reels-sync`
  get_authors.py          # 旧版（TikTok）：逐条视频作者信息——已不用于视频池
  download_videos.py      # 旧版（TikTok）：批量下载器——已不用于视频池
  ig_collector.py         # Instagram 冷号采集器（Plan A：滚动 + 链接/标签）
  center/
    center.mp4            # 随附的中央纪录片（离线可播）
  videos/
    manifest.js           # 视频清单——由 `task.py reels-sync` 按 review-team 池重建
    ig_downloaded.txt     # reels-sync 下载归档（已 gitignore）
    *.mp4                 # reels-sync 下载的 Instagram reels
  config.json / config.js # 由 task.py 生成（机器相关，已 gitignore）
  data/                   # 服务端实验记录存档（已 gitignore）
  README.md
```

## Instagram 冷号采集器（Plan A）

`ig_collector.py` 在一个全新、刻意不互动的 Instagram 账号上自动滚动 Reels feed，并从页面加载的 JSON 里抓取每条 reel 的链接与标签（文案 hashtag、音乐、作者、视频地址）——无需 API、无需 DOM 解析。

**冷号纪律**（让算法学不到任何口味）：不点赞、不关注、不评论、不点主页；每条 reel 固定停留（仅加与内容无关的抖动）；注册时跳过所有兴趣提示。

```
pip install playwright          # 使用本机 Edge，无需下载浏览器
python3 ig_collector.py --login # 一次性手动登录（会话存于 ig_profile/）
python3 ig_collector.py --reels 100 --dwell 5   # 采集
python3 ig_collector.py --reels 100 --download  # 采集 + 下载
python3 ig_collector.py --download-only         # 之后单独下载
```

输出：`videos/ig_captured.jsonl` —— 每条 reel 一行 JSON（shortcode、url、username、caption、hashtags、music、taken_at、media_urls、alt text）。

## 快速开始（浏览器模式）

1. 先同步一次 Instagram 池：`python3 task.py reels-sync`（把 review team 的
   reels 下载进 `videos/`——见下方「视频池」）
2. Chrome 打开 `index.html`（双击即可，无需服务器、无需联网）
3. 设置页调好参数：中央视频、弹出方向/左侧概率、饱和度与音量滑杆、时长 → **全屏** → **开始实验**
4. （触发模式）黑屏等待，按触发键（默认 `5`）开始
5. 到时间自动结束 → 结束页显示统计并自动下载 CSV

## 快速开始（服务器 + 命令行模式）

`task.py`（仅用 Python 3 标准库）给设置页加上文件夹扫描，并支持纯命令行启动实验：

```bash
python3 task.py reels-sync                 # 同步 Instagram 视频池（下载 + 重建清单）
python3 task.py serve                       # 服务器 + 常规设置页
python3 task.py run --subject P01 --duration 10 --trigger immediate \
    --left-pct 50 --sat-center 100 --vol-center 0 --sat-reel 100 --vol-reel 0
#   -> 一次免点击的完整实验
# `run` 默认自动全屏打开浏览器（--no-fullscreen 用窗口）。页面上：Esc 退出全屏
# （实验照常继续），F4 恢复全屏，Q 提前结束实验。--seek 允许拖动进度条。
```

完整命令参考与 reel-crawler 导入流程见 **CLI-GUIDE.md**。

## 布局与弹窗

任务（或中央视频）位于**固定尺寸的居中舞台**中，四周是黑边，左右两条黑边宽度正好等于一条 reel 的宽度；视频从**左侧或右侧滑入**并恰好填满黑边——中央舞台不会移动或缩放；两侧面板可以同时打开（每侧一个）。

| 设置 | 选项 |
|---|---|
| 弹出方向 | **随机**（默认）/ 两侧 / 仅左 / 仅右 |
| 左侧出现概率（%） | 仅随机模式：弹出出现在**左侧**的百分比（右侧 = 100 − 此值） |
| 弹出方式 | **手动**（按 A 开/关弹窗——「自发生成」式浏览）/ **自动**（每 N 秒自动弹出，视频播完自动收起——「外部探测」式） |
| 弹出间隔 | 仅自动模式：两次自动弹出间隔秒数 |
| 中央视频 | 居中播放的纪录片 URL（YouTube 链接自动转为嵌入；本地/远程视频文件用内置播放器播放）。默认 `center/center.mp4`——本地片段，离线可用；YouTube 需联网 |

按键：**A** = 按方向设置弹出/收起（「两侧」则同时弹出两个），**B** = 每个打开的面板各换下一条。

## 设置项

| 设置 | 说明 |
|---|---|
| 弹出方向 | 随机 / 两侧 / 仅左 / 仅右 |
| 左侧出现概率（%） | 仅随机模式：左侧弹出概率（0-100，默认 50） |
| 弹出方式 | 手动（按 A 开关）/ 自动（每 N 秒弹出、播完自动收起） |
| 弹出间隔 | 仅自动模式：两次自动弹出间隔秒数 |
| 中央视频 | 居中纪录片 URL（YouTube 自动转嵌入；留空 = 内置占位任务）。YouTube 需联网——扫描间离线请用本地文件 |
| 中央饱和度 | 纪录片滑杆 0-200%（0% = 黑白） |
| 中央音量 | 纪录片滑杆 0-100%（仅本地文件；YouTube 嵌入保持静音） |
| Reel 饱和度 | 弹出 reels 滑杆 0-200%（0% = 黑白） |
| Reel 音量 | 弹出 reels 滑杆 0-100%（0 = 静音，也是浏览器自动播放的安全默认） |
| 视频来源 | 自动 / 仅真实视频 / 仅占位动画（调试） |
| 实验时长 | 分钟，可小数 |
| 任务页面 | 人脸任务页面路径（留空 = 内置占位任务）。**填这个就是「接入」** |
| 开始方式 | 等待触发键（黑屏，适合扫描脉冲）/ 立即开始 |
| 触发键 | 默认 `5`，按钮盒接 TTL 脉冲通常映射 5 或 t |
| A / B 键 | 可改（按钮盒键码与键盘一致） |
| Instagram 装饰 | 点赞数 / @作者显示在 reels 上。占位动画为模拟数值；**真实视频左下角显示真实 @作者，屏幕右侧以 Instagram 样式显示真实点赞数**（进度条始终显示） |
| 允许拖动进度条 | 开启后受试者可**拖动进度条**调整 reels 与中央视频（本地文件）的播放位置。拖动从不记入日志、不影响计时；观看时长统计的是屏幕停留时间而非内容进度。YouTube 嵌入保持自带控件（不变） |
| 受试者编号 / 备注 | 写入 CSV |
| 视频文件夹 | 注册真实文件夹路径、从磁盘任意位置导入视频池（仅服务器模式） |

设置自动记忆（localStorage）；`task.py` 的命令行设置（config.js）存在时优先。

## 视频池

视频池**只含 Instagram reels**——即 review team 用 reel-crawler 收集的
shortcode（`pool.json`）。TikTok 视频不参与本实验（IRB 规定），也永远不会
进入视频池。

规范同步方式是 `task.py reels-sync`：把池内每条 reel 下载进 `videos/`
（走 yt-dlp——无需 Instagram 登录），默认跳过被模型排除的条目，并重建
`videos/manifest.js`——清单**只会**列出磁盘上确实存在的池内 shortcode：

```bash
python3 task.py reels-sync                 # 下载缺失的 reels + 重建清单
python3 task.py reels-sync --no-download   # 仅按磁盘上已有文件重建清单
python3 task.py reels-sync --max 5         # 限制条数（快速测试池）
python3 task.py reels-sync --include-excluded   # 把模型排除的条目也加进来
```

每条 reel 的作者、文案和点赞数直接取自池元数据并写进清单。
`FMRI_REELCRAWLER_ROOT` 指向 reel-crawler 检出的目录（默认：旁边的
`reel-crawler/` 文件夹）。之后重开 index.html，设置页会显示「检测到 N 条
真实视频」。

播放规则：随机排序、同条不连续、循环不到头，B 键逐条切换——模拟「实时推荐流」。
版权提醒：正式实验视频由实验室自备（自己账号内容或获授权内容），本模板不内置任何真实视频——内置的是动画占位内容，不是真实视频。

### 视频文件夹（从磁盘任意位置导入视频池）

`reels-sync`（如上）是填充内置视频池的规范方式；**视频文件夹**卡片
（服务器模式）是通用替代方案——与实际文件夹同步：

1. 注册一个文件夹路径（如 reel-crawler 的 `review_videos/` 输出目录）
2. 扫描会找到其中的视频；**导入**即设为当前视频池
3. 不复制任何文件——`task.py` 直接从真实位置伺服这些文件，并重写 `videos/manifest.js` 为 `/media/...` 地址

导入时还会为每条文件名（Instagram shortcode）能与本地元数据匹配上的 reel 拉取**作者名 + 点赞数**——元数据来自 `pool.json`（review-team 合并池）、`feed_collection.sqlite`（采集器存储）、`review_frames/<code>/meta.json`、`authors.json` 或 CSV 导出。点赞数以 Instagram 样式（如 `45.1K`）显示在**屏幕右侧**，作者与点赞数写入 CSV（`video_next` 行的 note 字段）。没有元数据的视频照常播放——显示 `@unknown`、不显示点赞数。

### 作者信息（@作者标签）

池内每条视频左下角都显示 **@作者**，右侧以 Instagram 样式显示点赞数。
走 `reels-sync` 时，元数据直接取自 review-team 的 `pool.json` 并写进
`videos/manifest.js`——不需要单独的元数据文件。查不到作者时界面显示
`@unknown`。

旧版 TikTok 路径（`videos/authors.json`、`get_authors.py`、
`download_videos.py`）仅作历史参考保留——本实验不允许 TikTok 视频
（IRB），这些脚本已不用于视频池。

## 按键总表

| 键 | 功能 |
|---|---|
| A（可改） | 打开/关闭弹出视频（按方向设置）。再次打开面板时**接着播下一条**（位置 +1，循环），每次打开都是新视频 |
| B（可改） | 每个打开的面板各换下一条 |
| 1 / 2 | 转发给任务页（人脸任务作答） |
| 触发键（默认 5） | 黑屏时开始实验（纪录片在这之后才开始播放） |
| Esc | 退出全屏——实验照常继续。（触发等待屏上按 Esc 退出全屏；若本就非全屏则刷新页面） |
| F4 | 重新进入全屏 |
| Q | 提前结束实验（记入日志，CSV + 时间线照常保存——与倒计时结束一致） |
| R | 返回设置（仅结束页） |

按钮盒即标准键盘，键码映射与普通键盘一致，按实验室惯例在设置页填实际键码即可。键盘始终由本页接管，任务页不得调用 `focus()`。可改的 A/B 键优先于固定的 Q/F4/Esc——选键码时避开冲突。

## 语言

设置页右上角有 **EN / 中文** 切换按钮，选择会被记住。所有界面文字跟随所选语言——设置页、使用指南、对接协议、触发等待屏、结束页、iframe 内的占位任务。数据日志与 CSV 始终为英文，保证分析一致。

## 被试说明（被试要做什么）

实验全程一部纪录片在屏幕中央播放（实验开始后才开播，不会提前放）。受试者随时可以：

- 按 **A** 让短视频从左侧或右侧（或两侧同时）弹出——自动模式下弹窗也会自己出现
- 按 **B** 看下一条视频
- 再按 **A** 收起弹窗、回到任务——之后再打开会接着播下一条，而不是刚才那条

这就是全部视频操作——不用鼠标、没有其他键。是否刷、刷多久完全自愿。任务作答用 1 / 2 键。同样内容在设置页「被试说明（实验前展示）」中可查。

## 数据记录

所有事件一行一条，毫秒时间戳（t=0 为触发/开始时刻），结束自动下载 CSV（经 `task.py` 运行时还会在服务器端存档到 `data/`）：

`t_ms, subject, type, key, value, note`

| type | 含义 |
|---|---|
| session_start | 开始（note 含全部配置：饱和度、音量、左侧概率、allowseek 等） |
| trigger | 扫描触发 |
| key | 本页收到的每个按键（note: press/repeat） |
| popup_manual / popup_auto | 弹窗打开（value=侧别） |
| video_open / video_close | 视频打开/关闭（value=视频名） |
| video_next | 换下一条（B 键或自动推进；note：新视频的作者与点赞数） |
| clip_start | 一条视频开始播放——value = `side\|name`，note = JSON `{side, name, src, kind, author, likes, reason}`（reason: open_first / open_advance / next / switch / begin）。side 为 `left` / `right` / `center`（纪录片） |
| clip_end | 一条视频停止——value = `side\|name`，note = `reason duration_ms=N`（reason: close / switch / run_end / replaced / missing_end） |
| video_play / video_error | 视频加载成功/失败 |
| task_event | 任务页上报的事件（value=事件类型，note=JSON） |
| task_ready / warn_* | 对接状态与警告 |
| run_end | 结束（value=timeout / manual——manual 即按 Q 键） |

**每条视频的观看时长**：把同侧的 `clip_start` / `clip_end` 配对即可（同侧新的
`clip_start` 隐式结束上一个区间）。结束页统计用左右区间**并集**（两侧同开不会
重复计）。所有 `t_ms` 都是相对实验开始的毫秒数（`performance.now()` 时钟）——
**视频进度条位置从不参与计时**，拖动进度条也不产生任何日志行。

### 实验时间线（可视化）

任何结束方式（倒计时或 Q 键）都会额外生成一份**自包含、可缩放的时间线**（单个
HTML 文件，零外部依赖）：

- 中央纪录片、左右两侧 reels 各一行，外加动作行（触发、A、B、自动弹出、结束）；
- 色条精确显示每条视频的上屏时刻与时长；
- **滚轮缩放**（以光标为锚点）、**拖动平移**，或用**方向键**（←→ 平移、
  ↑↓ 缩放）——长实验横向超出屏幕可左右滑动；**Fit** 复位视图；
- **点击 reel 色条**直接跳转该视频的 Instagram 页面（shortcode 重拼为
  `instagram.com/reel/<code>/` 链接；没有链接的视频不可点击）；
- **悬停视频**显示名称、侧别、起止、时长、作者、点赞数与结束原因——附该视频
  **首帧**（`/frames/<code>/f000.jpg`，由 task.py 从 reel-crawler 的
  `review_frames/` 伺服；文件名不是 Instagram shortcode 的视频、或 file://
  模式下，只显示文字）；
- **拖动图表顶部的拖拽条**可把图表浮到屏幕任意位置（Pin back 还原），
  **Hide data** 可折叠底部数据表；
- 底部 `Data table`（`<details>`）给出一张同样的区间数据表。

时间线在结束时自动下载（结束页有「Download timeline」按钮，防止浏览器拦截
第二次自动下载），经 `task.py` 运行时还会存档到
`data/timeline_<subject>_<stamp>.html`。

## 对接协议（给人脸任务开发者）

任务页通过 **iframe** 嵌入，视频层浮在上方，**不侵入任务页代码**。双向 postMessage：

### 任务页必须做的最小改动

```html
<script>
// 1. 绝对不要调用 window.focus()——键盘始终由模板页接管
// 2. 用消息监听替代 keydown 监听：
window.addEventListener('message', function(ev){
  var m = ev.data;
  if(!m || m.source !== 'fmri-video') return;
  if(m.type === 'key') {
    // 等价于原来的 keydown：m.key 为 "1"、"2" 等
    handleTaskKey(m.key);
  } else if(m.type === 'resume') {
    // 可选：实验已结束（结束页出现时发送）
    resumeTask();
  }
});

// 3. 可选：上报试次事件（合并进同一份 CSV）
function report(event){  // 任意字段，如 {type:'trial', trial:3, rt:412, correct:1}
  window.parent.postMessage({source:'task', type:'event', event: event}, '*');
}

// 4. 可选：加载完成后告知就绪
window.parent.postMessage({source:'task', type:'ready'}, '*');
</script>
```

### 消息表

| 方向 | 消息 | 说明 |
|---|---|---|
| 模板 → 任务 | `{source:'fmri-video', type:'key', key}` | 按键转发（任务页作答键） |
| 模板 → 任务 | `{source:'fmri-video', type:'resume'}` | 实验结束（结束页显示） |
| 任务 → 模板 | `{source:'task', type:'ready'}` | 任务页加载完成 |
| 任务 → 模板 | `{source:'task', type:'event', event:{...}}` | 试次事件，原样记入 CSV |

内置占位任务（设置页留空时）就是按此协议写的，可直接当参考实现。

## 扫描间部署清单

- [ ] Chrome/Edge 打开 index.html，F11 或设置页「全屏」按钮（CLI 启动自动全屏；Esc 退出全屏不结束实验，F4 恢复）
- [ ] 关闭系统通知、更新弹窗；开勿扰模式
- [ ] 确认按钮盒键码 → 设置页填 A / B / 触发键
- [ ] 分别调好纪录片与 reels 的饱和度/音量滑杆（默认静音——只有接扫描间耳机时才开音量）
- [ ] 按本次方案决定是否允许拖动进度条（设置「允许拖动进度条」；CLI `--seek` / `--no-seek`）——若允许，拖动不记日志
- [ ] 按本次方案设定左/右弹出概率
- [ ] 完整试跑一遍（含 CSV **与时间线 HTML**）确认数据无误后再约被试
- [ ] 屏幕亮度：`#taskArea` 背景为 `#808080`（常见投影仪灰），可在 CSS 中调

## 常见问题

- **页面报 manifest 未找到 / 视频不显示** → 确认 videos/manifest.js 存在且路径正确；重跑 `python3 task.py reels-sync --no-download`
- **某视频播不出来** → 转成 H.264 + AAC 的 MP4（如 `ffmpeg -i in.mov -c:v libx264 -pix_fmt yuv420p -c:a aac out.mp4`）
- **改了视频但页面没更新** → 重跑脚本 + 刷新（Ctrl/Cmd+R）
- **为什么不能直接嵌实时 Instagram/TikTok** → 无第三方 feed 接口、iframe 嵌入不可按键控制、依赖网络中途断连风险高；预下载池是可控替代
- **中央视频黑屏** → YouTube 嵌入需要联网；扫描间离线请先下载（如 `yt-dlp URL -o center/center.mp4`）再填本地路径，或留空用内置占位任务
- **导入的视频池播不出来** → 导入池以 `/media/...` 地址由 `task.py` 伺服，请保持服务器运行（`python3 task.py serve`）；或重跑 `python3 task.py reels-sync --no-download` 切回内置 `videos/` 池
- **file:// 限制** → 本模板已规避大部分限制（清单用 script 标签加载而非 fetch）；只有文件夹扫描和时间线缩略图需要服务器：`python3 task.py serve` 后访问 `http://127.0.0.1:8000/`
- **时间线 HTML 没下载** → 浏览器可能拦截连续两次自动下载（CSV + 时间线）。用结束页的「Download timeline」按钮，或到 `data/timeline_*.html` 拿存档（服务器模式）
- **悬停没缩略图** → 只有文件名为 Instagram shortcode 的视频有首帧，由 `task.py` 从同级 `reel-crawler/review_frames/` 伺服（可用环境变量 `FMRI_FRAMES_ROOT` 覆盖），且时间线需经服务器打开（`http://127.0.0.1:8000/data/timeline_*.html`）——离线打开退化为纯文字提示
- **CLI 启动后没进全屏** → 浏览器窗口通过 `--start-fullscreen` 最大化打开，页面还会在第一次按键/点 Start 时再请求 DOM 全屏。若扫描间系统窗口管理器吞掉了 Esc，改用浏览器自带全屏切换即可——实验不受影响
