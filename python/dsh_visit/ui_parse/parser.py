"""OmniParser v2 UI 结构化解析（M3 接入完成）。

依赖裁剪与修补（ADR-8/9/10，均已落实在 util/utils.py）：
- transformers 锁定 4.x（4.57.2，Florence-2 与 5.x 不兼容）
- paddle 硬依赖已裁剪：OCR 一律 EasyOCR（中英文），use_paddleocr=False
- 空 OCR 崩溃已修补：纯内容图（无文字）时 ocr_bbox 用 [] 而非 None（原代码 zip(None) 崩溃）

输出规范（与 plugin/src/tools/parse-ui-screenshot.js 的 output schema 严格对应）：
  {status, element_count, elements: [{type, text, bbox, description}], texts, message}
"""

import os
import sys
from pathlib import Path

from .._paths import OMP_MODELS_DIR

# 本机无法直连 huggingface.co（文件 CDN 被墙），HF 下载统一走镜像；
# 若环境已可直连，可自行移除。影响：Florence-2 remote code / processor 的拉取。
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

OMP_ROOT = OMP_MODELS_DIR / "OmniParser"
WEIGHTS_DIR = OMP_MODELS_DIR / "weights"
SOM_MODEL_PATH = WEIGHTS_DIR / "icon_detect" / "model.pt"
CAPTION_MODEL_PATH = WEIGHTS_DIR / "icon_caption_florence"

BOX_TRESHOLD = 0.05   # OmniParser v2 默认
IOU_THRESHOLD = 0.7
BATCH_SIZE = 32       # Florence-2 批量（显存小可调低，官方 128 约 4GB 显存）

INSTALL_HINT = (
    "OmniParser 未就绪。请运行 scripts/setup-omniparser.ps1："
    "git clone https://github.com/microsoft/OmniParser <models>/omniparser/OmniParser，"
    "并从 huggingface.co/microsoft/OmniParser-v2.0 下载权重到 <models>/omniparser/weights/"
    "（icon_detect/model.pt + icon_caption_florence/*，约 1.1GB）。"
)

_engine = None  # (get_som_labeled_img, som_model, caption_model_processor)


def _load_engine():
    """惰性加载 OmniParser（首次调用 15-25s：Florence-2 1GB + YOLO + EasyOCR）。"""
    global _engine
    if _engine is not None:
        return _engine
    if not OMP_ROOT.exists() or not SOM_MODEL_PATH.exists() or not (CAPTION_MODEL_PATH / "model.safetensors").exists():
        raise RuntimeError(INSTALL_HINT)

    sys.path.insert(0, str(OMP_ROOT))  # 使 `util` 解析到 OmniParser 的 util 包
    from util.utils import get_som_labeled_img, get_yolo_model, get_caption_model_processor, check_ocr_box

    som_model = get_yolo_model(model_path=str(SOM_MODEL_PATH))  # ultralytics YOLO 分支
    caption_processor = get_caption_model_processor(
        model_name="florence2", model_name_or_path=str(CAPTION_MODEL_PATH),
    )
    _engine = (get_som_labeled_img, check_ocr_box, som_model, caption_processor)
    return _engine


def parse_ui_screenshot(image_path) -> dict:
    """返回规范输出；未就绪/异常均返回结构化 JSON（不抛错，避免 DSH 工具崩溃）。"""
    try:
        get_som_labeled_img, check_ocr_box, som_model, caption_processor = _load_engine()
    except Exception as exc:
        return {
            "status": "not_ready",
            "element_count": 0,
            "elements": [],
            "texts": [],
            "message": f"OmniParser 未就绪: {exc}",
        }

    try:
        import contextlib
        import io
        from PIL import Image

        img = Image.open(str(image_path)).convert("RGB")
        w, h = img.size

        # 静音管线进度输出（ultralytics / OmniParser 会向 stdout/stderr 打印，
        # 会污染 CLI 的 JSON 输出协议；backend.js 也已按"最后一行 JSON"容错）。
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            # OCR（EasyOCR 中英文）
            (ocr_text, ocr_bbox), _ = check_ocr_box(
                img, display_img=False, output_bb_format="xyxy",
                easyocr_args={"text_threshold": 0.8}, use_paddleocr=False,
            )

            box_overlay_ratio = max(w, h) / 3200
            draw_bbox_config = {
                "text_scale": 0.8 * box_overlay_ratio,
                "text_thickness": max(int(2 * box_overlay_ratio), 1),
                "text_padding": max(int(3 * box_overlay_ratio), 1),
                "thickness": max(int(3 * box_overlay_ratio), 1),
            }

            # 核心解析：YOLO 检测 UI 元素 + Florence-2 语义描述 + OCR 文本
            _, _, parsed_content_list = get_som_labeled_img(
                img, som_model,
                BOX_TRESHOLD=BOX_TRESHOLD,
                output_coord_in_ratio=True,
                ocr_bbox=ocr_bbox,
                draw_bbox_config=draw_bbox_config,
                caption_model_processor=caption_processor,
                ocr_text=ocr_text,
                use_local_semantics=True,
                iou_threshold=IOU_THRESHOLD,
                scale_img=False,
                imgsz=None,  # 默认取原图尺寸
                batch_size=BATCH_SIZE,
            )

            # 映射为规范输出（bbox 为 ratio 坐标 → 还原像素坐标）
            elements = []
            texts = []
            for elem in parsed_content_list or []:
                box = elem.get("bbox") or [0, 0, 0, 0]
                bbox = [int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)]
                content = elem.get("content") or ""
                if elem.get("type") == "text":
                    texts.append(content)
                    elements.append({"type": "text", "text": content, "bbox": bbox, "description": ""})
                else:
                    elements.append({"type": "icon", "text": "", "bbox": bbox, "description": content})

        return {
            "status": "ok",
            "element_count": len(elements),
            "elements": elements,
            "texts": texts,
            "message": "",
        }
    except Exception as exc:
        return {
            "status": "error",
            "element_count": 0,
            "elements": [],
            "texts": [],
            "message": f"{type(exc).__name__}: {exc}",
        }
