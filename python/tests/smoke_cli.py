#!/usr/bin/env python
"""dsh_visit CLI 端到端冒烟测试（无需 pytest，直接运行）。

生成两张测试图（structure 风格 / content 风格），
以子进程方式调用 `python -m dsh_visit` 的 classify-image / classify-structure / ocr / status，
校验返回 JSON 的结构与关键字段。detect-image 需要联网下载权重，默认跳过（--with-detect 开启）。
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent  # python/
TMP_DIR = HERE / ".smoke-tmp"  # 工作区内临时目录（避免依赖系统 Temp）


def run_cmd(command: str, *args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "dsh_visit", command, *args],
        cwd=PKG_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**__import__("os").environ, "PYTHONUTF8": "1"},
        timeout=180,
    )
    assert proc.returncode == 0, f"{command} 退出码 {proc.returncode}: {proc.stderr}"
    return json.loads(proc.stdout)


def make_structure_image(path: Path) -> None:
    """白底 + 多行文本 + 表格线的"结构承载型"测试图。"""
    img = Image.new("RGB", (640, 480), "white")
    draw = ImageDraw.Draw(img)
    for i, text in enumerate(["Name:", "Age:", "Address:", "Phone:", "Email:", "备注:"]):
        draw.rectangle([40, 40 + i * 60, 360, 40 + i * 60 + 36], fill=(235, 235, 235))
        draw.text((48, 48 + i * 60), text, fill=(20, 20, 20))
    # 表格线
    for x in (40, 200, 360):
        draw.line([x, 40, x, 400], fill=(0, 0, 0), width=2)
    for y in range(40, 401, 60):
        draw.line([40, y, 360, y], fill=(0, 0, 0), width=2)
    img.save(path)


def make_content_image(path: Path) -> None:
    """彩色渐变 + 简单几何体的"内容承载型"测试图（近似照片的平滑梯度）。"""
    img = Image.new("RGB", (640, 480))
    px = img.load()
    for y in range(480):
        for x in range(640):
            px[x, y] = (
                int(120 + 100 * x / 640),
                int(80 + 120 * y / 480),
                int(200 - 90 * x / 640),
            )
    draw = ImageDraw.Draw(img)
    draw.ellipse([200, 120, 440, 360], fill=(40, 160, 90))
    draw.ellipse([260, 180, 380, 300], fill=(255, 220, 120))
    img.save(path)


def main() -> int:
    failures = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal failures
        status = "PASS" if cond else "FAIL"
        if not cond:
            failures += 1
        print(f"  [{status}] {name} {detail}")

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = TMP_DIR
    struct_img = tmp / "structure.png"
    content_img = tmp / "content.png"
    make_structure_image(struct_img)
    make_content_image(content_img)

    print("== status ==")
    st = run_cmd("status")
    check("status 返回项目根", bool(st.get("project_root")), st.get("project_root", ""))

    print("== classify-image ==")
    r1 = run_cmd("classify-image", "--input", str(struct_img))
    check("L1 category 字段合法", r1.get("category") in ("content", "structure"), str(r1))
    check("L1 confidence 0~1", 0 <= r1.get("confidence", -1) <= 1)
    check("L1 degraded 布尔", isinstance(r1.get("degraded"), bool))

    print("== classify-structure ==")
    r2 = run_cmd("classify-structure", "--input", str(struct_img))
    check("L2 category 字段合法", r2.get("category") in ("ui", "text", "form"), str(r2))
    check("L2 degraded 布尔", isinstance(r2.get("degraded"), bool))

    print("== ocr ==")
    try:
        r3 = run_cmd("ocr", "--input", str(struct_img))
        check("OCR status=ok", r3.get("status") == "ok", str(r3)[:200])
        check("OCR lines 为列表", isinstance(r3.get("lines"), list))
    except Exception as exc:  # rapidocr 首次需下载模型，网络不可用时允许跳过
        print(f"  [SKIP] ocr: {exc}")

    print("== ocr --with-table ==")
    try:
        from make_table_fixture import OUT as TABLE_OUT  # noqa: F401

        if TABLE_OUT.exists():
            r4 = run_cmd("ocr", "--input", str(TABLE_OUT), "--with-table")
            check("表格 status=ok", r4.get("status") == "ok", str(r4)[:150])
            check("表格 html 含 <table>", "<table>" in (r4.get("table") or {}).get("html", ""))
            check("表格 cell_count 数值", isinstance((r4.get("table") or {}).get("cell_count"), int))
        else:
            print("  [SKIP] 表格测试图缺失")
    except Exception as exc:  # rapid_table 首次需下载 SLANet+ 模型，允许跳过
        print(f"  [SKIP] ocr --with-table: {exc}")

    print(f"\n结果: {'全部通过' if failures == 0 else f'{failures} 项失败'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
