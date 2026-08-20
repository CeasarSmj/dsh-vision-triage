"""RapidOCR 文本提取（ADR-4：不造轮子，直接引用现成方案）。

- 文本提取：RapidOCR（模型首次使用自动下载缓存，之后离线可用）
- 表格结构识别（--with-table）：RapidAI TableStructureRec（pip 包 rapid_table，
  SLANet+ 模型，modelscope 源，首次自动下载；复用已识别的 OCR 结果避免二次识别）

模型缓存：rapid_table 的 SLANet+ 模型下载到 ~/.cache/rapid_table（ModelProcessor 默认）。
"""

import numpy as np

_engine = None
_table_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _engine = RapidOCR()
    return _engine


def _get_table_engine():
    """RapidTable（SLANet+）。首次调用下载模型（modelscope，约 30MB）。"""
    global _table_engine
    if _table_engine is None:
        from rapid_table import RapidTable

        _table_engine = RapidTable()
    return _table_engine


def _build_table(engine, image_path, result) -> dict:
    """用已识别的 OCR 结果跑 RapidTable 表格结构识别，返回结构化表格。"""
    try:
        table_engine = _get_table_engine()
        # rapid_table 期望 (boxes_np, texts, scores) 三元组列表；result 为
        # rapidocr 的 [[box4points, text, score], ...]，直接构造，避免二次 OCR
        ocr_results = None
        if result:
            boxes = np.array([item[0] for item in result], dtype=np.float32)  # (N, 4, 2)
            texts = tuple(str(item[1]) for item in result)
            scores = tuple(float(item[2]) for item in result)
            ocr_results = [(boxes, texts, scores)]

        out = table_engine(str(image_path), ocr_results=ocr_results)
        html = (out.pred_htmls or [""])[0]
        cell_count = len(out.cell_bboxes[0]) if (out.cell_bboxes and out.cell_bboxes[0] is not None) else 0
        return {
            "html": html,
            "cell_count": int(cell_count),
            "elapse": round(float(out.elapse), 3),
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def ocr_image(image_path, with_table: bool = False) -> dict:
    """返回规范输出：
    {status, text, lines: [{text, confidence, bbox}], table}
    """
    engine = _get_engine()
    result, _ = engine(str(image_path))  # result: list of [box, text, score] 或 None

    lines = []
    if result:
        for item in result:
            box, text, score = item[0], item[1], item[2]
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            lines.append({
                "text": str(text),
                "confidence": round(float(score), 4),
                "bbox": [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))],
            })

    table = None
    if with_table:
        table = _build_table(engine, image_path, result)

    return {
        "status": "ok",
        "text": "\n".join(line["text"] for line in lines),
        "lines": lines,
        "table": table,
    }
