#!/usr/bin/env python
"""对比：深色 UI 截图在"不反色"与"自动反色"两种策略下的 OmniParser 解析效果。

用法：python tests/compare_dark_invert.py
输出：两种策略的元素数 / 文本数 / 文本内容对比，量化反色提升。
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dsh_visit import ui_parse
from dsh_visit.ui_parse import parser

DARK_IMG = Path(__file__).resolve().parent / ".smoke-tmp" / "ui_screenshot_dark.png"


def run(threshold: int, label: str) -> dict:
    parser.DARK_THRESHOLD = threshold  # 128=自动反色；-1=强制不反色（旧行为基线）
    t0 = time.time()
    r = ui_parse.parse_ui_screenshot(str(DARK_IMG))
    print(f"\n=== {label}（耗时 {(time.time()-t0):.1f}s）===")
    print(f"status={r['status']} 元素={r['element_count']} 文本数={len(r['texts'])} inverted={r.get('inverted')}")
    print(f"message: {r.get('message')!r}")
    print("文本:", " / ".join(r["texts"][:20]))
    return r


def main() -> int:
    assert DARK_IMG.exists(), f"深色测试图缺失: {DARK_IMG}"
    base = run(-1, "不反色（旧行为基线）")
    inverted = run(128, "自动反色（新行为）")

    print("\n=== 对比 ===")
    print(f"元素数: {base['element_count']} → {inverted['element_count']}")
    print(f"文本数: {len(base['texts'])} → {len(inverted['texts'])}")

    # 关键文本正确性（深色图里应识别出的基准文本）
    expected = {"基本信息", "用户名:", "邮箱:", "手机号:", "保存", "取消", "项目", "状态", "备注",
                "本地模型", "运行中", "云端模型", "待配置", "缓存", "正常"}
    hit = lambda texts: len(expected & set(texts))
    print(f"基准文本命中: {hit(base['texts'])}/{len(expected)} → {hit(inverted['texts'])}/{len(expected)}")

    improved = inverted["element_count"] >= base["element_count"] and hit(inverted["texts"]) >= hit(base["texts"])
    print(f"\n结论: {'反色生效且解析不劣化 ✅' if improved else '反色未见改善，需检查 ⚠️'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
