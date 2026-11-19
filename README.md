# pet-dress —— 给泡泡做服饰 / 新动作的工坊

目标：把 AI 生成的绿幕视频，变成 dsh-pet 能播的**透明动画**（VP9-alpha webm），
再装进一个「宠物种类包」里，右键能换、能播。

> 规范不是我定的，是照上游 `MAKE-YOUR-OWN-PET.md` 抄的：绿幕 `#00FF00`、10 秒、
> 头顶约 20% 高度、脚底约 85% 高度、首尾正面站立。

## 一条命令的长度

```bash
# 1) 绿幕视频 → 透明 webm（自动判断绿幕色键 / 通用抠像）
python tools/build_anim.py --video raw/待机呼吸.mp4 --name 待机呼吸 --out pack/bubble-rain-animation

# 2) 建宠物包骨架（只在第一次做）
python tools/make_pack.py --name bubble-rain --action 待机呼吸 --display desktop

# 3) 完全退出 DSH 再打开，右键会多出这一「种类」
```

单张图（只是试抠像效果，不进包）：

```bash
python tools/build_anim.py --image raw/cover.png --mode ai --out-png test/cut.png
```

## 抠像两条路

| 模式 | 什么时候用 | 说明 |
|---|---|---|
| `chroma`（默认，绿幕） | 即梦/可灵出的绿幕视频 | HSV 判绿 + 去溢色 + 羽化；**纯绿背景才准** |
| `ai` | 没有绿幕、背景复杂 | u2netp ONNX 通用抠像，本地 CPU |
| `auto`（默认值） | 拿不准 | 绿占比 > 25% 走 chroma，否则走 ai |

模型在 `models/u2netp.onnx`（4.6 MB，已下好）。`--mode ai` 时才加载。

## 对齐规则（脚本已内置）

- 画布 **640×360**，角色高约 **234px**（20%→85%）
- 水平居中、脚底落在 **y≈306**
- **整段共用一个变换**（取所有帧包围盒的并集），避免逐帧抖动
- 输出 30fps、VP9-alpha、CRF 32，`alpha_mode=1`

## 质检清单（每次出片都过一遍）

1. **alpha 真的有吗** —— 用 libvpx 解码器，不用 ffmpeg 默认解码器：

   ```bash
   ffmpeg -v error -c:v libvpx-vp9 -i out.webm -vf alphaextract -f rawvideo - | wc -c
   # 结果应该是 帧数 × 230400
   ```

   > 坑：ffmpeg 默认解码器**看不到 VP9 的 alpha**，会给你一片 255——别据此判断失败。
   > 上游现成的 `待机呼吸休闲.webm` 用默认解码器读也是 255，用 libvpx 读才对。

2. **轮廓干不干净** —— 头发丝、裙摆、手指边缘有没有绿边/缺块
3. **首尾帧** —— 循环动作首尾要能接上；换装动作首尾回到正面站立
4. **位置一致** —— 和套装里其它动作对比，角色大小、脚底线要对齐

## 宠物包放哪

```
~/.dsh/dsh-pet/pet/
├── bubble-rain-config.json     ← 种类配置（脚本生成）
└── bubble-rain-animation/      ← 素材，平铺
    ├── 待机呼吸.webm
    └── ...
```

**素材只查自己目录**：包里引用了但目录里没有的名字 = 404，那只宠物就播不出来。
所以先用一个占位动作把所有槽位填满，再一段段替换。

## 槽位复用（省工作量）

必须有的槽位是 `idle` / `turn` / `drag` / `clicks` / `moves` / `categories` / `events`
（`events` 里必须带 `balance`）。但**多个槽位可以指向同一段视频**：
五个余额档位指同一段、四个点击回应指同一段，于是**最少 6~8 段动作就能跑起来一套衣服**。

## 常见坑

- **中文文件名**：ffmpeg 命令行里传中文路径容易炸（本次测试就炸过一次），中间产物用 ASCII 名，最后再改成中文名。
- **睡眠是三段接力**：`start` / `loop` / `end`，循环段首尾帧必须完全一样，否则睡觉会跳。不写 `animations.sleep` 就没有睡觉菜单。
- **改完要完全重启 DSH**：宠物包的扫描在宿主启动时做，热重载不认新包。

## 现在的状态

- 流水线已用合成绿幕验证通：`绿幕 mp4 → 抠像 → 对齐 → 640×360 VP9-alpha`，
  alpha 用 libvpx 解码器验过（30 帧 × 230400 字节，轮廓不透明占比 23%）。
- **还没接过真实的即梦素材**——那是周六的事。
