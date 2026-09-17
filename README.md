# fMRI · Face Task + Short-Form Video Browsing (Dual-Mode Template)

Subjects perform a boring face-recognition task in the scanner while voluntarily browsing short-form videos.
**Key A** = open/close the video, **Key B** = next video. Two video modes, chosen by the experimenter before the run.

```
fmri-face-video-task/
  index.html              # main page (single file, double-click to open, works offline)
  generate_manifest.py    # scans videos/ and generates the video manifest
  videos/
    manifest.js           # video manifest (auto-generated)
    *.mp4                 # lab-provided short videos (optional)
  README.md
```

## Quick start

1. Open `index.html` in Chrome (double-click — no server, no network needed)
2. On the settings page, pick a mode and parameters → **Fullscreen** → **Start experiment**
3. (Trigger mode) The screen stays black until the trigger key (default `5`)
4. When the run ends, statistics are shown and the CSV is downloaded automatically

## Two video modes

| | Mode 1 · Slide-in panel | Mode 2 · Full-page switch |
|---|---|---|
| Press A | A vertical (9:16) video panel slides in from the right; the task area shifts left and **keeps running in parallel** | The whole page switches to the video feed; the task page is hidden |
| Press B | Next video | Next video |
| Press A again | Panel collapses, task area restored | Back to the task page |
| Mode 2 task behavior | — | Setting: **keep running hidden** (default) / **pause via message** (needs task-page support) |

Panel width = CSS variable `--panel-w` (in `:root` of index.html, default 34%).

## Settings

| Setting | Description |
|---|---|
| Video mode | Mode 1 / Mode 2 |
| Task behavior in Mode 2 | Keep running hidden / Pause via message (falls back to hidden + logged warning if the task page doesn't support it) |
| Video source | Auto / real videos only / placeholder clips only (debugging) |
| Run duration | Minutes, decimals allowed |
| Task page | Path to the face-task page (empty = built-in placeholder task). **Filling this in is the "integration"** |
| Start mode | Wait for trigger key (black screen — for scanner pulse) / start immediately |
| Trigger key | Default `5`; scanner pulse boxes usually map to 5 or t |
| Keys A / B | Remappable (button boxes send standard key codes, same as a keyboard) |
| Sound | Muted by default (scanner rooms are loud; use MR-compatible headphones if enabled) |
| TikTok-style decorations | Like column / user info / progress bar on/off |
| Subject ID / Note | Written into the CSV |

Settings are remembered automatically (localStorage).

## Video pool

1. Put short videos (`.mp4`/`.webm`, ideally H.264+AAC) into `videos/`
2. Run `python3 generate_manifest.py` (or edit `videos/manifest.js` by hand)
3. Reopen index.html — the settings page shows "N real video(s) detected"

Playback rules: randomized order, no immediate repeats, endless looping, B advances clip by clip — mimics a live feed.
Copyright note: real videos for the study must be provided by the lab (own account content or licensed content). This template ships no real videos — the placeholder clips are animated, not real.

## Key reference

| Key | Action |
|---|---|
| A (remappable) | Open / close the video |
| B (remappable) | Next video |
| 1 / 2 | Forwarded to the task page (face-task responses) |
| Trigger (default 5) | Start the run from the black screen |
| Esc | End the run early (logged) |
| R | Back to settings (end screen) |

Button boxes act as standard keyboards; key codes match a normal keyboard, so just fill in the actual codes per your lab's convention. This page always owns the keyboard — the task page must never call `focus()`.

## Language

The settings page has an **EN / 中文** toggle at the top right; the choice is remembered. All on-screen texts follow the selected language — settings, usage guide, integration protocol, trigger-wait screen, end screen, and the placeholder task inside the iframe. Data logs and CSV output stay in English regardless, for analysis consistency.

## Subject instructions (what the subject does)

During the run the subject performs the face task. At any moment they can:

- press **A** to open the video — Mode 1: a vertical panel slides in from the right while the task keeps running; Mode 2: the whole page switches to the video
- press **B** to go to the next video
- press **A** again to close the video and return to the task

That is the entire video interaction — no mouse, no other keys. Whether and how long they browse is entirely up to them. Task responses use keys 1 / 2. The same instructions are available on the settings page under "Subject instructions (show before the run)".

## Data logging

Every event is one CSV row with millisecond timestamps (t=0 is the trigger/start moment); downloaded automatically at the end:

`t_ms, subject, type, key, value, note`

| type | Meaning |
|---|---|
| session_start | Run start (note contains full config) |
| trigger | Scanner trigger received |
| key | Every key this page receives (note: press/repeat) |
| video_open / video_close | Video opened/closed (value = clip name) |
| video_next | B pressed, next clip (value = clip name) |
| video_play / video_error | Clip loaded successfully / failed |
| task_event | Events reported by the task page (value = event type, note = JSON) |
| task_ready / warn_* | Integration status and warnings |
| run_end | Run finished (value = timeout/abort) |

End-screen stats: times opened, scrolls, total viewing time, per-clip viewing time.

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
  } else if(m.type === 'pause') {
    // optional: pause timing and trial presentation (Mode 2, video open)
    pauseTask();
  } else if(m.type === 'resume') {
    // optional: resume
    resumeTask();
  }
});

