"""M2 训练：L1 分类器（content vs structure，yolo-classify）。

用法：
  python -m dsh_visit.train.train_l1 --data-dir <data> --epochs 50
先运行 train/data.py 生成数据集与 YAML。
"""

import argparse
from pathlib import Path

from .._paths import DATA_DIR, MODELS_DIR


def train_l1(data_dir: Path, epochs: int, device: str) -> None:
    from ultralytics import YOLO

    yaml_path = data_dir / "yolo" / "l1.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"缺少 {yaml_path}，请先运行 python -m dsh_visit.train.data")

    model = YOLO("yolov8n-cls.pt")  # 轻量分类预训练（约 5MB，首次自动下载）
    model.train(
        data=str(yaml_path),
        epochs=epochs,
        imgsz=224,
        device=device,
        project=str(MODELS_DIR / "runs"),
        name="l1",
    )
    print(f"训练完成，best.pt 位于 {MODELS_DIR / 'runs' / 'l1' / 'weights' / 'best.pt'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="训练 L1 分类器（content vs structure）")
    parser.add_argument("--data-dir", default=str(DATA_DIR))
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--device", default="0", help="cuda 设备号或 cpu")
    args = parser.parse_args()
    train_l1(Path(args.data_dir), args.epochs, args.device)


if __name__ == "__main__":
    main()
