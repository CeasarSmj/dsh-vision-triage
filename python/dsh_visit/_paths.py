"""路径约定：项目根 / 模型目录 / 数据集目录（均可被环境变量覆盖）。"""

from pathlib import Path
import os

# python/dsh_visit/_paths.py → parents[0]=dsh_visit, [1]=python, [2]=项目根
PROJECT_ROOT = Path(os.environ.get("DSH_VISIT_ROOT") or Path(__file__).resolve().parents[2])
MODELS_DIR = Path(os.environ.get("DSH_VISIT_MODELS_DIR") or PROJECT_ROOT / "models")
DATA_DIR = Path(os.environ.get("DSH_VISIT_DATA_DIR") or PROJECT_ROOT / "data")

# 分类权重（train/export.py 产出）
L1_WEIGHTS = MODELS_DIR / "classify" / "l1.pt"
L2_WEIGHTS = MODELS_DIR / "classify" / "l2.pt"

# 检测权重（缺失时自动下载）
DETECT_COCO_WEIGHTS = MODELS_DIR / "detect" / "yolo11n.pt"
DETECT_WORLD_WEIGHTS = MODELS_DIR / "detect" / "yolov8s-worldv2.pt"

# OmniParser v2（M3 安装到此处）
OMP_MODELS_DIR = MODELS_DIR / "omniparser"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def require_image(path: str | Path) -> Path:
    """校验图片路径存在、是文件、扩展名受支持。"""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"图片不存在: {p}")
    if not p.is_file():
        raise ValueError(f"不是普通文件: {p}")
    if p.suffix.lower() not in IMAGE_EXTS:
        raise ValueError(f"不支持的图片扩展名 {p.suffix!r}（支持: {sorted(IMAGE_EXTS)}）")
    return p