// 3. Optional: report trial events (merged into the same CSV)
function report(event){  // any fields, e.g. {type:'trial', trial:3, rt:412, correct:1}
  window.parent.postMessage({source:'task', type:'event', event: event}, '*');
}

// 4. Optional: send on load (required for Mode 2 "Pause" support)
window.parent.postMessage({source:'task', type:'ready'}, '*');
</script>
```

### Message table

| Direction | Message | Description |
|---|---|---|
| Template → task | `{source:'fmri-video', type:'key', key}` | Forwarded key (the task page's response keys) |
| Template → task | `{source:'fmri-video', type:'pause'}` | Pause the task while Mode 2 video is open (only when the setting is "Pause") |
| Template → task | `{source:'fmri-video', type:'resume'}` | Resume |
| Task → template | `{source:'task', type:'ready'}` | Task page loaded |
| Task → template | `{source:'task', type:'event', event:{...}}` | Trial events, logged into the CSV as-is |

The built-in placeholder task (settings left empty) is written against exactly this protocol — use it as the reference implementation.

## Scanner-room deployment checklist

- [ ] Open index.html in Chrome/Edge; F11 or the **Fullscreen** button
- [ ] Disable system notifications / update popups; enable Do Not Disturb
- [ ] Confirm button-box key codes → fill in A / B / trigger key on the settings page
- [ ] Video is muted by default; if sound is needed, connect MR headphones and tick "Play sound"
- [ ] Run one full pilot session (including the CSV download) and check the data before booking subjects
- [ ] Screen brightness: `#taskArea` background is `#808080` (common projector gray), adjustable in the CSS

## FAQ

- **Page says manifest not found / videos don't play** → make sure videos/manifest.js exists with correct paths; rerun `python3 generate_manifest.py`
- **A video won't play** → transcode to H.264 + AAC MP4 (e.g. `ffmpeg -i in.mov -c:v libx264 -pix_fmt yuv420p -c:a aac out.mp4`)
- **Changed videos but the page doesn't update** → rerun the script + refresh (Ctrl/Cmd+R)
- **Why not embed live TikTok directly** → TikTok offers no third-party feed API, iframe embeds can't be key-controlled, and a network dependency is risky mid-scan; a pre-downloaded pool is the controllable alternative
- **file:// limitations** → this template already works around them (manifest loads via a script tag instead of fetch); for HTTP: `python3 -m http.server` then visit `http://localhost:8000/`

---

# fMRI · 人脸任务 + 短视频浏览（双模式模板）

受试者在扫描仪内做枯燥的人脸识别任务，同时可自愿刷短视频。**A 键** = 开/关视频，**B 键** = 下一条视频。两种视频模式由科学家在实验前选择。

