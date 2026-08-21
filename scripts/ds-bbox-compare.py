#!/usr/bin/env python
"""对比 DeepSeek-V4-Flash-Vision 报出的 bbox 百分比坐标 vs OmniParser 真实值，并画图。

流程：
1. 用 OmniParser 解析截图，得到目标元素的真实 bbox（ground truth）
2. 对每个元素，让 DeepSeek 输出 bbox 百分比坐标（x1%,y1%,x2%,y2%）
3. 用 PIL 在图上画出真实框(绿)与预测框(红)，保存对比图
"""

import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

IMG = r"C:\Users\Administrator\Pictures\Screenshots\屏幕截图 2026-08-21 175349.png"
OUT = r"C:\Users\Administrator\Downloads\DS定位对比图.png"
DSH_HOME = Path(r"C:\Users\Administrator\.dsh")
PLUGIN_ROOT = Path(r"D:\temple\dsh-vision-triage")

# 选中元素：名称 + 在 OmniParser 结果中的匹配文本（选大区域元素，VLM 更易定位）
TARGETS = [
    {"name": "选择车辆(顶部标题)", "match": "选择车辆"},
    {"name": "新越(车辆卡片)", "match": "新越"},
    {"name": "雷加利亚(车辆卡片)", "match": "雷加利亚"},
    {"name": "开始比赛(大按钮)", "match": "开始比赛"},
]

# 从 .credentials.yaml 读 DEEPSEEK_API_KEY（与 smoke-describe.mjs 同源）
cred_raw = (DSH_HOME / ".credentials.yaml").read_text(encoding="utf-8")
m = re.search(r"^DEEPSEEK_API_KEY:\s*(\S+)", cred_raw, re.M)
if not m:
    print("未找到 DEEPSEEK_API_KEY")
    sys.exit(1)
DS_KEY = m.group(1)


def ds_describe(prompt: str, img_path: str) -> str:
    """直接调 DeepSeek chat/completions；reasoning 模型偶发 content 为空，最多重试 3 次。"""
    import base64
    import urllib.request

    data_url = "data:image/png;base64," + base64.b64encode(Path(img_path).read_bytes()).decode()
    for attempt in range(3):
        body = json.dumps({
            "model": "deepseek-v4-flash-vision-exp",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt + ("（请直接给出数字答案，不要思考过程）" if attempt else "")},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]}],
            "max_tokens": 1000,
        }).encode()
        req = urllib.request.Request(
            "https://api.deepseek.com/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {DS_KEY}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            j = json.loads(resp.read())
        msg = j["choices"][0]["message"]
        content = (msg.get("content") or "").strip()
        print(f"    [debug] attempt{attempt + 1} content={content!r} reasoning_len={len(msg.get('reasoning_content') or '')}")
        if content:
            return content
    return ""


def parse_coords(text: str):
    """从 VLM 输出中提取 4 个百分比数字。"""
    nums = re.findall(r"(\d+(?:\.\d+)?)\s*%?", text)
    if len(nums) >= 4:
        try:
            return [float(n) for n in nums[:4]]
        except ValueError:
            return None
    return None


def main():
    sys.path.insert(0, str(PLUGIN_ROOT / "python"))
    from dsh_visit.ui_parse import parse_ui_screenshot

    im = Image.open(IMG)
    W, H = im.size
    print(f"图片: {W}x{H}")

    parsed = parse_ui_screenshot(IMG)
    # 收集真实 bbox
    gt = {}  # name -> [x1,y1,x2,y2] 像素
    for e in parsed["elements"]:
        text = (e.get("text") or "") + (e.get("description") or "")
        for t in TARGETS:
            if t["name"] not in gt and t["match"] in text:
                gt[t["name"]] = list(e["bbox"])
    print("OmniParser ground truth:", {k: v for k, v in gt.items()})

    draw = ImageDraw.Draw(im)
    fnt = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 22)
    results = []

    for t in TARGETS:
        name = t["name"]
        real = gt.get(name)
        if not real:
            print(f"[跳过] OmniParser 未找到: {name}")
            continue
        rx1, ry1, rx2, ry2 = real
        rpct = [rx1 / W * 100, ry1 / H * 100, rx2 / W * 100, ry2 / H * 100]

        prompt = (
            f"这张图片（{W}x{H} 像素）里有一个元素，文字是「{t['match']}」。"
            f"请给出这个元素边界框（bounding box）的百分比坐标，格式：x1%, y1%, x2%, y2%，"
            f"其中 (x1,y1) 是左上角、(x2,y2) 是右下角，均以图片宽高为 100%。"
            f"只输出 4 个数字，不要解释。"
        )
        reply = ds_describe(prompt, IMG)
        pred = parse_coords(reply)
        print(f"\n[{name}] DS 回复: {reply!r} -> 解析: {pred}")

        # 画真实框（绿）
        draw.rectangle(real, outline=(0, 200, 0), width=4)
        draw.text((rx1, max(0, ry1 - 26)), f"真实 {name}", font=fnt, fill=(0, 200, 0))
        # 画预测框（红，可解析时）
        if pred:
            px1, py1, px2, py2 = [p / 100 * (W if i % 2 == 0 else H) for i, p in enumerate(pred)]
            draw.rectangle([px1, py1, px2, py2], outline=(255, 60, 60), width=4)
            draw.text((px1, min(H - 28, py2 + 2)), f"DS预测 {name}", font=fnt, fill=(255, 60, 60))
            err = max(abs(pred[0] - rpct[0]), abs(pred[1] - rpct[1]), abs(pred[2] - rpct[2]), abs(pred[3] - rpct[3]))
            results.append({"name": name, "real": [round(v, 2) for v in rpct], "pred": [round(v, 2) for v in pred], "max_err_pp": round(err, 2)})
        else:
            results.append({"name": name, "real": [round(v, 2) for v in rpct], "pred": None, "max_err_pp": None})

    im.save(OUT)
    print(f"\n对比图已保存: {OUT}")

    print("\n=== 对比表 ===")
    print(f"{'元素':<16} {'真实 x1y1x2y2%':<28} {'DS 预测 x1y1x2y2%':<28} {'最大偏差pp':<10}")
    for r in results:
        rr = " ".join(f"{v}" for v in r["real"])
        pp = " ".join(f"{v}" for v in r["pred"]) if r["pred"] else "无法解析"
        err = str(r["max_err_pp"]) if r["max_err_pp"] is not None else "-"
        print(f"{r['name']:<16} {rr:<28} {pp:<28} {err:<10}")


if __name__ == "__main__":
    main()
