#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一段视频 → 一个透明动画（VP9-alpha webm）或一张抠好的 PNG。

两种抠像模式：
  --mode chroma  绿幕色键（上游默认路线，源视频必须纯绿 #00FF00）
  --mode ai      u2netp ONNX 通用抠像（没有绿幕时兜底）

对齐规则（照抄上游 MAKE-YOUR-OWN-PET.md）：
  画布 640×360；角色头顶约在 20% 高度、脚底约在 85% 高度；水平居中。
  以所有帧包围盒的**并集**算一个统一变换，整段共用 —— 避免逐帧抖动。

用法：
  python build_anim.py --video in.mp4 --name 待机呼吸 --out <pack>/pet/x-animation
  python build_anim.py --image cover.png --mode ai --out-png cut.png
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageFilter

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE", "ffprobe")

CANVAS_W, CANVAS_H = 640, 360
TOP_RATIO, FEET_RATIO = 0.20, 0.85      # 头顶 20%、脚底 85%
CHAR_H = int(round((FEET_RATIO - TOP_RATIO) * CANVAS_H))   # ≈234px
FEET_Y = int(round(FEET_RATIO * CANVAS_H))                 # ≈306px
FPS = 30


# ---------------- 抠像 ----------------

def cutout_chroma(rgb: np.ndarray, tolerance: int = 60, despill: float = 0.6) -> np.ndarray:
    """绿幕色键：返回 0-255 的 alpha。绿通道明显强于红蓝且不太亮偏 → 判为背景。"""
    r, g, b = rgb[..., 0].astype(np.int16), rgb[..., 1].astype(np.int16), rgb[..., 2].astype(np.int16)
    # 绿度：g 比 r/b 高出多少
    green_excess = g - np.maximum(r, b)
    alpha = np.where(green_excess > tolerance, 0, 255).astype(np.uint8)
    # 半透明过渡带：在阈值附近做线性羽化
    band = (green_excess > tolerance * 0.4) & (green_excess <= tolerance)
    alpha[band] = np.clip(255 * (1 - (green_excess[band] - tolerance * 0.4) / (tolerance * 0.6)), 0, 255).astype(np.uint8)
    return alpha


