"""L2 细分：ui / text / form（仅对 structure 图像使用）。"""

from .._paths import L2_WEIGHTS
from .fallback import heuristic_l2
from .model import CONFIDENCE_THRESHOLD, classify_with_yolo


def classify_l2(image_path) -> dict:
    """返回规范输出：
    {category, confidence, degraded, model, note}
    """
    weights = L2_WEIGHTS
    if weights.exists():
        category, confidence = classify_with_yolo(weights, image_path)
        model_id = weights.name
    else:
        category, confidence = heuristic_l2(image_path)
        model_id = "heuristic-l2 (placeholder)"
        note = "L2 权重缺失，使用启发式占位分类（M2 训练后自动切换）"
    degraded = confidence < CONFIDENCE_THRESHOLD
    return {
        "category": category,
        "confidence": round(confidence, 4),
        "degraded": bool(degraded),
        "model": model_id,
        "note": note if "note" in dir() else f"置信度 {confidence:.2f}",
    }
