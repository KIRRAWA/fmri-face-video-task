# Quick Start — fmri-face-video-task

**What this is:** one web page (`index.html`) + one Python file (`task.py`).
The subject watches a center documentary; short Instagram reels pop up on the
left or right side of the screen; the subject presses **A** to open them.
Every key press and every video is logged.

---

## 1. One-time setup (2 minutes)

```bash
# 1a. Sync the reel pool — downloads Instagram reels into videos/
python3 task.py reels-sync
#     (needs python3 and yt-dlp; install with: pip3 install yt-dlp)
#     Works right after unzipping — the repo ships with a pool.json snapshot.
#     For reels the review team approved later, refresh pool.json from the lab
#     repo first (or use the "team review" card where the lab checkout exists).

# 1b. Documentaries live in center/. Videos are too large for GitHub, so the
#     zip ships with none of them — copy the lab's documentaries into center/
#     (this laptop already has all three):
#     center/stimulus_lawn.mp4  ·  center/stimulus_rocky.mp4  ·  center/center.mp4
#     No documentary at hand? Skip this step — pick option 4 (any local MP4)
#     or option 5 (web link) on the settings page instead.
```

Re-run `python3 task.py reels-sync` whenever the pool gains new reels.

**Pick team-approved reels in the browser** (server mode): the settings page
card **Instagram pool · team review** lists the reels the review team has
approved on the lab GitHub repo — tick the ones for this experiment and press
**Apply pool list** (downloads run in the background; tags are kept for a
future preference algorithm).

## 2. Start the experiment

**Simplest (no terminal):** double-click `index.html` → set the options →
press **Start experiment**.

**Terminal:**
```bash
python3 task.py serve          # opens http://127.0.0.1:8000/ in a browser
# or one fully-configured run, no clicks:
python3 task.py run --center lawn --subject P01 --duration 10
```

## 3. Choosing the center documentary

On the settings page, **Center documentary** offers 5 choices:

| Option | What plays |
|---|---|
| 1 · Lawn | `center/stimulus_lawn.mp4` (built-in) |
| 2 · Rocky | `center/stimulus_rocky.mp4` (built-in) |
| 3 · Original | `center/center.mp4` (the original demo, **default**) |
| 4 · Custom video file | a text box appears — put your file in `center/` and type e.g. `center/myvideo.mp4` |
| 5 · Web link | a text box appears — paste a YouTube URL (needs internet) |

Options 4–5 use the text box; options 1–3 ignore it. On the command line the
same choice is `--center lawn|rocky|original|<path>|<url>`.

## 4. Keys during a run

| Key | Action |
|---|---|
| **5** (trigger key) | start the run from the black waiting screen |
| **A** | open/close the pop-up reel (each reopen plays the **next** reel) |
| **B** | next reel |
| **Esc** | leave fullscreen (the run keeps going) |
| **F4** | back to fullscreen |
| **Q** | end the run early (data is still saved) |

## 5. Where the data goes

- **Browser mode** (double-click): a CSV + a timeline HTML download
  automatically when the run ends — check your Downloads folder.
- **Server mode** (`task.py serve`): additionally archived in `data/` —
  one CSV per run (`data/P01_...csv`), all events (`data/events.jsonl`),
  and a zoomable timeline (`data/timeline_...html`).

The timeline HTML is self-contained: open it in any browser to see which
video was on screen at which moment, with every key press marked.

---

# 快速上手 — fmri-face-video-task

**这是什么：** 一个网页（`index.html`）+ 一个 Python 文件（`task.py`）。
受试者观看中央纪录片，屏幕左右随机弹出 Instagram 短视频，受试者按 **A** 打开。
每次按键和每个视频都会被记录。

## 1. 一次性设置（约 2 分钟）

```bash
# 1a. 同步视频池 — 把 Instagram reels 下载到 videos/
python3 task.py reels-sync
#     （需要 python3 和 yt-dlp；安装：pip3 install yt-dlp）
#     解压 zip 后即可直接运行——仓库自带 pool.json 快照。
#     想加入审核团队后来新通过的 reels，先从实验室仓库刷新 pool.json
#     （或是在有实验室 checkout 的机器上用设置页的「团队审核」卡片）。

# 1b. 纪录片放在 center/ 里。视频太大进不了 GitHub，zip 里不包含纪录片——
#     把实验室的纪录片拷进 center/（本机已放好三个）：
#     center/stimulus_lawn.mp4 · center/stimulus_rocky.mp4 · center/center.mp4
#     手上没有纪录片？跳过这步——在设置页改用选项 4（任意本地 MP4）
#     或选项 5（网络链接）。
```

视频池加入新视频后，重新跑一次 `python3 task.py reels-sync` 即可。

**在浏览器里挑选团队已通过的 reels**（服务器模式）：设置页的
**Instagram 视频池 · 团队审核** 卡片列出审核团队在实验室 GitHub 仓库上
已通过的 reels——勾选本实验要用的，点 **应用视频池列表**（下载在后台
进行；标签会保留下来供将来的 preference 算法使用）。

## 2. 开始实验

**最简单（不开终端）：** 双击 `index.html` → 调好设置 → 点 **Start experiment**。

**终端：**
```bash
python3 task.py serve          # 浏览器自动打开 http://127.0.0.1:8000/
# 或者一条命令直接跑（无需点鼠标）：
python3 task.py run --center lawn --subject P01 --duration 10
```

## 3. 选择中央纪录片

设置页的 **Center documentary** 有 5 个选项：

| 选项 | 播放内容 |
|---|---|
| 1 · Lawn | `center/stimulus_lawn.mp4`（内置） |
| 2 · Rocky | `center/stimulus_rocky.mp4`（内置） |
| 3 · Original | `center/center.mp4`（原版演示视频，**默认**） |
| 4 · 自选本地文件 | 出现输入框——把视频放进 `center/`，然后填如 `center/myvideo.mp4` |
| 5 · 网络链接 | 出现输入框——粘贴 YouTube 链接（需要联网） |

选项 4–5 使用输入框；选项 1–3 忽略输入框。命令行同样可选：
`--center lawn|rocky|original|<路径>|<链接>`。

## 4. 实验中的按键

| 按键 | 作用 |
|---|---|
| **5**（触发键） | 从黑屏等待界面开始实验 |
| **A** | 打开/关闭弹出短视频（每次重新打开都会播**下一条**） |
| **B** | 下一条短视频 |
| **Esc** | 退出全屏（实验继续） |
| **F4** | 恢复全屏 |
| **Q** | 提前结束实验（数据照常保存） |

## 5. 数据在哪里

- **浏览器模式**（双击打开）：结束时自动下载 CSV + 时间线 HTML——在 Downloads 文件夹找。
- **服务器模式**（`task.py serve`）：额外存档到 `data/`——每次实验一个 CSV
  （`data/P01_...csv`）、全部事件（`data/events.jsonl`）、可缩放的时间线
  （`data/timeline_...html`）。

时间线 HTML 自包含：用任意浏览器打开即可查看每个时刻屏幕上是哪条视频，
每次按键都有标记。
