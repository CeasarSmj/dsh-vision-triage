# 架构 — 分级视觉处理流水线

> 对应 [项目需求.md](../项目需求.md) §3。本文档描述组件布局、数据流与工程约定。

## 1. 总览

```
                        ┌─────────────────────────────┐
  图片 ────────────────► │  L1 大分类 (yolo-classify)   │
                        │  content vs structure        │
                        └──────────────┬──────────────┘
                                       │
              ┌────────────────────────┴────────────────────────┐
              ▼                                                 ▼
     content (内容承载)                                 structure (结构承载)
     → YOLO / YOLO-World 本地检测                           │
     → 细节/语义 → QwenVL 追问                    ┌────────────────────────┐
                                                  │  L2 细分 (yolo-classify) │
                                                  │  ui / text / form       │
                                                  └──────┬─────────┬───────┘
                                                         ▼         ▼
                                                 ui → OmniParser   text/form → OCR
                                                 (元素/布局)         (文本/表格)
```

## 2. 分层职责

| 层 | 模块 | 职责 | 后端 |
|---|---|---|---|
| 表现层 | `plugin/`（DSH 插件） | 向 LLM 注册 6 个工具；解析参数、渲染结果；调用 Python 桥 | `@deepseek-ai/dsh-tools` |
| 桥接层 | `plugin/src/backend.js` | 拉起 `python -m dsh_visit <cmd>` 子进程，JSON 进出，超时/取消透传 | Node `child_process` |
| 推理层 | `python/dsh_visit/` | 分类 / 检测 / OCR / UI 解析 / 训练，全部本地 PyTorch | torch + ultralytics + RapidOCR + OmniParser |
| 云端层 | `plugin/src/describe-image.js` | Qwen-VL 语义追问（仅按需），沿用 dsh-vision-mcp 的凭据/HTTP 实现 | DashScope OpenAI 兼容 API |

**分层原则**：插件只做"参数↔JSON"与进程编排，不做任何图像处理；Python 端只做推理，
不了解 DSH 会话语义；描述（description）把"推荐流程 + 回退策略"写给 LLM，由 LLM 自主组装，**不做固定程序化编排**。

## 3. 分类体系（设计哲学）

依据图像**内容如何表达含义**分为两大类：

- **内容承载型 `content`**：靠图像像素内容本身表达（物体、场景、光影、透视）→ 照片、CG、插画、画作。
- **结构承载型 `structure`**：靠文字与布局规则表达（字体、控件、表格线、排版）→ 纯文本、表单、UI、文档。

自然图像本质是"透视 + 对象化分层"；人工界面本质是"图元组合 + 显式空间关系"。
两类构成过程差异巨大，分开处理。

- **L1**：`content` vs `structure`（yolo-classify 二分类）。
- **L2**（仅 structure 内部）：`ui` / `text` / `form`（yolo-classify 三分类）。
- **嵌套不归分类器管**：UI 内的照片/表单区域由 OmniParser 逐元素识别（OmniParser 会把内嵌图像
  检测为一个元素并用 Florence-2 生成语义描述——原型已验证）。
- **OmniParser 不参与分类决策**：它加载 1.3GB 模型需 15-25s，分类只用轻量模型。

## 4. 回退策略（§3.4-5）

- 分类置信度 **< 0.6** 时返回 `degraded: true`，工具描述中指示 LLM：改用 `describe_image` 交叉验证，
  保证不劣于"所有图片一律走云端"的现状。
- 分类器权重缺失（M2 未训练）时，Python 端使用**启发式占位实现**（`classify/fallback.py`，
  边缘/直线密度 + 色彩饱和度），置信度固定压到 0.6 以下，使管线在骨架阶段即可端到端跑通，
  且不会产生"看似可信"的错误分类。
- OmniParser 未安装/模型未下载时返回 `{ status: "not_ready" }` + 安装指引，不崩溃。

## 5. 目录与路径约定

| 路径 | 用途 | 默认 | 环境变量覆盖 |
|---|---|---|---|
| 项目根 | 包内自定位（`python/dsh_visit/_paths.py`） | 自动推断 | `DSH_VISIT_ROOT` |
| 模型目录 | L1/L2 权重、YOLO 权重、OmniParser 模型 | `<root>/models` | `DSH_VISIT_MODELS_DIR` |
| 数据目录 | M2 真实数据 | `<root>/data` | `DSH_VISIT_DATA_DIR` |
| Python 解释器 | 桥接层子进程 | `E:\conda\envs\sdenv\python.exe` | `DSH_VISIT_PYTHON` |

权重约定：

```
models/
├── classify/l1.pt            # L1 训练产物（train/export.py 产出）
├── classify/l2.pt            # L2 训练产物
├── detect/yolo11n.pt         # COCO 80 类（缺失时 ultralytics 自动下载）
├── detect/yolov8s-worldv2.pt # 开放词汇检测（text_prompts 时使用）
└── omniparser/               # OmniParser v2 模型（M3 下载，约 1.3GB）
```

## 6. 桥接协议（常驻后端 + 行式 JSON-RPC）

`plugin/src/backend.js` 维持一个常驻 Python 进程（`python -m dsh_visit daemon`），
本地工具（分类/检测/OCR/UI 解析）经 **stdin/stdout 行式 JSON-RPC** 调用：

```
请求（stdin 每行）:  {id, method, params}
响应（stdout 每行）: {id, ok: true, result} | {id, ok: false, error}
方法: classify_image / classify_structure / detect_image / ocr / parse_ui / ping / shutdown
```

**设计要点（ADR-14）**：
- **常驻缓存**：模型引擎（OmniParser Florence-2 / RapidOCR / RapidTable / YOLO / 分类器）
  为 daemon 进程内模块级单例，首次调用加载、之后秒级响应
  （parse-ui 实测：36s → 1.3s）。进程拉起时零 GPU 占用，模型懒加载。
- **生命周期**：`manage_vision_backend` 工具（status / release / restart）供 agent 管理；
  `release` 关闭 daemon 归还 GPU（OmniParser 常驻约 2.4GB）；插件 dispose（DSH 关闭）自动
  release 防僵尸进程；daemon 崩溃后下次调用自动重启。
- **超时/取消**：Node 侧 per-call 超时（`timeoutMs`）；`exec.signal` 触发时拒绝调用，
  迟到的响应按 id 丢弃（模型调用在 daemon 内继续完成，无副作用）。
- **stdout 保护**：daemon 把模型库的进度输出（ultralytics/tqdm/easyocr）重定向到 stderr，
  协议行走保留的真实 stdout fd，避免污染。

> CLI 单次模式（`python -m dsh_visit <cmd>`）仍保留，供调试/测试/脚本使用，
> 与 daemon 复用同一套实现。