```
fmri-face-video-task/
  index.html              # 主页面（单文件，双击即开，离线可用）
  generate_manifest.py    # 扫描 videos/ 生成视频清单
  videos/
    manifest.js           # 视频清单（自动生成）
    *.mp4                 # 实验室自备的短视频（可选）
  README.md
```

## 快速开始

1. Chrome 打开 `index.html`（双击即可，无需服务器、无需联网）
2. 设置页选好模式与参数 → **全屏** → **开始实验**
3. （触发模式）黑屏等待，按触发键（默认 `5`）开始
4. 到时间自动结束 → 结束页显示统计并自动下载 CSV

## 两种视频模式

| | 模式 1 · 侧滑面板 | 模式 2 · 整页切换 |
|---|---|---|
| 按 A | 右侧滑出竖屏(9:16)视频面板，任务区左移、任务**继续并行** | 整页切到视频流，任务页隐藏 |
| 按 B | 下一条视频 | 下一条视频 |
| 再按 A | 面板收起，任务区恢复 | 回到任务页 |
| 模式 2 任务行为 | — | 设置项二选一：**隐藏继续**（默认）/ **消息暂停**（需任务页支持） |

面板宽度 = CSS 变量 `--panel-w`（index.html 内 `:root`，默认 34%）。

## 设置项

| 设置 | 说明 |
|---|---|
| 视频模式 | 模式 1 / 模式 2 |
| 模式 2 任务行为 | 隐藏继续 / 消息暂停（任务页不支持时自动退化并记入日志） |
| 视频来源 | 自动 / 仅真实视频 / 仅占位动画（调试） |
| 实验时长 | 分钟，可小数 |
| 任务页面 | 人脸任务页面路径（留空 = 内置占位任务）。**填这个就是「接入」** |
| 开始方式 | 等待触发键（黑屏，适合扫描脉冲）/ 立即开始 |
| 触发键 | 默认 `5`，按钮盒接 TTL 脉冲通常映射 5 或 t |
| A / B 键 | 可改（按钮盒键码与键盘一致） |
| 声音 | 默认静音（扫描间噪音大；开声需扫描间耳机） |
| TikTok 装饰 | 点赞列 / 用户信息 / 进度条开关 |
| 受试者编号 / 备注 | 写入 CSV |

设置自动记忆（localStorage）。

## 视频池

1. 把短视频（`.mp4`/`.webm`，建议 H.264+AAC）放进 `videos/`
2. 运行 `python3 generate_manifest.py`（或手动编辑 `videos/manifest.js`）
3. 重开 index.html，设置页会显示「检测到 N 条真实视频」

播放规则：随机排序、同条不连续、循环不到头，B 键逐条切换——模拟「实时推荐流」。
版权提醒：正式实验视频由实验室自备（自己账号内容或获授权内容），本模板不内置任何真实视频——内置的是动画占位内容，不是真实视频。

## 按键总表

| 键 | 功能 |
|---|---|
| A（可改） | 开/关视频 |
| B（可改） | 下一条视频 |
| 1 / 2 | 转发给任务页（人脸任务作答） |
| 触发键（默认 5） | 黑屏时开始实验 |
| Esc | 提前结束（记入日志） |
| R | 返回设置（仅结束页） |

按钮盒即标准键盘，键码映射与普通键盘一致，按实验室惯例在设置页填实际键码即可。键盘始终由本页接管，任务页不得调用 `focus()`。

## 语言

设置页右上角有 **EN / 中文** 切换按钮，选择会被记住。所有界面文字跟随所选语言——设置页、使用指南、对接协议、触发等待屏、结束页、iframe 内的占位任务。数据日志与 CSV 始终为英文，保证分析一致。

## 被试说明（被试要做什么）

实验中受试者做人脸任务，同时随时可以：

