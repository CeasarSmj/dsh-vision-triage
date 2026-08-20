# 工具契约（6 个工具）

> 对应 [项目需求.md](../项目需求.md) §3.3。这里定义每个工具的：模型可见描述（description 的核心内容）、
> 参数、规范输出（canonical JSON）、推荐使用流程与回退策略。
> **编排原则**：由 LLM 依据 description 自主组装，不做固定程序化编排。

## 路由总览

```
classify_image (L1) ──content──► detect_natural_image（需要细节/语义时 → describe_image）
        │
        └──structure──► classify_structure (L2) ──ui──► parse_ui_screenshot
                                              └─text/form─► ocr_image
置信度 < 0.6（degraded=true）的任何环节 → describe_image 交叉验证
```

---

## ① classify_image — L1 大分类（本地，毫秒级）

- **职责**：判断图像是 `content`（内容承载：照片/插画/CG/画作）还是 `structure`（结构承载：文本/表单/UI/网页/文档）。
- **推荐流程**：任何图片任务的第一步。`content` → `detect_natural_image`（需要细节/语义时再 `describe_image`）；
  `structure` → `classify_structure`。
- **回退**：`confidence < 0.6` 时 `degraded: true`，结果不可靠，改用 `describe_image` 交叉验证。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file_path` | string | ✅ | 图片绝对路径（png/jpg/jpeg/webp） |

**输出**：

```json
{ "category": "content", "confidence": 0.93, "degraded": false,
  "model": "l1.pt", "note": "..." }
```

## ② classify_structure — L2 细分（本地，毫秒级）

- **职责**：仅在 `classify_image` 返回 `structure` 时使用，细分 `ui`（软件界面）/ `text`（纯文本）/ `form`（表单表格）。
- **推荐流程**：`ui` → `parse_ui_screenshot`；`text` / `form` → `ocr_image`。
- **回退**：`confidence < 0.6` 时 `degraded: true`，改用 `describe_image` 交叉验证。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file_path` | string | ✅ | 图片绝对路径 |

**输出**：同上结构，`category ∈ {ui, text, form}`，`model: "l2.pt"`。

## ③ detect_natural_image — 内容图像目标检测（本地，YOLO11）

- **职责**：对 `content` 类图像做目标检测（COCO 80 类，YOLO11）。返回目标类别、置信度、边框。
- **推荐流程**：仅用于 `classify_image` 判定为 `content` 的图像。不适用于文本/UI 图像
  （应走 OCR / OmniParser）。
- **开放词汇**：传入 `text_prompts` 时切换 YOLO-World 零样本检测（任意文本提示，如
  `text_prompts: "person, dog"`）；不传则用 COCO 预训练 YOLO11。
- **回退**：检测数过少或置信度普遍偏低时，改用 `describe_image` 做语义描述。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file_path` | string | ✅ | 图片绝对路径 |
| `text_prompts` | string | - | 逗号分隔的开放词汇提示（YOLO-World）；缺省用 COCO 80 类 |
| `conf_threshold` | number | - | 置信度阈值，默认 0.25 |
| `max_detections` | integer | - | 最多返回的检测框数，默认 100 |

**输出**：

```json
{ "count": 2, "model": "yolo11n.pt",
  "detections": [
    { "label": "person", "confidence": 0.91, "bbox": [10, 20, 300, 600] },
    { "label": "dog", "confidence": 0.85, "bbox": [120, 400, 260, 520] }
  ] }
