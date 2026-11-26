# pet-dress —— 给 dsh-pet 的换装，自带四套衣服

一个 **DSH 插件**，给 [dsh-pet](https://github.com/PC2005-cloud/dsh-pet) 加右键换装：
点一下换整套外观 + 动作。**四套衣服打包在插件里**，装上就有，不用手动拷宠物包。

**不改上游一行代码**：只走 dsh-pet 的公开 HTTP 接口（`/menu/item`、`/menu/events`、`/pet-display`）
和它自己的 `pet/` 目录约定。

## 环境要求

- DSH（DeepSeek Harness）
- **dsh-pet >= 0.4.8**（写这个时最新版是 0.4.8，2026-11-12）
- Node.js >= 22

**没装 dsh-pet 会怎样**：插件启动时会先探一下 `/dsh-pet-7340/state`，探不到就什么都不做——
不往 `~/.dsh/dsh-pet/` 写包、不注册菜单，日志里明确提示先把 dsh-pet 装进同一个 profile。
「更多」菜单是 dsh-pet 自己拼的（有第三方菜单项才出现），不需要额外装别的插件。

## 四套衣服

| 默认桌宠名 | 主题 | 动作数 |
|---|---|---|
| 鲸雪冬装 | 鲸雪同游 | 24 |
| 圣诞鲸装 | 鲸诞快乐 | 23 |
| 鲸绒毛衣 | 鲸绒暖冬 | 23 |
| 鲸蝠夜装 | 鲸蝠夜巡 | 23 |

每套都覆盖这些槽位（缺一个整只宠物会回退到内置默认，等于那套衣服白做）：

- `idle` 待机 / `turn` 转向 / `drag` 被拖拽
- `clicks` 点击回应 ×5（开心招手 / 傲娇生气 / 害羞捂嘴 / 挠痒咯咯笑 / 元气挥手）
- `moves` 走路 / 小跑
- `events.workStatus` 工作状态 ×6（思考 / 忙碌 / 整理 / 等待 / 收尾 / 出错）
- `events.balance` 余额 ×6（满溢 / 满溢 / 如常 / 皱眉 / 皱眉 / 分文不剩）
- `sleep` 睡觉三段（开始 / 循环 / 起来）

素材统一 **640×360、VP9-alpha、30fps**，透明背景，直接播。

## 安装

在 DSH 的 profile 目录里：

```bash
pnpm add file:/path/to/pet-dress
```

然后把 `pet-dress` 写进 profile 的 `dsh.profile.bundles`，重启 DSH。

**首次启动**时插件会把自带的四套包装进 `~/.dsh/dsh-pet/pet/`。
如果重启后右键里没看到四套，**再重启一次**——dsh-pet 可能先扫了目录、插件后装。

装好后右键 →「换装：鲸雪冬装」……点哪套换哪套，其余自动收起。

## 名字（改的是桌宠名，不是衣服名）

换装换的是「整套外观 + 动作」，**桌宠叫什么名字不在换装范围内**——那是你自己的事。

- `pets[].name` 是**桌宠的显示名**：右键菜单、碎碎念里的自称都来自它。
- 我们只在里面填了一个占位默认值（就是衣服名），只是让你装完有个名字可用。
- 想要自己的角色名，直接改：dsh-pet 设置里改，或改 `~/.dsh/dsh-pet/pet/<kind>-config.json` 里的 `pets[].name`。
- 改名只影响显示和自称，跟素材无关——素材按动作名找文件，宠物叫什么都不影响播哪段。
- **衣服名**（鲸雪冬装 / 圣诞鲸装 / 鲸绒毛衣 / 鲸蝠夜装）和**主题**（鲸雪同游……）是这套衣服的标识，不用改。

## 换装模式

插件自己的配置在 `~/.dsh/pet-dress/config.json`：

```json
{ "mode": "single" }
```

| mode | 行为 |
|---|---|
| `single`（默认） | 换装：点哪套换哪套，其余收起（互斥，一次穿一套） |
| `multi` | 每套单独开/关，菜单里多一项「换装：全部显示」 |

没有这个文件、或内容不合法，一律按 `single`。

## 装机规则

插件只做「补缺」，不做「覆盖」：

- 缺哪套补哪套；四套都在就不动
- 已有的 `*-config.json` **不覆盖**（你改过名字的版本会保留）
- 素材文件缺了才补，不覆盖你替换过的
- **不删**你别的宠物包

新加的宠物包（你自己做的）不需要插件管——dsh-pet 重启后自己就认。

---

## 怎么做一套新衣服（工具链）

> 规范照上游 `MAKE-YOUR-OWN-PET.md`：绿幕 `#00FF00`、约 10 秒、头顶约 20% 高度、脚底约 85% 高度、首尾正面站立。
> **实测以真素材为准**：内置素材是头顶 17.8% / 脚底 91.4%，跑的时候用 `--top 0.178 --feet 0.914`。

工具链在 `tools/`（clone 仓库直接用；npm 装的在 `node_modules/pet-dress/tools/`）。
依赖：Python 3、ffmpeg（带 libvpx-vp9）、Pillow、numpy。

### 一条命令的长度

```bash
# 1) 绿幕视频 → 透明 webm
python tools/build_anim.py --video raw/idle.mp4 --name 待机呼吸 --out pack/我的-新衣服-animation --top 0.178 --feet 0.914

# 2) 建宠物包骨架（只在第一次做）
python tools/make_pack.py --name 我的-新衣服 --action 待机呼吸 --display desktop

# 3) 完全退出 DSH 再打开，右键会多出这一「种类」
```

单张图试抠像：

```bash
python tools/build_anim.py --image raw/cover.png --mode ai --out-png test/cut.png
```

### 抠像两条路

| 模式 | 什么时候用 | 说明 |
|---|---|---|
| `chroma`（默认，绿幕） | 即梦/可灵/豆包出的绿幕视频 | HSV 判绿 + 去溢色 + 羽化；**纯绿背景才准** |
| `ai` | 没有绿幕、背景复杂 | u2netp ONNX 通用抠像，本地 CPU |
| `auto`（默认值） | 拿不准 | 绿占比 > 25% 走 chroma，否则走 ai |

`ai` 模式需要 `models/u2netp.onnx`（4.6 MB），自己下；仓库里不附带（`.gitignore` 挡着）。

### 对齐与质检

- 画布 640×360，角色高约 234px（20%→85%），水平居中，脚底 y≈306。
- **整段共用一个变换**（取所有帧包围盒的并集），避免逐帧抖动。
- 跳跃/带道具/换装动作加 `--align-first`：以首帧高度做缩放和放置锚点，否则站立帧变矮、脚底悬空。
- alpha 检查要用 **libvpx 解码器**，默认解码器看不到 VP9 的 alpha，会给你一片 255（别据此判失败）：

  ```bash
  ffmpeg -v error -c:v libvpx-vp9 -i out.webm -vf alphaextract -f rawvideo - | wc -c
  # 应该 = 帧数 × 230400
  ```

- 睡觉是三段接力：`start` / `loop` / `end`，**循环段首尾帧必须完全一样**，否则睡觉会跳。

### 加一个动作（给已有的一套）

1. 新动作的 webm 放进那套的 `*-animation/`，**文件名 = 动作名**。
2. 在对应的 `*-config.json` 的 `animations` 里引用这个名字（五个点击回应往 `clicks` 数组里加，余额/工作状态往 `events.*` 的数组里加）。
3. 落盘后点 DSH 里的「重载配置」。

**槽位可以复用同一段视频**：五个点击回应指同一段、六个余额档指同一段，最少 6~8 段就能跑起来一套衣服。先拿占位动作把所有槽位填满，再一段段替换。

### 三个硬坑（都踩过）

1. **`events.balance` 不能删**。删了整段 `animations` 判非法，整套动作回退成内置默认——等于衣服白做。
2. **六档要补齐**。`workStatus` 和 `balance` 的数组必须各有 6 格（余额按 0..5 取档）；少一格就索引越界、不播动画。
3. **`make_pack.py` 生成的两组只有 1 档**。新包生成后第一件事就是把这两组补到 6 档，别以为骨架里那 1 格能用。

其它老坑：

- **素材天生就大**：dsh-pet 是视频渲染，每个动作都是烧进视频的（不是骨骼/精灵图），一套衣服 15~20MB 是正常的——原生 dsh-pet 自己的 `assets/webm` 也有 56MB / 114 段，我们在同一量级。想省体积只能降 CRF、缩短时长或降分辨率，都会牺牲画质；用 PNG/WebP 替代不行，播放器播的是 `<video>`。
- **中文文件名**：shell 里没问题；但 **Python subprocess 把中文路径传给 ffmpeg 会炸**，中间产物一律用 ASCII 名，最后再改成中文。
- **素材只查自己目录**：包里引用了但目录里没有的名字 = 404，那只宠物就播不出来。
- **改完要完全重启 DSH**（换动作只重载配置，加新包必须重启）。

---

## 它怎么工作（想写自己的 dsh-pet 插件可以看）

`index.js` 只有三处 HTTP 调用：

| 目的 | 调用 |
|---|---|
| 注册右键菜单 | `POST /dsh-pet-7340/menu/item`，body `{ owner, labels: ["换装：…"], target: "both" }` |
| 收点击 | `GET /dsh-pet-7340/menu/events?owner=<owner>`——**读即消费**，每 300ms 轮询一次 |
| 切显示 | `POST /dsh-pet-7340/pet-display`，body `{ id, display: "desktop" | "none" }` |

- 端口不是写死的 `7340`，从宿主 `webServer.port` 取（见 `makeApi`）。
- 第三方菜单**只有同 owner 下 label 重名才会分组**，所以是平铺的，做不出「换装 → 衣服名」二级。
- 菜单登记会丢（宿主重启等），读到 `reason: "unknown-owner"` 就重新注册。

## 目录结构

```
pet-dress/
├── index.js                 ← 插件本体：装机 + 换装
├── package.json
├── cordis.patch.yml
├── README.md
├── LICENSE                  ← 代码：MIT
├── LICENSE-ASSETS           ← 四套素材：CC BY-NC 4.0
├── pets/                    ← 自带的四套衣服
│   ├── bubble-rain-config.json
│   ├── bubble-rain-animation/*.webm
│   ├── xmas-config.json
│   ├── xmas-animation/
│   ├── sweater-config.json
│   ├── sweater-animation/
│   ├── bat-config.json
│   └── bat-animation/
└── tools/
    ├── build_anim.py        ← 绿幕视频 / 单图 → 640×360 VP9-alpha
    ├── make_pack.py         ← 生成 <名>-config.json + 素材目录骨架
    └── make_firstframe.py   ← 立绘（白底）→ 16:9 纯绿首帧
```

`raw/`、`test/`、`pp*/`、`models/*.onnx` 是本地工作目录，不进仓库。

## 许可

| 部分 | 许可 |
|---|---|
| 代码（`index.js`、`tools/`） | **MIT**，见 [LICENSE](LICENSE) |
| 四套衣服素材（`pets/` 下的 webm 与形象） | **CC BY-NC 4.0**，**禁止商业使用**，见 [LICENSE-ASSETS](LICENSE-ASSETS) |

- 素材由 **豆包 Seedance 2.0** 制作，角色形象为**二创**；再经本地脚本抠像、对齐、转码。
- 这里只声明非商业使用限制：禁止商用，非商业使用时请署名，商用请先联系。
- 上游 dsh-pet 是 MIT（© 2026 PC2005-cloud）。