- 按 **A** 打开视频——模式 1：右侧滑出竖屏面板，任务继续并行；模式 2：整页切到视频
- 按 **B** 看下一条视频
- 再按 **A** 收起视频、回到任务

这就是全部视频操作——不用鼠标、没有其他键。是否刷、刷多久完全自愿。任务作答用 1 / 2 键。同样内容在设置页「被试说明（实验前展示）」中可查。

## 数据记录

所有事件一行一条，毫秒时间戳（t=0 为触发/开始时刻），结束自动下载 CSV：

`t_ms, subject, type, key, value, note`

| type | 含义 |
|---|---|
| session_start | 开始（note 含全部配置） |
| trigger | 扫描触发 |
| key | 本页收到的每个按键（note: press/repeat） |
| video_open / video_close | 视频打开/关闭（value=视频名） |
| video_next | B 键换下一条（value=视频名） |
| video_play / video_error | 视频加载成功/失败 |
| task_event | 任务页上报的事件（value=事件类型，note=JSON） |
| task_ready / warn_* | 对接状态与警告 |
| run_end | 结束（value=timeout/abort） |

结束页统计：打开次数、滚动次数、总观看时长、每条视频观看时长。

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
  } else if(m.type === 'pause') {
    // 可选：暂停计时与出题（模式 2 视频打开期间）
    pauseTask();
  } else if(m.type === 'resume') {
    // 可选：恢复
    resumeTask();
  }
});

// 3. 可选：上报试次事件（合并进同一份 CSV）
function report(event){  // 任意字段，如 {type:'trial', trial:3, rt:412, correct:1}
  window.parent.postMessage({source:'task', type:'event', event: event}, '*');
}

// 4. 可选：加载完成后发送（启用模式 2「暂停」功能的前提）
window.parent.postMessage({source:'task', type:'ready'}, '*');
</script>
```

### 消息表

| 方向 | 消息 | 说明 |
|---|---|---|
| 模板 → 任务 | `{source:'fmri-video', type:'key', key}` | 按键转发（任务页作答键） |
| 模板 → 任务 | `{source:'fmri-video', type:'pause'}` | 模式 2 视频打开时暂停任务（仅当设置选「暂停」） |
| 模板 → 任务 | `{source:'fmri-video', type:'resume'}` | 恢复 |
| 任务 → 模板 | `{source:'task', type:'ready'}` | 任务页加载完成 |
| 任务 → 模板 | `{source:'task', type:'event', event:{...}}` | 试次事件，原样记入 CSV |

内置占位任务（设置页留空时）就是按此协议写的，可直接当参考实现。

## 扫描间部署清单

- [ ] Chrome/Edge 打开 index.html，F11 或设置页「全屏」按钮
- [ ] 关闭系统通知、更新弹窗；开勿扰模式
- [ ] 确认按钮盒键码 → 设置页填 A / B / 触发键
- [ ] 视频默认静音；如需声音，连接扫描间耳机并勾选「播放声音」
- [ ] 完整试跑一遍（含 CSV 下载）确认数据无误后再约被试
- [ ] 屏幕亮度：`#taskArea` 背景为 `#808080`（常见投影仪灰），可在 CSS 中调

## 常见问题

- **页面报 manifest 未找到 / 视频不显示** → 确认 videos/manifest.js 存在且路径正确；重跑 `python3 generate_manifest.py`
- **某视频播不出来** → 转成 H.264 + AAC 的 MP4（如 `ffmpeg -i in.mov -c:v libx264 -pix_fmt yuv420p -c:a aac out.mp4`）
- **改了视频但页面没更新** → 重跑脚本 + 刷新（Ctrl/Cmd+R）
- **为什么不能直接嵌实时 TikTok** → TikTok 无第三方 feed 接口、iframe 嵌入不可按键控制、依赖网络中途断连风险高；预下载池是可控替代
- **file:// 限制** → 本模板已规避（清单用 script 标签加载而非 fetch）；如需 HTTP：`python3 -m http.server` 后访问 `http://localhost:8000/`
