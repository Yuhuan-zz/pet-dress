"""立绘（白底三视图之一）→ 16:9 纯绿幕首帧图。

只做一件事：把白底去掉、换成 #00FF00，角色居中、脚底留边，
尺寸按 --canvas 输出，供豆包/即梦做图生视频的首帧。
白底去法：只去掉「与图像边缘连通的白色」，角色内部的白毛边/白袜不受影响。

用法：
  python tools/make_firstframe.py --src raw/xmas.jpg --crop 20,20,450,714 --out test/xmas_firstframe.png
"""
import argparse
import sys

import numpy as np
from PIL import Image, ImageFilter


def remove_white_background(crop: Image.Image) -> Image.Image:
    arr = np.asarray(crop.convert("RGBA")).astype(np.int16)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    white = (r > 238) & (g > 238) & (b > 238) & ((mx - mn) < 16)

    seed = np.zeros_like(white)
    seed[0, :] = white[0, :]
    seed[-1, :] = white[-1, :]
    seed[:, 0] = white[:, 0]
    seed[:, -1] = white[:, -1]
    bg = seed.copy()
    for _ in range(800):
        prev = int(bg.sum())
        d = bg.copy()
        d[1:, :] |= bg[:-1, :]
        d[:-1, :] |= bg[1:, :]
        d[:, 1:] |= bg[:, :-1]
        d[:, :-1] |= bg[:, 1:]
        bg = d & white
        if int(bg.sum()) == prev:
            break

    alpha = np.where(bg, 0, 255).astype(np.uint8)
    am = Image.fromarray(alpha).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.6))
    alpha = np.asarray(am)

    # 只保留角色主体所在的连通域（去掉三视图里混进来的邻座碎片）
    mask = alpha > 0
    keep = np.zeros_like(mask)
    h, w = mask.shape
    sy, sx = h // 2, w // 2
    ys, xs = np.where(mask)
    if len(xs) == 0:
        raise SystemExit("抠完一张不剩，检查裁剪框是不是切到了角色")
    if not mask[sy, sx]:
        dist = (ys - sy) ** 2 + (xs - sx) ** 2
        sy, sx = int(ys[dist.argmin()]), int(xs[dist.argmin()])
    keep[sy, sx] = True
    for _ in range(3000):
        prev = int(keep.sum())
        d = keep.copy()
        d[1:, :] |= keep[:-1, :]
        d[:-1, :] |= keep[1:, :]
        d[:, 1:] |= keep[:, :-1]
        d[:, :-1] |= keep[:, 1:]
        keep = d & mask
        if int(keep.sum()) == prev:
            break
    alpha = np.where(keep, alpha, 0).astype(np.uint8)

    rgba = np.dstack([np.asarray(crop.convert("RGBA"))[..., :3], alpha])
    return Image.fromarray(rgba, "RGBA")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="立绘图片")
    ap.add_argument("--crop", required=True, help="裁剪框 x0,y0,x1,y1")
    ap.add_argument("--out", required=True, help="输出 PNG")
    ap.add_argument("--canvas", default="1920x1080", help="输出画布，默认 1920x1080")
    ap.add_argument("--role-h", type=int, default=880, help="角色高度（像素）")
    ap.add_argument("--bottom", type=int, default=1010, help="脚底位于画布的 y")
    a = ap.parse_args()

    x0, y0, x1, y1 = [int(v) for v in a.crop.split(",")]
    cw, ch = [int(v) for v in a.canvas.split("x")]
    im = Image.open(a.src)
    crop = im.crop((x0, y0, x1, y1))
    cut = remove_white_background(crop)

    bbox = cut.getbbox()
    if bbox is None:
        raise SystemExit("bbox 为空")
    bx0, by0, bx1, by1 = bbox
    scale = a.role_h / (by1 - by0)
    nw = max(1, int(round((bx1 - bx0) * scale)))
    nh = max(1, int(round((by1 - by0) * scale)))
    role = cut.crop(bbox).resize((nw, nh), Image.LANCZOS)

    canvas = Image.new("RGBA", (cw, ch), (0, 255, 0, 255))
    px = (cw - nw) // 2
    py = a.bottom - nh
    canvas.alpha_composite(role, (px, py))
    canvas.convert("RGB").save(a.out)
    print("完成：%s（角色 %dx%d，脚底 y=%d）" % (a.out, nw, nh, a.bottom))


if __name__ == "__main__":
    sys.exit(main())
