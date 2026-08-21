#!/usr/bin/env python
"""对 Downloads 目录下所有图片做 L1/L2 分类并生成报告。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dsh_visit.classify import classify_l1, classify_l2

DL = Path(r"C:\Users\Administrator\Downloads")
EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

ROUTE = {
    ("content", None): "内容承载 → 目标检测 / 语义追问（detect_natural_image / describe_image）",
    ("structure", "ui"): "结构承载-UI → OmniParser 解析（parse_ui_screenshot）",
    ("structure", "text"): "结构承载-文本 → OCR（ocr_image）",
    ("structure", "form"): "结构承载-表单 → OCR+表格（ocr_image --with-table）",
}


def main() -> None:
    imgs = sorted(p for p in DL.iterdir() if p.is_file() and p.suffix.lower() in EXTS)
    if not imgs:
        print("Downloads 下没有图片")
        return

    results = []
    for img in imgs:
        r1 = classify_l1(img)
        row = {
            "file": img.name,
            "size_kb": img.stat().st_size // 1024,
            "l1": r1["category"],
            "l1_conf": r1["confidence"],
        }
        if r1["category"] == "structure":
            r2 = classify_l2(img)
            row["l2"] = r2["category"]
            row["l2_conf"] = r2["confidence"]
            row["route"] = ROUTE[("structure", r2["category"])]
        else:
            row["l2"] = ""
            row["l2_conf"] = ""
            row["route"] = ROUTE[("content", None)]
        results.append(row)

    # 汇总统计
    from collections import Counter
    l1_stat = Counter(r["l1"] for r in results)
    l2_stat = Counter((r["l2"] or "") for r in results if r["l2"])

    lines = []
    lines.append("# Downloads 图片分类报告")
    lines.append("")
    lines.append(f"- 时间：{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"- 图片总数：{len(results)}")
    lines.append(f"- L1：content {l1_stat.get('content', 0)} / structure {l1_stat.get('structure', 0)}")
    lines.append(f"- L2（structure 细分）：ui {l2_stat.get('ui', 0)} / text {l2_stat.get('text', 0)} / form {l2_stat.get('form', 0)}")
    lines.append("")
    lines.append("| 预览 | 文件 | 大小 | L1 | 置信度 | L2 | 置信度 | 推荐路由 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in results:
        # 图片与报告同目录，用相对路径嵌入；文件名含空格/括号时用 <...> 包裹链接目标
        # （CommonMark 标准，VSCode/Typora 均支持），避免 ) 提前闭合链接
        lines.append(
            f"| ![{r['file']}](<{r['file']}>) | `{r['file']}` | {r['size_kb']}KB | {r['l1']} | {r['l1_conf']:.2f} | "
            f"{r['l2'] or '—'} | {r['l2_conf'] if r['l2'] else '—'} | {r['route']} |"
        )
    report = "\n".join(lines)
    print(report)

    out = DL / "图片分类报告.md"
    out.write_text(report, encoding="utf-8")
    print(f"\n报告已保存: {out}")


if __name__ == "__main__":
    main()