def _despill(rgb: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """去溢色：把背景绿反到边缘上的绿污染压掉。"""
    out = rgb.astype(np.float32).copy()
    r, g, b = out[..., 0], out[..., 1], out[..., 2]
    over = np.maximum(0, g - np.maximum(r, b))
    out[..., 1] = g - over * 0.85
    out[..., 0] = r + over * 0.10
    out[..., 2] = b + over * 0.10
    return np.clip(out, 0, 255).astype(np.uint8)


class U2Net:
    """u2netp ONNX 通用抠像（输入 320×320，输出 sigmoid 掩膜）。"""

    def __init__(self, model_path: str):
        import onnxruntime as ort
        self.sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self.input_name = self.sess.get_inputs()[0].name
        self.size = 320

    def mask(self, rgb: np.ndarray) -> np.ndarray:
        img = Image.fromarray(rgb).resize((self.size, self.size), Image.BILINEAR)
        arr = np.asarray(img, dtype=np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        arr = (arr - mean) / std
        x = arr.transpose(2, 0, 1)[None].astype(np.float32)
        pred = self.sess.run(None, {self.input_name: x})[0][0, 0]
        pred = (pred - pred.min()) / max(pred.max() - pred.min(), 1e-6)
        m = Image.fromarray((pred * 255).astype(np.uint8)).resize((rgb.shape[1], rgb.shape[0]), Image.BILINEAR)
        return np.asarray(m, dtype=np.uint8)


def cut_image(rgb: np.ndarray, mode: str, u2net: "U2Net | None") -> np.ndarray:
    if mode == "chroma":
        a = cutout_chroma(rgb)
    elif mode == "ai":
        if u2net is None:
            raise SystemExit("ai 模式需要 --model 指向 u2netp.onnx")
        a = u2net.mask(rgb)
    else:
        raise SystemExit("mode 只能是 chroma / ai")
    # 统一做一次轻微羽化，边缘不锯齿
    a = np.asarray(Image.fromarray(a).filter(ImageFilter.GaussianBlur(0.8)), dtype=np.uint8)
    return a


# ---------------- 对齐 ----------------

def bbox_of(alpha: np.ndarray, thr: int = 32):
    ys, xs = np.where(alpha > thr)
    if len(xs) == 0:
        return None
    return xs.min(), ys.min(), xs.max(), ys.max()


def place(rgba: np.ndarray, box, scale: float, dx: int, dy: int) -> np.ndarray:
    """把 rgba 的 box 区域按 scale 缩放后贴到 640×360 画布（脚底 FEET_Y、水平居中）。"""
    x0, y0, x1, y1 = box
    crop = Image.fromarray(rgba[y0:y1 + 1, x0:x1 + 1])
    w = max(1, int(round(crop.width * scale)))
    h = max(1, int(round(crop.height * scale)))
    crop = crop.resize((w, h), Image.LANCZOS)
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    canvas.alpha_composite(crop, (int(round(CANVAS_W / 2 - w / 2 + dx)), int(round(FEET_Y - h + dy))))
    return canvas


# ---------------- 视频进出 ----------------

def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit("命令失败: " + " ".join(cmd[:6]) + "\n" + (p.stderr or "")[-800:])


def prob_fps(path: str) -> float:
    p = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=r_frame_rate", "-of", "default=nw=1:nk=1", path],
                       capture_output=True, text=True)
    try:
        num, den = p.stdout.strip().split("/")
        return float(num) / float(den)
    except Exception:
        return 30.0


def extract_frames(video: str, workdir: str):
    run([FFMPEG, "-hide_banner", "-loglevel", "error", "-i", video,
         "-vsync", "0", os.path.join(workdir, "f_%05d.png")])
    names = sorted(n for n in os.listdir(workdir) if n.startswith("f_") and n.endswith(".png"))
    return [os.path.join(workdir, n) for n in names]


def encode_webm(frames_dir: str, out_path: str):
    run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(FPS),
         "-i", os.path.join(frames_dir, "a_%05d.png"),
         "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0",
         "-b:v", "0", "-crf", "32", "-row-mt", "1",
         "-metadata:s:v:0", "alpha_mode=1", out_path])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video")
    ap.add_argument("--image")
    ap.add_argument("--out-png")
    ap.add_argument("--name", default="")
    ap.add_argument("--out", help="宠物包动画目录（webm 直接落这里）")
    ap.add_argument("--mode", default="auto", choices=["auto", "chroma", "ai"])
    ap.add_argument("--model", default=os.path.join(os.path.dirname(__file__), "..", "models", "u2netp.onnx"))
    ap.add_argument("--keep-frames", action="store_true")
    a = ap.parse_args()

    u2net = None
    need_ai = a.mode == "ai"
    if need_ai or a.mode == "auto":
        if os.path.exists(a.model):
            try:
                u2net = U2Net(a.model)
            except Exception as e:
                if need_ai:
                    raise SystemExit("加载模型失败: %s" % e)
        elif need_ai:
            raise SystemExit("找不到模型: " + a.model)

    def pick_mode(rgb):
        if a.mode != "auto":
            return a.mode
        # auto：绿幕占比高就走 chroma，否则走 ai
        alpha = cutout_chroma(rgb)
        return "chroma" if (alpha < 32).mean() > 0.25 else ("ai" if u2net else "chroma")

    # 单图模式
    if a.image:
        rgb = np.asarray(Image.open(a.image).convert("RGB"))
        mode = pick_mode(rgb)
        alpha = cut_image(rgb, mode, u2net)
        rgba = np.dstack([_despill(rgb, alpha) if mode == "chroma" else rgb, alpha])
        Image.fromarray(rgba, "RGBA").save(a.out_png or "cut.png")
        print("单图完成：%s（mode=%s）" % (a.out_png or "cut.png", mode))
        return

    if not a.video or not a.out:
        raise SystemExit("要么 --image，要么 --video + --out")

    work = tempfile.mkdtemp(prefix="petanim_")
    frames = extract_frames(a.video, work)
    if not frames:
        raise SystemExit("没抽到帧")
    src_fps = prob_fps(a.video)
    print("帧数 %d，源 %0.1ffps" % (len(frames), src_fps))

    cut_dir = os.path.join(work, "cut")
    os.makedirs(cut_dir, exist_ok=True)
    boxes, prepared = [], []
    mode_used = None
    for i, f in enumerate(frames, 1):
        rgb = np.asarray(Image.open(f).convert("RGB"))
        mode = mode_used or pick_mode(rgb)
        mode_used = mode
        alpha = cut_image(rgb, mode, u2net)
        rgba = np.dstack([_despill(rgb, alpha) if mode == "chroma" else rgb, alpha])
        box = bbox_of(alpha)
        if box is None:
            continue
        boxes.append(box)
        prepared.append(rgba)
    print("抠像完成（mode=%s），有效帧 %d" % (mode_used, len(prepared)))

    # 全段共用一套变换：取各帧包围盒的并集，按角色高度缩放到 CHAR_H
    x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes); y1 = max(b[3] for b in boxes)
    union_h = max(1, y1 - y0 + 1)
    scale = CHAR_H / union_h
    print("包围盒并集 %dx%d → scale %.3f" % (x1 - x0 + 1, union_h, scale))

    for i, rgba in enumerate(prepared, 1):
        canvas = place(rgba, (x0, y0, x1, y1), scale, 0, 0)
        canvas.save(os.path.join(cut_dir, "a_%05d.png" % i))

    os.makedirs(a.out, exist_ok=True)
    out_video = os.path.join(a.out, (a.name or os.path.splitext(os.path.basename(a.video))[0]) + ".webm")
    encode_webm(cut_dir, out_video)
    size = os.path.getsize(out_video)
    print("完成：%s（%.0f KB，640×360 VP9-alpha）" % (out_video, size / 1024))
    if not a.keep_frames:
        shutil.rmtree(work, ignore_errors=True)
    else:
        print("中间帧在：" + work)


if __name__ == "__main__":
    main()
