# dsh_visit 本地推理后端

两种运行模式，复用同一套实现：
- **常驻后端（默认，DSH 插件使用）**：`python -m dsh_visit daemon`——行式 JSON-RPC 服务，
  模型引擎进程内缓存（parse-ui 首次 ~36s，之后秒级）。插件经
  `plugin/src/backend.js` spawn 并通信，生命周期由 `manage_vision_backend` 工具管理。
- **单次 CLI（调试/测试/脚本）**：`python -m dsh_visit <cmd>`，每次调用一个进程。

## 子命令

| 命令 | 对应工具 | 说明 |
|---|---|---|
| `classify-image --input <path>` | ① classify_image | L1 大分类 |
| `classify-structure --input <path>` | ② classify_structure | L2 细分 |
| `detect-image --input <path> [--text-prompts ...]` | ③ detect_natural_image | YOLO11 / YOLO-World |
| `parse-ui --input <path>` | ④ parse_ui_screenshot | OmniParser v2（setup-omniparser.ps1 安装） |
| `ocr --input <path> [--with-table]` | ⑤ ocr_image | RapidOCR + 表格结构识别 |
| `status` | — | 环境/模型就绪度自检 |
| `daemon` | — | 常驻 JSON-RPC 服务（stdin/stdout 协议，见 `dsh_visit/daemon.py`） |

单次 CLI 输出为 stdout 单行 JSON（utf-8）；退出码 `0` 成功 / `1` 参数或 IO 错误 / `2` 推理层错误。

## 快速自测

```powershell
# 自检
& E:\conda\envs\sdenv\python.exe -m dsh_visit status

# 常驻后端冒烟（RPC 协议、模型懒加载、常驻加速、shutdown）
& E:\conda\envs\sdenv\python.exe .\tests\smoke_daemon.py
# 自检
& E:\conda\envs\sdenv\python.exe -m dsh_visit status

# 随机占位分类器（不训练，让 classify 走真实 yolo 路径；夜间训练真实权重后 export 覆盖）
& E:\conda\envs\sdenv\python.exe -m dsh_visit.train.init_random

# 端到端冒烟（生成测试图，跑 classify/detect/ocr/表格）
& E:\conda\envs\sdenv\python.exe .\tests\smoke_cli.py

# M2：数据 → 训练 → 导出
& E:\conda\envs\sdenv\python.exe -m dsh_visit.train.data --data-dir <data>
& E:\conda\envs\sdenv\python.exe -m dsh_visit.train.train_l1 --data-dir <data> --epochs 50
& E:\conda\envs\sdenv\python.exe -m dsh_visit.train.export l1
```

## 包结构

```
dsh_visit/
├── cli.py            # 统一入口（子命令 → JSON）
├── _paths.py         # 项目根/模型目录/数据目录约定
├── classify/         # L1/L2 分类 + 置信度回退策略（model.py / fallback.py）
├── detect/           # YOLO11 / YOLO-World
├── ocr/              # RapidOCR
├── ui_parse/         # OmniParser v2（M3）
└── train/            # M2：data.py / train_l1.py / train_l2.py / export.py
```

## 关键约束（踩坑规避）

- **transformers 锁定 4.x**（ADR-8）：OmniParser 的 Florence-2 与 transformers 5.x 不兼容。
- **不用 paddle**（ADR-9）：Python 3.13 装不上；OCR 一律 RapidOCR。
- **空 OCR 修补**（ADR-10）：OmniParser 纯内容图崩溃的 `zip(None)` bug，接入时内置修补。
- **启发式占位**（ADR-5）：L1/L2 权重未训练时分类走 `classify/fallback.py`，
  置信度恒 < 0.6，强制触发"降级到 QwenVL 交叉验证"策略。
