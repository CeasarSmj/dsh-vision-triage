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

## 6. 桥接协议

`plugin/src/backend.js` 以子进程方式调用，一次调用一个进程（简单可靠，分类毫秒级、OCR 秒级，
OmniParser 首次 15-25s 属可接受范围）：

```
node 侧:  spawn <python> -m dsh_visit <cmd> --input <path> [--flag ...]
python 侧: stdout 输出单个 JSON 对象（utf-8），错误走 stderr + 非零退出码
```

退出码约定：`0` 成功；`1` 参数/IO 错误；`2` 推理层错误（模型缺失、后端异常）。
超时与取消：Node 侧用 `AbortSignal.any([exec.signal, AbortSignal.timeout(ms)])` 传给 `spawn` 的 `signal`，
子进程被杀后按失败结果返回。
