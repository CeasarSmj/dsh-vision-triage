"""L1 大分类：content vs structure。"""

from .._paths import L1_WEIGHTS
from .fallback import heuristic_l1
from .model import CONFIDENCE_THRESHOLD, classify_with_yolo


def classify_l1(image_path) -> dict:
    """返回规范输出：
    {category, confidence, degraded, model, note}
    """
    weights = L1_WEIGHTS
    if weights.exists():
        category, confidence = classify_with_yolo(weights, image_path)
        model_id = weights.name
    else:
        category, confidence = heuristic_l1(image_path)
        model_id = "heuristic-l1 (placeholder)"
        note = "L1 权重缺失，使用启发式占位分类（M2 训练后自动切换）"
    degraded = confidence < CONFIDENCE_THRESHOLD
    return {
        "category": category,
        "confidence": round(confidence, 4),
        "degraded": bool(degraded),
        "model": model_id,
        "note": note if "note" in dir() else f"置信度 {confidence:.2f}",
    }
