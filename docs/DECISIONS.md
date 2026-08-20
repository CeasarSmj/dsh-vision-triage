# 关键决策记录（ADR）

> 对应 [项目需求.md](../项目需求.md) §3.4。每条记录"背景 → 决策 → 理由/代价"，
> 供后续实现与评审引用（编号 = 需求文档编号）。

## ADR-1：两级轻量分类器（yolo-classify）

- **背景**：需要秒级、本地、零云端成本的图像分类，且训练数据来自网络真实图片。
- **决策**：L1（content/structure 二分类）+ L2（ui/text/form 三分类），均用轻量 `yolo-classify` 训练。
- **理由**：与检测环节共用 ultralytics 生态，训练/推理一条链；分类只承担路由，不承担语义。
- **代价**：需要 M2 数据与训练；在权重就绪前用启发式占位（见 ADR-5）。

## ADR-2：本地推理仅 PyTorch

- **决策**：本地推理只用 PyTorch，不做 ONNX/OpenVINO 适配（自用项目，避免双栈维护）。
- **例外**：RapidOCR 本身是 ONNX 运行时，属"不造轮子"引用，不违背本决策。

## ADR-3：数据只用网络真实数据

- **决策**：M2 数据全部来自软件名搜索截图 / 真实照片，不用合成数据；每类 1000 张
  （train 800 + val 200），混入少量噪声可接受。
- **理由**：合成数据在 UI/表单上分布失真；真实分布直接对齐线上负载。

## ADR-4：不造轮子

- **决策**：OCR 用 RapidOCR、UI 解析用 OmniParser v2、检测用 YOLO11/YOLO-World，
  分类训练用 ultralytics 官方 `yolo classify train`。
- **理由**：各领域已有成熟方案，聚焦在"路由编排"这一增量价值上。

## ADR-5：失败回退（置信度阈值 0.6）

- **决策**：分类置信度 < 0.6 时降级——直接走 QwenVL 或交叉验证，保证不劣于现状
  （现状 = 所有图片一律云端）。
- **实现**：工具返回 `degraded: true`，描述中指示 LLM 用 `describe_image` 交叉验证；
  骨架阶段权重缺失时启发式占位的置信度固定 < 0.6，从而始终触发该策略。
- **代价**：低置信度图片多一次云端往返；换来的是"永远不会给出自信的错误分类"。

## ADR-6：OmniParser 只做 UI 结构化输出，不参与分类路由

- **背景**：OmniParser 加载 1.3GB 模型需 15-25s，参与分类会毁掉"秒级分诊"。
- **决策**：分类路由只用轻量分类器；OmniParser 仅在 L2 判定为 `ui` 后调用。
- **代价**：UI 截图中内嵌的图片/表单区域由 OmniParser 逐元素识别兜底（已验证可行）。

## ADR-7：工具编排交给 LLM，不做固定流水线

- **决策**：6 个工具各自独立注册；把"推荐流程 + 阈值/回退策略"写进工具 description，
  由 DSH 的 LLM 自主组装调用序列。
- **理由**：场景组合远超程序化分支可穷举的范围；LLM 已有工具编排能力，成本为零。

## ADR-8（原型教训，重做规避）：transformers 版本锁定 4.x

- **事实**：Florence-2（OmniParser 依赖）与 transformers 5.x 不兼容
  （`EncoderDecoderCache`、`_supports_sdpa`、tied-weights dict 等 API 变更）。
- **决策**：`python/requirements.txt` 锁定 `transformers==4.57.2`（已验证）。
- **补充（实测确认）**：即使 4.57.2，Florence-2 的 HF 缓存 remote code
  （`modeling_florence2.py`）在 `generate` 时仍崩溃——新 generate 流程首步传入空缓存结构
  （`EncoderDecoderCache` / 空元组），旧代码 `past_key_values[0][0].shape[2]` 直接解引用抛
  AttributeError/IndexError。**已修补 HF 缓存 remote code**（幂等脚本
  `scripts/patch-florence-remote-code.ps1`，setup-omniparser.ps1 自动调用）：
  1. `prepare_inputs_for_generation`（两处）：空缓存归一为 `None`；
  2. `past_length` / `past_key_values_length` 取值改为维度安全（`ndim >= 3` 才取 `shape[2]`）。

## ADR-9（原型教训，重做规避）：paddle 依赖裁剪

- **事实**：Python 3.13 下 paddle 通常装不上；OmniParser 的 paddle 硬依赖需裁剪，
  OCR 分支改走 RapidOCR。
- **决策**：本仓库 OCR 一律 RapidOCR；OmniParser 安装按官方流程裁剪 paddle 依赖。

