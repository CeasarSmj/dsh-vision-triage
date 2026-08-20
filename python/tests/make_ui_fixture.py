#!/usr/bin/env python
"""生成一张"软件 UI 截图"风格的测试图（中文文本 + 控件 + 表格 + 内嵌图片），
用于确定性验证 parse_ui_screenshot（OmniParser）全链路。

用法: python make_ui_fixture.py [输出路径]（默认 ./.smoke-tmp/ui_screenshot.png）
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / ".smoke-tmp" / "ui_screenshot.png"

W, H = 1024, 768
BG = (244, 246, 248)
PANEL = (255, 255, 255)
BORDER = (210, 214, 220)
ACCENT = (52, 120, 246)
TEXT = (30, 32, 36)
GRAY = (110, 116, 124)


def font(size: int):
    for path in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\simhei.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT
    out.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f_title = font(22)
    f_label = font(16)
    f_small = font(14)

    # 标题栏
    d.rectangle([0, 0, W, 56], fill=(40, 44, 52))
    d.text((20, 14), "设置 - Settings", font=f_title, fill=(255, 255, 255))
    d.rectangle([W - 90, 0, W - 60, 56], fill=(60, 64, 72))  # 窗口按钮占位

    # 左侧导航
    d.rectangle([0, 56, 180, H], fill=(232, 236, 240))
    for i, item in enumerate(["个人资料", "账号安全", "通知设置", "关于我们"]):
        y = 90 + i * 56
        if i == 0:
            d.rectangle([0, y, 180, y + 44], fill=(52, 120, 246))
        d.text((24, y + 10), item, font=f_label, fill=(30, 32, 36) if i else (255, 255, 255))

    # 右侧主面板：表单
    x0, y0 = 220, 100
    d.rectangle([x0, y0, 980, 640], fill=PANEL, outline=BORDER, width=2)
    d.text((x0 + 24, y0 + 20), "基本信息", font=f_title, fill=TEXT)

    labels = ["用户名:", "邮箱:", "手机号:"]
    for i, lab in enumerate(labels):
        ly = y0 + 80 + i * 70
        d.text((x0 + 24, ly + 4), lab, font=f_label, fill=GRAY)
        d.rectangle([x0 + 140, ly, x0 + 460, ly + 40], fill=(250, 251, 252), outline=BORDER, width=2)

    # 按钮
    d.rectangle([x0 + 24, y0 + 330, x0 + 140, y0 + 374], fill=ACCENT)
    d.text((x0 + 48, y0 + 340), "保存", font=f_label, fill=(255, 255, 255))
    d.rectangle([x0 + 156, y0 + 330, x0 + 272, y0 + 374], fill=PANEL, outline=BORDER, width=2)
    d.text((x0 + 196, y0 + 340), "取消", font=f_label, fill=TEXT)

    # 表格
    tx, ty = x0 + 24, y0 + 410
    cols = ["项目", "状态", "备注"]
    for ci, cname in enumerate(cols):
        d.rectangle([tx + ci * 150, ty, tx + (ci + 1) * 150, ty + 36], fill=(236, 240, 246))
        d.text((tx + ci * 150 + 10, ty + 8), cname, font=f_small, fill=TEXT)
    rows = [["本地模型", "运行中", "YOLO/OCR"], ["云端模型", "待配置", "QwenVL"], ["缓存", "正常", "128MB"]]
    for ri, row in enumerate(rows):
        ry = ty + 36 + ri * 36
        d.line([tx, ry, tx + 450, ry], fill=BORDER, width=1)
        for ci, cell in enumerate(row):
            d.text((tx + ci * 150 + 10, ry + 9), cell, font=f_small, fill=TEXT)
    d.line([tx, ty + 36 * 4, tx + 450, ty + 36 * 4], fill=BORDER, width=1)

    # 内嵌图片（Florence-2 应对其生成语义描述）
    ex, ey = x0 + 520, y0 + 80
    for yy in range(240):
        for xx in range(220):
            r = int(140 + 80 * xx / 220)
            g = int(90 + 100 * yy / 240)
            b = int(200 - 100 * xx / 220)
            img.putpixel((ex + xx, ey + yy), (r, g, b))
    dd = ImageDraw.Draw(img)
    dd.ellipse([ex + 40, ey + 40, ex + 180, ey + 200], fill=(40, 160, 90))
    dd.text((ex + 60, ey + 220), "内嵌图片区域", font=f_small, fill=GRAY)

    img.save(out)
    print(f"UI 测试图已生成: {out}（{W}x{H}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
