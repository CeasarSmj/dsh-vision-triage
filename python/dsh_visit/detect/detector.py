"""目标检测：YOLO11（COCO 80 类）/ YOLO-World（开放词汇，text_prompts）。"""

from pathlib import Path

from .._paths import DETECT_COCO_WEIGHTS, DETECT_WORLD_WEIGHTS


def _ensure_model(weights: Path) -> Path:
    """权重缺失时尝试从 ultralytics assets 下载；失败给出明确指引。"""
    if weights.exists():
        return weights
    try:
        from ultralytics.utils.downloads import attempt_download_asset

        attempt_download_asset(str(weights), repo="ultralytics/assets", release="v8.3.0")
    except Exception:
        pass
    if not weights.exists():
        raise RuntimeError(
            f"检测权重缺失: {weights}（自动下载失败，请手动下载后放到该路径）"
        )
    return weights


def detect_natural_image(
    image_path,
    text_prompts: str | None = None,
    conf: float = 0.25,
    max_detections: int = 100,
) -> dict:
    """返回规范输出：
    {count, model, detections: [{label, confidence, bbox: [x1,y1,x2,y2]}]}
    """
    from ultralytics import YOLO

    use_world = bool(text_prompts and text_prompts.strip())
    if use_world:
        weights = _ensure_model(DETECT_WORLD_WEIGHTS)
        model = YOLO(str(weights))
        prompts = [p.strip() for p in text_prompts.split(",") if p.strip()]
        model.set_classes(prompts)
    else:
        weights = _ensure_model(DETECT_COCO_WEIGHTS)
        model = YOLO(str(weights))

    results = model(str(image_path), conf=conf, verbose=False)
    boxes = results[0].boxes
    names = results[0].names

    detections = []
    if boxes is not None:
        for box in boxes:
            cls_id = int(box.cls.item())
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            detections.append({
                "label": str(names[cls_id]),
                "confidence": round(float(box.conf.item()), 4),
                "bbox": [x1, y1, x2, y2],
            })

    detections = detections[: max(0, int(max_detections))]
    return {"count": len(detections), "model": weights.name, "detections": detections}
