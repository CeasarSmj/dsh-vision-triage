"""M2 数据准备：从网络真实数据构建 YOLO 分类数据集（ADR-3）。

输入目录约定（用户手工收集的原始图片，全部为网络真实数据）：
  <data>/raw/l1/content/*.{jpg,png,...}     照片/CG/插画/画作
  <data>/raw/l1/structure/*.{jpg,png,...}   纯文本/表单/UI/网页/文档
  <data>/raw/l2/ui/*.…                      软件界面/网页截图
  <data>/raw/l2/text/*.…                    纯文本/文档页截图
  <data>/raw/l2/form/*.…                    表单/表格截图

输出（YOLO classify 标准布局，train/val 各含类别子目录）：
  <data>/yolo/l1/train/{content,structure}/...
  <data>/yolo/l1/val/{content,structure}/...
  <data>/yolo/l2/train/{ui,text,form}/...
  <data>/yolo/l2/val/{ui,text,form}/...

划分：目标每类 1000 张（train 800 + val 200）；不足时按 80/20 比例划分并告警。
"""

import argparse
import random
import shutil
from pathlib import Path

from .._paths import DATA_DIR

SPLIT_RATIO = 0.8  # train / (train+val)

L1_CLASSES = ["content", "structure"]
L2_CLASSES = ["ui", "text", "form"]


def build_split(src_root: Path, dst_root: Path, classes: list[str], seed: int = 42) -> dict:
    """把一个 stage（l1/l2）的 raw 目录划分到 yolo 布局，返回统计。"""
    rng = random.Random(seed)
    stats = {}
    for cls in classes:
        src_dir = src_root / cls
        if not src_dir.exists():
            print(f"  [跳过] 缺少类别目录: {src_dir}")
            stats[cls] = (0, 0)
            continue
        images = sorted(
            p for p in src_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
        )
        rng.shuffle(images)
        n_train = int(len(images) * SPLIT_RATIO)
        if len(images) < 100:
            print(f"  [警告] {cls} 仅 {len(images)} 张（目标 1000），划分后训练集偏小")
        for split, subset in (("train", images[:n_train]), ("val", images[n_train:])):
            out_dir = dst_root / split / cls
            out_dir.mkdir(parents=True, exist_ok=True)
            for src in subset:
                shutil.copy2(src, out_dir / src.name)
        stats[cls] = (n_train, len(images) - n_train)
    return stats


def write_yaml(name: str, data_dir: Path, classes: list[str]) -> Path:
    yaml_path = data_dir / f"{name}.yaml"
    names = ", ".join(f"{i}: {c}" for i, c in enumerate(classes))
    yaml_path.write_text(
        f"# 由 train/data.py 生成（{name}）\n"
        f"path: {data_dir.as_posix()}\n"
        f"train: {name}/train\n"
        f"val: {name}/val\n"
        f"names:\n  {names}\n",
        encoding="utf-8",
    )
    return yaml_path


def main() -> None:
    parser = argparse.ArgumentParser(description="构建 L1/L2 YOLO 分类数据集")
    parser.add_argument("--data-dir", default=str(DATA_DIR), help="数据集根目录")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    raw_dir = data_dir / "raw"

    for stage, classes in (("l1", L1_CLASSES), ("l2", L2_CLASSES)):
        print(f"== 构建 {stage} ==")
        stats = build_split(raw_dir / stage, data_dir / "yolo" / stage, classes, args.seed)
        for cls, (n_tr, n_va) in stats.items():
            print(f"  {cls}: train {n_tr} / val {n_va}")
        yaml_path = write_yaml(stage, data_dir / "yolo", classes)
        print(f"  数据配置: {yaml_path}")


if __name__ == "__main__":
    main()
