"""统一命令行入口：`python -m dsh_visit <cmd>`。

桥接协议（docs/architecture.md §6）：
  - stdout 输出单个 JSON 对象（utf-8）
  - 退出码：0 成功 / 1 参数或 IO 错误 / 2 推理层错误

子命令：classify-image / classify-structure / detect-image / parse-ui / ocr / status
"""

import argparse
import json
import sys

from ._paths import (
    DATA_DIR,
    DETECT_COCO_WEIGHTS,
    DETECT_WORLD_WEIGHTS,
    L1_WEIGHTS,
    L2_WEIGHTS,
    MODELS_DIR,
    OMP_MODELS_DIR,
    PROJECT_ROOT,
    require_image,
)


def _emit(payload: dict, exit_code: int = 0) -> None:
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(exit_code)


def _fail(message: str, exit_code: int = 2) -> None:
    print(json.dumps({"status": "error", "message": message}, ensure_ascii=False))
    sys.exit(exit_code)


def _load_image(args) -> str:
    try:
        return str(require_image(args.input))
    except (FileNotFoundError, ValueError) as exc:
        _fail(str(exc), exit_code=1)


# ---- 子命令实现 -------------------------------------------------------------

def cmd_classify_image(args) -> None:
    from .classify import classify_l1

    path = _load_image(args)
    try:
        _emit(classify_l1(path))
    except Exception as exc:  # 推理层错误 → 退出码 2
        _fail(f"classify-image 失败: {exc}")


def cmd_classify_structure(args) -> None:
    from .classify import classify_l2

    path = _load_image(args)
    try:
        _emit(classify_l2(path))
    except Exception as exc:
        _fail(f"classify-structure 失败: {exc}")


def cmd_detect_image(args) -> None:
    from .detect import detect_natural_image

    path = _load_image(args)
    try:
        _emit(detect_natural_image(
            path,
            text_prompts=args.text_prompts,
            conf=args.conf,
            max_detections=args.max_detections,
        ))
    except Exception as exc:
        _fail(f"detect-image 失败: {exc}")


def cmd_parse_ui(args) -> None:
    from .ui_parse import parse_ui_screenshot

    path = _load_image(args)
    try:
        _emit(parse_ui_screenshot(path))
    except Exception as exc:
        _fail(f"parse-ui 失败: {exc}")


def cmd_ocr(args) -> None:
    from .ocr import ocr_image

    path = _load_image(args)
    try:
        _emit(ocr_image(path, with_table=args.with_table))
    except Exception as exc:
        _fail(f"ocr 失败: {exc}")


def cmd_status(args) -> None:
    """环境与模型就绪度自检（供 verify 脚本 / 人查错用）。"""
    def check(name: str, path, exists_ok=True) -> dict:
        return {"name": name, "path": str(path), "ready": path.exists() if exists_ok else None}

    _emit({
        "project_root": str(PROJECT_ROOT),
        "models_dir": str(MODELS_DIR),
        "data_dir": str(DATA_DIR),
        "weights": [
            check("L1 分类器", L1_WEIGHTS),
            check("L2 分类器", L2_WEIGHTS),
            check("YOLO11 COCO", DETECT_COCO_WEIGHTS),
            check("YOLO-World", DETECT_WORLD_WEIGHTS),
        ],
        "omniparser": check("OmniParser", OMP_MODELS_DIR),
        "note": "L1/L2 权重由 M2 训练产出；检测权重缺失时首次调用自动下载；"
                "OmniParser 由 M3 安装。骨架阶段分类走启发式占位（degraded=true）。",
    })


# ---- 入口 -------------------------------------------------------------------

def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="dsh_visit", description="dsh-vision-triage 本地推理后端")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("classify-image", help="L1 大分类 content vs structure")
    p.add_argument("--input", required=True, help="图片路径")
    p.set_defaults(func=cmd_classify_image)

    p = sub.add_parser("classify-structure", help="L2 细分 ui/text/form")
    p.add_argument("--input", required=True, help="图片路径")
    p.set_defaults(func=cmd_classify_structure)

    p = sub.add_parser("detect-image", help="内容图像目标检测（YOLO11 / YOLO-World）")
    p.add_argument("--input", required=True, help="图片路径")
    p.add_argument("--text-prompts", default=None, help="逗号分隔开放词汇（YOLO-World）")
    p.add_argument("--conf", type=float, default=0.25, help="置信度阈值")
    p.add_argument("--max-detections", type=int, default=100)
    p.set_defaults(func=cmd_detect_image)

    p = sub.add_parser("parse-ui", help="UI 结构化解析（OmniParser v2）")
    p.add_argument("--input", required=True, help="截图路径")
    p.set_defaults(func=cmd_parse_ui)

    p = sub.add_parser("ocr", help="OCR 文本提取（RapidOCR）")
    p.add_argument("--input", required=True, help="图片路径")
    p.add_argument("--with-table", action="store_true", help="尝试表格结构识别（M3）")
    p.set_defaults(func=cmd_ocr)

    p = sub.add_parser("status", help="环境/模型就绪度自检")
    p.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
