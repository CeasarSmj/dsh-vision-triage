"""M2 收尾：把训练产物 best.pt 复制为推理权重（models/classify/l1.pt / l2.pt）。

用法：
  python -m dsh_visit.train.export
"""

import shutil
from pathlib import Path

from .._paths import L1_WEIGHTS, L2_WEIGHTS, MODELS_DIR


def export(stage: str) -> Path:
    best = MODELS_DIR / "runs" / stage / "weights" / "best.pt"
    if not best.exists():
        raise FileNotFoundError(f"训练产物缺失: {best}（先运行 train_l1/train_l2）")
    dst = L1_WEIGHTS if stage == "l1" else L2_WEIGHTS
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best, dst)
    print(f"已导出: {best} → {dst}")
    return dst


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="导出训练权重为推理权重")
    parser.add_argument("stage", choices=["l1", "l2"], help="导出哪个分类器")
    args = parser.parse_args()
    export(args.stage)


if __name__ == "__main__":
    main()
