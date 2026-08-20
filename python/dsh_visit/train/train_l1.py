"""M2 训练：L1 分类器（content vs structure，yolo-classify）。

用法：
  python -m dsh_visit.train.train_l1 --data-dir <data> --epochs 100
先运行 train/data.py 生成 <data>/yolo/l1/{train,val}/<class>/ 目录
（ultralytics 分类数据集约定：data 参数传目录，类别名取自子目录）。
"""

import argparse
from pathlib import Path

from .._paths import DATA_DIR, MODELS_DIR


def train_l1(data_dir: Path, epochs: int, device: str) -> None:
    from ultralytics import YOLO

    data_root = data_dir / "yolo" / "l1"
    if not (data_root / "train").exists():
        raise FileNotFoundError(f"缺少 {data_root}/train，请先运行 python -m dsh_visit.train.data")

    model = YOLO("yolov8n-cls.pt")  # 轻量分类预训练（约 5MB，首次自动下载）
    model.train(
        data=str(data_root),  # 分类数据集：目录（train/val 各含类别子目录）
        epochs=epochs,
        imgsz=224,
        batch=64,             # RTX 3060 6GB 稳妥值
        patience=20,          # 早停
        device=device,
        project=str(MODELS_DIR / "runs"),
        name="l1",
    )
    print(f"训练完成，best.pt 位于 {MODELS_DIR / 'runs' / 'l1' / 'weights' / 'best.pt'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="训练 L1 分类器（content vs structure）")
    parser.add_argument("--data-dir", default=str(DATA_DIR))
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--device", default="0", help="cuda 设备号或 cpu")
    args = parser.parse_args()
    train_l1(Path(args.data_dir), args.epochs, args.device)


if __name__ == "__main__":
    main()
