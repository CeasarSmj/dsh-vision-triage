"""检测子系统：YOLO11（COCO 80 类）/ YOLO-World（开放词汇）。"""

from .detector import detect_natural_image

__all__ = ["detect_natural_image"]
