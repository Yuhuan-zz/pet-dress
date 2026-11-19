#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成一个「宠物种类包」的骨架：pet/<名>-config.json + pet/<名>-animation/。

规则（照抄上游 MAKE-YOUR-OWN-PET.md / CONFIG.md）：
  - 前缀 = 文件名词干 = 素材根；素材只查自己目录，查不到就 404（不回落主素材）
  - 必须有的段：idle / turn / drag / clicks / moves / categories / events（含 balance）
  - 槽位可以复用同一段动作：先用一个"占位动作"把所有槽位填满，再逐段替换
  - animations.sleep 可选，不写就没有「睡觉」菜单

用法：
  python make_pack.py --name bubble-rain --action 待机呼吸 --display desktop
"""
import argparse
import json
import os

REQUIRED_EVENTS = ("balance", "whisper", "workStatus", "notify")


def build(name: str, action: str, display: str, size: int, pet_name: str):
    slot = [action]
    events = {k: [slot] for k in REQUIRED_EVENTS}
    return {
        "_comment": [
            "由 pet-dress/tools/make_pack.py 生成。槽位先全部指向同一个占位动作，",
            "做好新动作后把文件名替换进来即可（名字 = <名>-animation/ 里的 webm 文件名）。",
        ],
        "pets": [
            {
                "id": f"{name}-main",
                "name": pet_name,
                "size": size,
                "balanceEnabled": True,
                "whisperEnabled": True,
                "workStatusEnabled": True,
                "fixedEnabled": False,
                "display": display,
                "position": {"corner": "top-right", "marginX": 24, "marginY": 100},
            }
        ],
        "animations": {
            "idle": slot,
            "turn": slot,
            "drag": slot,
            "clicks": slot,
            "moves": {
                "default": {"minDist": 60, "maxDist": 240, "margin": 20, "leadSec": 2, "tailSec": 2},
                "actions": [{"name": action}],
            },
            "categories": [{"id": "小动作", "weight": 20, "actions": slot}],
            "events": events,
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="种类名（= 文件名前缀 = 素材根）")
    ap.add_argument("--action", required=True, help="占位动作名（先全槽位指向它）")
    ap.add_argument("--pet-name", default="泡泡")
    ap.add_argument("--display", default="desktop", choices=["web", "desktop", "both", "none"])
    ap.add_argument("--size", type=int, default=400)
    ap.add_argument("--home", default=os.path.join(os.path.expanduser("~"), ".dsh", "dsh-pet"))
    a = ap.parse_args()

    pet_dir = os.path.join(a.home, "pet")
    anim_dir = os.path.join(pet_dir, a.name + "-animation")
    cfg_path = os.path.join(pet_dir, a.name + "-config.json")
    os.makedirs(anim_dir, exist_ok=True)

    if os.path.exists(cfg_path):
        raise SystemExit("配置已存在，先看一眼再决定要不要覆盖：" + cfg_path)
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(build(a.name, a.action, a.display, a.size, a.pet_name), f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("配置：", cfg_path)
    print("素材目录：", anim_dir, "（把 webm 放这里，文件名 = 动作名）")
    print("下一步：把「%s.webm」放进素材目录，再完全重启 DSH。" % a.action)


if __name__ == "__main__":
    main()
