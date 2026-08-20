#!/usr/bin/env python
"""生成"软件 UI 截图"风格的测试图（中文文本 + 控件 + 表格 + 内嵌图片），
用于确定性验证 parse_ui_screenshot（OmniParser）全链路。

用法:
  python make_ui_fixture.py [--dark] [输出路径]
    --dark  生成深色主题版（深底浅字，用于验证 parser 的自动反色预处理）
默认输出 ./.smoke-tmp/ui_screenshot.png（--dark 时 ui_screenshot_dark.png）
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / ".smoke-tmp" / "ui_screenshot.png"
OUT_DARK = HERE / ".smoke-tmp" / "ui_screenshot_dark.png"

W, H = 1024, 768

# 主题色板：light（默认）/ dark（深色 UI 常见配色）
THEMES = {
    "light": dict(
        bg=(244, 246, 248), panel=(255, 255, 255), border=(210, 214, 220),
        accent=(52, 120, 246), text=(30, 32, 36), gray=(110, 116, 124),
        nav=(232, 236, 240), nav_active=(52, 120, 246),
        field=(250, 251, 252), head=(236, 240, 246),
        titlebar=(40, 44, 52), titlebar_btn=(60, 64, 72), titlebar_text=(255, 255, 255),
    ),
    "dark": dict(
        bg=(32, 34, 40), panel=(44, 47, 56), border=(70, 74, 86),
        accent=(86, 156, 246), text=(230, 232, 238), gray=(158, 162, 172),
        nav=(26, 28, 33), nav_active=(86, 156, 246),
        field=(58, 62, 72), head=(52, 56, 66),
        titlebar=(24, 26, 30), titlebar_btn=(50, 54, 62), titlebar_text=(235, 238, 244),
    ),
}


def font(size: int):
    for path in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\simhei.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def main() -> int:
    dark = "--dark" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = Path(args[0]) if args else (OUT_DARK if dark else OUT)
    out.parent.mkdir(parents=True, exist_ok=True)
    C = THEMES["dark" if dark else "light"]

    img = Image.new("RGB", (W, H), C["bg"])
    d = ImageDraw.Draw(img)
    f_title = font(22)
    f_label = font(16)
    f_small = font(14)

    # 标题栏
    d.rectangle([0, 0, W, 56], fill=C["titlebar"])
    d.text((20, 14), "设置 - Settings", font=f_title, fill=C["titlebar_text"])
    d.rectangle([W - 90, 0, W - 60, 56], fill=C["titlebar_btn"])  # 窗口按钮占位

    # 左侧导航
    d.rectangle([0, 56, 180, H], fill=C["nav"])
    for i, item in enumerate(["个人资料", "账号安全", "通知设置", "关于我们"]):
        y = 90 + i * 56
        if i == 0:
            d.rectangle([0, y, 180, y + 44], fill=C["nav_active"])
        d.text((24, y + 10), item, font=f_label, fill=(255, 255, 255) if i == 0 else C["text"])

    # 右侧主面板：表单
    x0, y0 = 220, 100
    d.rectangle([x0, y0, 980, 640], fill=C["panel"], outline=C["border"], width=2)
    d.text((x0 + 24, y0 + 20), "基本信息", font=f_title, fill=C["text"])

    labels = ["用户名:", "邮箱:", "手机号:"]
    for i, lab in enumerate(labels):
        ly = y0 + 80 + i * 70
        d.text((x0 + 24, ly + 4), lab, font=f_label, fill=C["gray"])
        d.rectangle([x0 + 140, ly, x0 + 460, ly + 40], fill=C["field"], outline=C["border"], width=2)

    # 按钮
    d.rectangle([x0 + 24, y0 + 330, x0 + 140, y0 + 374], fill=C["accent"])
    d.text((x0 + 48, y0 + 340), "保存", font=f_label, fill=(255, 255, 255))
    d.rectangle([x0 + 156, y0 + 330, x0 + 272, y0 + 374], fill=C["panel"], outline=C["border"], width=2)
    d.text((x0 + 196, y0 + 340), "取消", font=f_label, fill=C["text"])

    # 表格
    tx, ty = x0 + 24, y0 + 410
    cols = ["项目", "状态", "备注"]
    for ci, cname in enumerate(cols):
        d.rectangle([tx + ci * 150, ty, tx + (ci + 1) * 150, ty + 36], fill=C["head"])
        d.text((tx + ci * 150 + 10, ty + 8), cname, font=f_small, fill=C["text"])
    rows = [["本地模型", "运行中", "YOLO/OCR"], ["云端模型", "待配置", "QwenVL"], ["缓存", "正常", "128MB"]]
    for ri, row in enumerate(rows):
        ry = ty + 36 + ri * 36
        d.line([tx, ry, tx + 450, ry], fill=C["border"], width=1)
        for ci, cell in enumerate(row):
            d.text((tx + ci * 150 + 10, ry + 9), cell, font=f_small, fill=C["text"])
    d.line([tx, ty + 36 * 4, tx + 450, ty + 36 * 4], fill=C["border"], width=1)

    # 内嵌图片（Florence-2 应对其生成语义描述；主题无关，保持彩色）
    ex, ey = x0 + 520, y0 + 80
    for yy in range(240):
        for xx in range(220):
            r = int(140 + 80 * xx / 220)
            g = int(90 + 100 * yy / 240)
            b = int(200 - 100 * xx / 220)
            img.putpixel((ex + xx, ey + yy), (r, g, b))
    dd = ImageDraw.Draw(img)
    dd.ellipse([ex + 40, ey + 40, ex + 180, ey + 200], fill=(40, 160, 90))
    dd.text((ex + 60, ey + 220), "内嵌图片区域", font=f_small, fill=C["gray"])

    img.save(out)
    print(f"UI {'深色' if dark else '浅色'}测试图已生成: {out}（{W}x{H}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
