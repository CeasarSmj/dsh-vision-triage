#!/usr/bin/env python
"""parser/ocr 数据防御逻辑单测：异常 bbox/元素结构不再导致崩溃（回归护栏）。

用法：python tests/test_robustness.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dsh_visit.ui_parse.parser import _normalize_bbox  # noqa: E402
from dsh_visit.ocr.ocr import _normalize_ocr_line  # noqa: E402


def main() -> int:
    failures = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal failures
        print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail}")
        if not cond:
            failures += 1

    print("== _normalize_bbox ==")
    # 正常四元组（ratio → 像素）
    check("正常四元组", _normalize_bbox([0.1, 0.2, 0.5, 0.8], 1000, 500) == [100, 100, 500, 400])
    check("tuple 输入", _normalize_bbox((0.1, 0.2, 0.5, 0.8), 1000, 500) == [100, 100, 500, 400])
    try:
        import numpy as np
        check("numpy 输入", _normalize_bbox(np.array([0.1, 0.2, 0.5, 0.8]), 1000, 500) == [100, 100, 500, 400])
    except ImportError:
        print("  [SKIP] numpy 未装")
    # 缺失兜底
    check("None → [0,0,0,0]", _normalize_bbox(None, 1000, 500) == [0, 0, 0, 0])
    check("空列表 → [0,0,0,0]", _normalize_bbox([], 1000, 500) == [0, 0, 0, 0])
    # 结构异常 → None（跳过，不崩溃——本轮修复的核心）
    check("dict 输入 → None", _normalize_bbox({"x1": 0.1}, 1000, 500) is None)
    check("str 输入 → None", _normalize_bbox("0.1,0.2,0.5,0.8", 1000, 500) is None)
    check("长度≠4 → None", _normalize_bbox([0.1, 0.2], 1000, 500) is None)
    check("长度>4 → None", _normalize_bbox([0.1, 0.2, 0.3, 0.4, 0.5], 1000, 500) is None)
    check("非数值 → None", _normalize_bbox(["a", "b", "c", "d"], 1000, 500) is None)
    check("NaN → None", _normalize_bbox([0.1, float("nan"), 0.5, 0.8], 1000, 500) is None)
    check("int 输入 → None", _normalize_bbox(42, 1000, 500) is None)

    print("== _normalize_ocr_line ==")
    box4 = [[0, 0], [10, 0], [10, 20], [0, 20]]
    check("正常行", _normalize_ocr_line([box4, "hello", 0.9]) ==
          {"text": "hello", "confidence": 0.9, "bbox": [0, 0, 10, 20]})
    check("box 为空 → None", _normalize_ocr_line([[], "hello", 0.9]) is None)
    check("item 长度不足 → None", _normalize_ocr_line([box4, "hello"]) is None)
    check("box 点数不足 → None", _normalize_ocr_line([[[0, 0]], "hello", 0.9]) is None)
    check("box 为 dict → None", _normalize_ocr_line([{"a": 1}, "hello", 0.9]) is None)
    check("score 非数值 → None", _normalize_ocr_line([box4, "hello", "high"]) is None)

    print("== parse_ui_screenshot 集成（mock 异常 parsed_content_list）==")
    from dsh_visit import ui_parse as up

    TEST_IMG = Path(__file__).resolve().parent / ".smoke-tmp" / "ui_screenshot.png"

    def fake_get_som(*a, **k):
        # 返回含异常结构的元素（dict bbox / str bbox / 裸字符串 / 正常元素）
        parsed = [
            {"type": "text", "bbox": [0.1, 0.1, 0.5, 0.3], "content": "正常文本"},
            {"type": "icon", "bbox": {"x1": 0.1, "y1": 0.2}, "content": "dict bbox"},  # ← 用户报告的场景
            {"type": "icon", "bbox": "oops", "content": "str bbox"},
            "裸字符串元素",
            {"type": "icon", "bbox": [0.6, 0.6, 0.8, 0.8], "content": "正常图标"},
        ]
        return (None, None, parsed)

    def fake_check_ocr_box(*a, **k):
        return ([], []), None

    orig = up.parser._load_engine
    up.parser._load_engine = lambda: (fake_get_som, fake_check_ocr_box, None, None)
    try:
        r = up.parse_ui_screenshot(str(TEST_IMG))
        check("status=ok（不崩溃）", r.get("status") == "ok", str(r.get("message")))
        check("异常元素被跳过（5 个输入 → 2 个正常元素）", r.get("element_count") == 2, f"count={r.get('element_count')}")
        check("跳过数上报", "跳过 3" in (r.get("message") or ""), r.get("message"))
        texts = [e["text"] for e in r.get("elements", []) if e["type"] == "text"]
        check("正常文本保留", texts == ["正常文本"], str(texts))
        check("正常图标保留", any(e["type"] == "icon" and e["description"] == "正常图标" for e in r.get("elements", [])),
              str(r.get("elements")))
    finally:
        up.parser._load_engine = orig

    print(f"\n结果: {'全部通过' if failures == 0 else f'{failures} 项失败'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
