#!/usr/bin/env python
"""生成一张带边框的表格测试图（中文 + 英文数据），用于验证 ocr_image --with-table。"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / ".smoke-tmp" / "table_test.png"


def font(size: int):
    for path in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\simhei.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT
    out.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (760, 320), "white")
    d = ImageDraw.Draw(img)
    f = font(18)

    # 表头 + 数据（3 列 x 4 行）
    table = [
        ["姓名", "年龄", "城市"],
        ["张三", "28", "北京"],
        ["李四", "35", "上海"],
        ["王五", "42", "深圳"],
    ]
    col_w = [140, 120, 160]
    x0, y0, row_h = 40, 40, 60
    cell_h = 52

    for r, row in enumerate(table):
        y = y0 + r * cell_h
        x = x0
        for c, cell in enumerate(row):
            d.rectangle([x, y, x + col_w[c], y + cell_h], outline=(0, 0, 0), width=2)
            d.text((x + 12, y + 12), cell, font=f, fill=(0, 0, 0))
            x += col_w[c]

    img.save(out)
    print(f"表格测试图已生成: {out}（{img.size[0]}x{img.size[1]}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