```

## ④ parse_ui_screenshot — UI 结构化解析（本地，OmniParser v2）

- **职责**：对 `classify_structure` 判定为 `ui` 的截图做结构化解析，返回元素/布局/文本
  （YOLO 检测 UI 元素 + Florence-2 生成语义描述 + OCR 提取文本）。
- **推荐流程**：仅在 L2 判定为 `ui` 后调用；内嵌图片会被识别为元素并附带语义描述，无需再单独分类。
- **注意**：首次运行需下载模型（约 1.1GB）并加载 15-25s；未就绪时返回 `{ status: "not_ready" }`。
  安装与修补见 `scripts/setup-omniparser.ps1`（含 paddle 裁剪、空 OCR 修补、Florence-2 remote code 修补）。
- **回退**：元素结构不足以回答问题时，改用 `describe_image` 做语义追问。
- **实测**（合成中文 UI 截图 1024x768）：OCR 识别 13 段中文文本 + YOLO 12 图标 + Florence-2 语义描述，
  共 25 个元素；元素含 `type: text|icon`、像素 bbox、语义 description。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file_path` | string | ✅ | 截图绝对路径 |

**输出**：

```json
{ "status": "ok", "element_count": 12,
  "elements": [
    { "type": "button", "text": "登录", "bbox": [x1,y1,x2,y2], "description": "..." }
  ],
  "texts": ["登录", "用户名"] }
```

## ⑤ ocr_image — OCR 文本提取（本地，RapidOCR + 表格识别）

- **职责**：提取图片中全部文本行；`with_table=true` 时叠加表格结构识别（RapidAI
  TableStructureRec / SLANet+，输出 HTML 表格）。
- **推荐流程**：用于 `classify_structure` 判定为 `text` / `form` 的图像；对 UI 截图优先用
  `parse_ui_screenshot`（布局信息更全），而非直接 OCR。**表单/表格截图建议传 `with_table: true`**
  以获得结构化表格（HTML + 单元格数）。
- **回退**：识别文本过少或置信度低（如手写体、艺术字）时，改用 `describe_image`；
  表格识别失败时 `table.error` 携带原因，`text`/`lines` 仍可用。
- **实测**（合成中文 3x4 表格）：HTML 行列结构正确（表头 + 3 数据行），单元格内容
  （张三/28/北京…）准确填入，识别约 0.2s；SLANet+ 模型首次从 modelscope 自动下载。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file_path` | string | ✅ | 图片绝对路径 |
| `with_table` | boolean | - | 是否做表格结构识别，默认 false |

**输出**：

```json
{ "status": "ok", "text": "第一行\n第二行",
  "lines": [ { "text": "第一行", "confidence": 0.98, "bbox": [x1,y1,x2,y2] } ],
  "table": { "html": "<html><body><table>…</table></body></html>",
             "cell_count": 14, "elapse": 0.2 } }
```

## ⑥ describe_image — 云端语义追问（Qwen-VL，按需）

- **职责**：把图片发给云端 Qwen-VL 多模态模型，返回文本描述/回答。融合自
  [dsh-vision-mcp](https://github.com/CeasarSmj/dsh-vision-mcp)。
- **推荐流程**：**仅在以下场景调用**——
  1. 需要语义理解（"这张图讲什么故事"、"图表说明了什么趋势"）；
  2. 本地分类置信度不足（`degraded: true`）需交叉验证；
  3. 本地工具无法覆盖的追问。
  简单/确定的任务（识别文本、数目标、判类型）先用本地工具，避免云端 token 成本。
- **凭据**：`QWEN_VISION_API_KEY`（DSH 凭据存储，`Settings → Credentials` 或 `.credentials.yaml`）。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file_path` | string | ✅ | 图片绝对路径 |
| `prompt` | string | - | 追问指令；缺省为详细描述 |

**输出**：string（模型文本回答）。

---

## 契约一致性

- 所有工具经 `defineTool`（`@deepseek-ai/dsh-tools`）注册：参数按 `ParameterSchemaSpec` 校验，
  输出按 `ValueSchemaSpec` 校验，非法输出视为失败（`isError`）。
- 本地工具的输出 schema 与 Python 端 CLI 返回的 JSON 严格对应（字段名/类型一致），
  见 [architecture.md](./architecture.md) §6 桥接协议。
- 6 个工具注册后即出现在 DSH 模型工具目录（验收标准 §5-1）。