## ADR-10（原型教训，重做规避）：OmniParser 空 OCR bug 修补

- **事实**：纯内容图（无文字）会导致 OmniParser 管道崩溃（`zip(None)` 与裸 list 元素）。
- **决策**：`python/dsh_visit/ui_parse/parser.py` 内置修补：空 OCR 用 `[]` 而非 `None`、
  无 OCR 分支保持 dict 结构。

## ADR-11：桥接层用子进程而非 in-process Python

- **决策**：Node 插件与 Python 后端之间用 `spawn <python> -m dsh_visit` 子进程通信。
- **理由**：进程隔离避免 Python 崩溃/内存泄漏拖垮 DSH 宿主；DSH 端无 Python 嵌入能力。
- **代价**：每次调用有 ~200ms 进程启动开销；OmniParser 首载 15-25s 属于可接受边界。

## ADR-12：本地环境固定为 sdenv，环境变量可覆盖

- **决策**：默认 Python 为 `E:\conda\envs\sdenv\python.exe`（Python 3.13 + torch 2.13 + CUDA），
  插件与脚本均读取 `DSH_VISIT_PYTHON` 覆盖。
- **理由**：原型已验证该环境全栈可用（ultralytics / rapidocr / transformers 4.57.2）。

## ADR-13：表格结构识别用 RapidAI TableStructureRec（rapid_table）

- **背景**：`form` 类图像需要结构化表格输出；PaddleOCR 含表格结构化但 paddle 在
  Python 3.13 装不上（ADR-9）。
- **决策**：`ocr_image --with-table` 用 pip 包 `rapid_table`（SLANet+ 表格结构模型，
  默认从 modelscope 下载，国内可达），复用本工具已跑过的 RapidOCR 结果
  （`(boxes, texts, scores)` 三元组），避免二次 OCR；输出 HTML 表格 + 单元格数。
- **实测坑**：rapid_table 3.0.2 内部 `_init_ocr_engine` 只探测 `rapidocr` 包名
  （新版统一包），sdenv 装的是 `rapidocr-onnxruntime`（1.2.3 分叉包名）→ 内部 OCR
  引擎为 None 会崩溃。解法：**显式传入 `ocr_results`**（非 None 时不再调用内部引擎）。
- **代价**：SLANet+ 对复杂合并单元格/无边框表格的鲁棒性一般；失败时 `table.error`
  携带原因，文本结果不受影响。

## ADR-14：本地工具改走常驻后端（daemon + 行式 JSON-RPC）

- **背景**：旧实现每次工具调用 `spawn` 单次 Python 进程，OmniParser 每次重载
  Florence-2（约 1GB）需 15-36s，多次 UI 解析成本不可接受。
- **决策**：`python -m dsh_visit daemon` 常驻进程持有全部模型引擎（模块级单例、懒加载），
  Node 插件经 stdin/stdout 行式 JSON-RPC 调用；新增 `manage_vision_backend` 工具
  （status / release / restart）供 agent 管理生命周期——**release 关闭常驻进程归还 GPU
  （OmniParser 常驻约 2.4GB）**；插件 dispose 自动 release 防僵尸；daemon 崩溃自动重启。
- **实测**：parse-ui 首次 36s → 常驻二次 1.3s（约 28 倍）。
- **代价**：常驻进程占用 GPU/内存（可用 release 释放）；RPC 增加一层的实现复杂度；
  daemon 需 stdout 保护（模型进度输出重定向 stderr，协议行走真实 fd）。

## ADR-15：深色 UI 自动反色预处理

- **背景**：OmniParser 的 OCR（EasyOCR）与元素检测（YOLO）以浅色 UI 为主训练，
  深色 UI（深底浅字）上表现下降（用户实测，如 Win11 深色托盘面板）。
- **决策**：解析前用平均亮度（ImageStat，缩小 64x64）检测，< `DARK_THRESHOLD`(128)
  时整图 `ImageOps.invert` 反色（深底浅字 → 浅底深字），几何坐标不变，
  返回结果带 `inverted` 标记与 message 说明。阈值 `DARK_THRESHOLD` 可调。
- **实测（重要）**：高对比度合成深色图与真实 DSH 深色设置面板截图上，
  反色前后元素数/文本数**基本持平**（34→35 元素、文本 8→8）——**反色不改变对比度**，
  对低对比度 + 小字号场景收益有限；对纯黑底高对比场景应有帮助。
  保留该预处理（零成本、不劣化），真实收益需按具体截图评估；
  若仍不足，可进一步叠加对比度增强（CLAHE）等，暂未纳入。
