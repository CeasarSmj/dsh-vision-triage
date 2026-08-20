"""yolo-classify 推理包装：加载权重 → 返回 (类别, 置信度)。

权重为 M2 训练产物（models/classify/l1.pt / l2.pt，由 train/export.py 复制 best.pt），
或 train/init_random.py 生成的随机占位权重。权重缺失时调用方回退到启发式占位（fallback.py）。

类别名不依赖模型文件内 names（随机占位模型的 names 是 0..999 默认值），
由调用方按权重约定显式传入（ADR：模型与代码解耦）。
"""

from pathlib import Path

CONFIDENCE_THRESHOLD = 0.6  # 低于该值 → degraded（ADR-5）

# 各权重的类别名约定（与 train/data.py 的类别顺序一致）
WEIGHT_CLASS_NAMES: dict[str, tuple[str, ...]] = {
    "l1.pt": ("content", "structure"),
    "l2.pt": ("ui", "text", "form"),
}


def classify_with_yolo(weights: Path, image_path: Path) -> tuple[str, float]:
    """运行 yolo-classify 推理。返回 (类别名, top1 置信度)。"""
    from ultralytics import YOLO

    class_names = WEIGHT_CLASS_NAMES.get(weights.name)
    if class_names is None:
        raise ValueError(f"未知分类权重约定: {weights.name}（期望 l1.pt / l2.pt）")

    model = YOLO(str(weights))
    results = model(str(image_path), verbose=False)
    probs = results[0].probs
    category = class_names[int(probs.top1)]
    confidence = float(probs.top1conf)
    return category, confidence
