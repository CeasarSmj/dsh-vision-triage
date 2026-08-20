"""生成随机参数的 L1/L2 占位分类器（不训练，仅打通推理管线）。

背景：M2 训练占用算力，用户夜间自行执行 train_l1/train_l2 + export（覆盖占位权重）。
在此之前用随机初始化的 yolov8n-cls 权重占位，使 classify_image / classify_structure
走真实 yolo-classify 推理路径（而非启发式 fallback），管线可端到端测试。

随机模型的输出置信度通常 < 0.6 → 触发 degraded 交叉验证策略（ADR-5），
与"占位结果不可信"的语义一致；类别名由 classify/model.py 的 WEIGHT_CLASS_NAMES
显式映射，不依赖模型文件内 names。

用法：
  python -m dsh_visit.train.init_random [--stage l1|l2] [--seed 42]

产出：
  models/classify/l1.pt（content/structure 二分类）
  models/classify/l2.pt（ui/text/form 三分类）
"""

import argparse
from pathlib import Path

from .._paths import L1_WEIGHTS, L2_WEIGHTS


def init_random(stage: str, seed: int = 42) -> Path:
    import torch.nn as nn
    from ultralytics import YOLO

    nc = 2 if stage == "l1" else 3
    out = L1_WEIGHTS if stage == "l1" else L2_WEIGHTS
    out.parent.mkdir(parents=True, exist_ok=True)

    model = YOLO("yolov8n-cls.yaml")  # 随机初始化的分类骨架
    # 重建分类头为指定类别数：随机骨架默认 1000 类，top1 会越界且置信度恒极低
    seq = model.model.model  # ClassificationModel -> nn.Sequential
    head = seq[-1]  # Classify head
    in_features = head.linear.in_features
    head.nc = nc
    head.linear = nn.Linear(in_features, nc)

    model.save(str(out))  # 保存随机权重（类别名由 WEIGHT_CLASS_NAMES 显式映射）
    print(f"已生成随机占位分类器: {out}（{out.stat().st_size / 1e6:.1f} MB，{nc} 类，未训练）")
    print("夜间训练后运行 `python -m dsh_visit.train.export <stage>` 覆盖为真实权重。")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="生成随机参数占位分类器（不训练）")
    parser.add_argument("--stage", choices=["l1", "l2", "all"], default="all")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    stages = ["l1", "l2"] if args.stage == "all" else [args.stage]
    for s in stages:
        init_random(s, args.seed)


if __name__ == "__main__":
    main()
