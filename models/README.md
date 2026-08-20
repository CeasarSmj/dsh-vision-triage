# models/ — 模型权重目录（不入库，大文件）

```
models/
├── classify/
│   ├── l1.pt               # L1 分类器（content/structure）
│   └── l2.pt               # L2 分类器（ui/text/form）
├── detect/
│   ├── yolo11n.pt          # COCO 80 类（缺失时首次调用自动下载）
│   └── yolov8s-worldv2.pt  # YOLO-World 开放词汇（text_prompts 时使用）
├── omniparser/             # OmniParser v2（setup-omniparser.ps1 安装，约 1.1GB）
└── runs/                   # ultralytics 训练日志与产物
```

## 分类器权重（两种来源）

1. **随机占位（默认，不占算力）**：`python -m dsh_visit.train.init_random` 一键生成
   随机初始化的 yolov8n-cls 权重（L1 二分类 / L2 三分类，各约 3MB），让分类工具走真实
   yolo-classify 推理路径。随机模型置信度通常 < 0.6 → `degraded=true` 触发交叉验证。
2. **真实训练（夜间自行启动）**：数据就绪后
   `train.data` → `train.train_l1` / `train.train_l2` → `train.export l1|l2` 覆盖占位权重，
   推理路径无需任何改动。

路径约定见 `python/dsh_visit/_paths.py`，可用 `DSH_VISIT_MODELS_DIR` 覆盖。
