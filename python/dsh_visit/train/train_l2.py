"""M2 训练：L2 分类器（ui / text / form，yolo-classify）。

用法：
  python -m dsh_visit.train.train_l2 --data-dir <data> --epochs 50
"""

import argparse
from pathlib import Path

from .._paths import DATA_DIR, MODELS_DIR


def train_l2(data_dir: Path, epochs: int, device: str) -> None:
    from ultralytics import YOLO

    yaml_path = data_dir / "yolo" / "l2.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"缺少 {yaml_path}，请先运行 python -m dsh_visit.train.data")

    model = YOLO("yolov8n-cls.pt")
    model.train(
        data=str(yaml_path),
        epochs=epochs,
        imgsz=224,
        device=device,
        project=str(MODELS_DIR / "runs"),
        name="l2",
    )
    print(f"训练完成，best.pt 位于 {MODELS_DIR / 'runs' / 'l2' / 'weights' / 'best.pt'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="训练 L2 分类器（ui/text/form）")
    parser.add_argument("--data-dir", default=str(DATA_DIR))
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--device", default="0", help="cuda 设备号或 cpu")
    args = parser.parse_args()
    train_l2(Path(args.data_dir), args.epochs, args.device)


if __name__ == "__main__":
    main()
