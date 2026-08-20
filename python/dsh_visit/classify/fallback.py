"""启发式占位分类器（M2 训练就绪前的临时实现，ADR-5 / ADR-3）。

原则：宁可恒低置信度触发 degrade（< 0.6 → LLM 改用 describe_image 交叉验证），
也绝不给出"看似自信"的错误分类。骨架阶段用它保证流水线端到端可跑。
"""

import cv2
import numpy as np

PLACEHOLDER_CONFIDENCE = 0.55  # 恒低于 0.6 阈值，强制走回退策略

STRUCTURE_CLASSES = ("content", "structure")
STRUCTURE_L2_CLASSES = ("ui", "text", "form")


def heuristic_l1(path) -> tuple[str, float]:
    """content vs structure 启发式：
    - 结构图（文本/UI/表单）：高边缘密度 + 高短线密度（字形、控件、表格线）、低色彩度
    - 内容图（照片）：平滑梯度、高色彩度
    """
    img = cv2.imread(str(path))
    if img is None:
        raise ValueError(f"无法读取图片: {path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    edges = cv2.Canny(gray, 50, 150)
    edge_density = float(edges.mean() / 255.0)

    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=30, minLineLength=8, maxLineGap=3)
    n_lines = min(len(lines), 2000) if lines is not None else 0
    h, w = gray.shape
    line_density = n_lines / (h * w / 1e5)  # 每 10 万像素的短线数

    saturation = float(hsv[:, :, 1].mean() / 255.0)

    score = 0.45 * edge_density + 0.10 * min(line_density / 50, 0.5) - 0.35 * saturation
    category = "structure" if score > 0 else "content"
    return category, PLACEHOLDER_CONFIDENCE


def heuristic_l2(path) -> tuple[str, float]:
    """ui / text / form 启发式（仅对 structure 图像使用）：
    - form：大量长水平/垂直线（表格线、表单分隔线）
    - text：文本行多、网格线少
    - ui：默认（有文本行 + 规则矩形控件）
    """
    img = cv2.imread(str(path))
    if img is None:
        raise ValueError(f"无法读取图片: {path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    h, w = gray.shape

    # 长直线密度（表格线/分隔线）
    long_lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=60, minLineLength=min(h, w) * 0.3, maxLineGap=5
    )
    n_long = len(long_lines) if long_lines is not None else 0
    long_density = n_long / (h * w / 1e5)

    # 文本行数（用 OCR 统计，可能失败则按 0 处理）
    n_text_lines = 0
    try:
        from ..ocr.ocr import ocr_image

        n_text_lines = len(ocr_image(path)["lines"])
    except Exception:
        pass

    if long_density > 0.8:
        category = "form"
    elif n_text_lines >= 5:
        category = "text"
    else:
        category = "ui"
    return category, PLACEHOLDER_CONFIDENCE
