# dsh-vision-triage（视觉分诊）

为 DSH（DeepSeek Harness）提供一套**分级视觉处理流水线**：先用轻量本地分类器判断图像的
"内容构成类型"，再把图片分流到最合适的处理工具（YOLO / OmniParser / OCR / QwenVL），
在保证可用性的前提下，把简单任务留在本地、把昂贵的云端 VLM 只留给真正需要语义理解的追问环节。

> 名字含义：`triage`（分诊）——像急诊分诊一样，先快速判断"这是什么类型的问题"，再决定送哪个科室处理。
> 仓库：https://github.com/CeasarSmj/dsh-vision-triage
> 完整需求与架构蓝图见 [项目需求.md](./项目需求.md)，本文档是工程说明。

## 快速开始

```powershell
# 1. 克隆仓库
git clone https://github.com/CeasarSmj/dsh-vision-triage.git
cd dsh-vision-triage

# 2. 生成随机占位分类器（不训练，仅打通管线；夜间训练真实权重后 export 覆盖）
& E:\conda\envs\sdenv\python.exe -m dsh_visit.train.init_random   # 需在 python/ 目录或设 PYTHONPATH

# 3. （可选）安装 OmniParser v2（parse_ui_screenshot 需要；clone + 1.1GB 权重 + 自动修补）
.\scripts\setup-omniparser.ps1

# 4. 安装插件到当前 DSH profile（创建 junction + 追加 cordis.patch.yml 行）
.\scripts\install-plugin.ps1 -Profile web

# 5. 自测（不重启 DSH，仅验证 6 工具能注册、后端命令可用）
.\scripts\verify-tools.ps1                     # 结构 + 后端自检
node scripts/smoke-register.mjs                # 6 工具注册冒烟测试
node scripts/smoke-bridge.mjs <图片路径>        # 桥接链路冒烟（真实执行本地工具）
node scripts/smoke-describe.mjs <图片路径>      # 云端 Qwen-VL 实测（读 DSH 凭据）

# 6. 重启 DSH（或等待配置 HMR），确认模型工具目录出现 6 个工具
#    验收标准见 项目需求.md §5
```

## 里程碑状态

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M1 | 重开项目目录，按本文档搭骨架（两级分类器 + 7 工具注册） | ✅ |
| M2 | 真实数据收集并训练 L1/L2 | ✅ 已训练（2026-08-21 夜）：L1 val **100%** / L2 val **88%** |
| M3 | 接入 DSH，验证 7 工具可用与 LLM 自主组装 | 🔶 本地工具与云端已实测，待装入 live profile |
| M4 | 真实负载下成本/延迟/精度对比评测 | ⬜ |

**分类器现状（已训练，占位已替换）**：

| 分类器 | 数据 | val 准确率 | 实测 |
|---|---|---|---|
| L1 content/structure | 1000 真实照片 + 1088 真实网页/截图 | **100%** | 猫咪→content 1.00、Blender→structure 1.00、深色资源管理器→structure 0.95 |
| L2 ui/text/form | 376/342/370 真实网页 | **88%** | 深色资源管理器→ui 0.995、深色设置面板→ui 0.97、表格→form 0.72 |

数据来源：`fetch_content.py`（picsum 真实照片）+ `render-webpages.mjs`（headless Chromium
渲染真实网页，URL 见 `data/urls/`）。权重落于 `models/classify/l1.pt|l2.pt`（gitignore）。
复训：`train.data` → `train.train_l1|train_l2` → 复制 `models/runs/<stage>/weights/best.pt` 覆盖。
`train.init_random` 仍可用作未训练时的占位回退。

**本地工具走常驻后端（ADR-14）**：插件维持 `python -m dsh_visit daemon` 常驻进程，
模型进程内缓存（parse-ui 首次 36s → 之后 **1.3s**，约 28 倍加速）。新增
`manage_vision_backend` 工具供 agent 管理：`status` 查看进程/模型/GPU，
**`release` 释放常驻后端归还 GPU 显存**（下次调用自动重新拉起），`restart` 重启；
插件卸载（DSH 关闭）自动释放。

**无需训练的部分已实跑通**（RTX 3060 6GB / sdenv）：

| 工具 | 状态 | 实测 |
|---|---|---|
| ③ `detect_natural_image` | ✅ | YOLO11 COCO（yolo11n.pt 自动下载）+ YOLO-World 开放词汇（yolov8s-worldv2.pt 338MB），真实照片检出 cat 0.90/0.88 |
| ⑤ `ocr_image` | ✅ | RapidOCR 提取中英文文本；`--with-table` 表格结构识别（RapidAI TableStructureRec/SLANet+）实测：中文 3x4 表格 → 正确 HTML 结构（约 0.2s） |
| ④ `parse_ui_screenshot` | ✅ | OmniParser v2 常驻后端（首次 36s，之后 1.3s），中文 UI 截图实测解析出 25 个元素（13 段中文文本 + 12 图标语义描述） |
| ⑥ `describe_image` | ✅ | 云端 Qwen-VL 实测 6.7s 返回详细中文描述（凭据 `QWEN_VISION_API_KEY` 已配置） |
| ①② 分类器 | ✅ | L1 val 100% / L2 val 88%（2026-08-21 夜训练），真实图实测全部高置信、degraded=false |
| ⑦ `manage_vision_backend` | ✅ | status / release（释放 GPU 显存）/ restart，崩溃自动重启，实测全通 |

> 本机无法直连 huggingface.co 文件 CDN，相关下载已走 `HF_ENDPOINT=https://hf-mirror.com` 镜像
> （见 `python/dsh_visit/ui_parse/parser.py` 与 `scripts/setup-omniparser.ps1`）。

## 本地环境约定

- 推理后端：`E:\conda\envs\sdenv\python.exe`（Python 3.13 + torch 2.13 + CUDA），可用环境变量 `DSH_VISIT_PYTHON` 覆盖。
- 模型目录：`models/`（L1/L2 权重、YOLO 权重、OmniParser 模型均落于此，自动创建）。
- 数据目录：`data/`（M2 起填充网络真实数据）。
- 路径均可通过 `DSH_VISIT_MODELS_DIR` / `DSH_VISIT_DATA_DIR` 覆盖，见 [.env.example](./.env.example)。
