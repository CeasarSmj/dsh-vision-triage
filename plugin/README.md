# dsh-vision-triage（插件）

DSH 视觉分诊插件：注册 7 个工具（①~⑦），本地工具经 Python 常驻后端（daemon + RPC）执行。

## 与多模态主模型的协作（重要）

**DeepSeek V4 Flash 的纯文本与多模态定价相同**（视觉模型 `deepseek-v4-flash-vision-exp`
与 `v4-flash` 同价，见 [DeepSeek 定价](https://api-docs.deepseek.com/quick_start/pricing/)）。
因此：

- **若 DSH 主模型本身是多模态**（如把主模型配为 `deepseek-v4-flash-vision-exp`），
  图片可直接作为对话输入由主模型自行处理——**无需再调用 `describe_image` 中转**。
  好处：少一层工具调用与延迟，成本与纯文本相同，主模型上下文更连贯。
- **`describe_image` 的定位**变为兜底/专用渠道：
  1. 主模型不是多模态时，作为图片语义理解的云端渠道；
  2. 需要独立凭据/独立后端（如 qwen-vl）或专门的追问场景；
  3. 主模型对图片细节/多次追问时避免占用主上下文。
- **精细操作（UI 元素定位 / 坐标 / 点击目标）→ 优先 `parse_ui_screenshot`（OmniParser）**：
  多模态模型对"文字类元素"定位尚可（实测按钮/标题偏差 <3pp），
  但对"区域/卡片类"目标会报成文字那一小块（实测偏差 15-20pp）。
  OmniParser 返回元素级检测框（类型/文本/坐标/语义描述），是可靠的 ground truth。

一句话：**看图靠主模型，精细定位靠 OmniParser，`describe_image` 是兜底**。

## 安装（junction 方式，与 dsh-vision-mcp 相同）

```powershell
# 在项目根执行（自动创建 junction + 追加 cordis.patch.yml 行）
.\scripts\install-plugin.ps1 -Profile web
```

安装脚本做三件事：

1. `$DSH_HOME/profiles/<profile>/node_modules/dsh-vision-triage` → junction → 本项目 `plugin/` 目录；
2. 插件目录内 `node_modules` → junction → `$DSH_HOME/profiles/node_modules`（解析 `@deepseek-ai/dsh-tools`，
   见需求文档 §4.3-5）；
3. 在 profile 的 `cordis.patch.yml` 追加挂载行（已存在则跳过）：

```yaml
- insert:
    - id: dsh-vision-triage
      name: dsh-vision-triage
      config:
        provider: deepseek
```

## 验证

```powershell
.\scripts\verify-tools.ps1                    # 结构检查（junction/patch 行）
node .\scripts\smoke-register.mjs             # 7 工具注册冒烟测试（不依赖 DSH 运行时）
node .\scripts\smoke-bridge.mjs <图片路径>     # 桥接链路冒烟（真实执行本地工具）
```

重启 DSH（或等待配置 HMR）后，模型工具目录应出现 7 个工具：
`classify_image` / `classify_structure` / `detect_natural_image` / `parse_ui_screenshot` /
`ocr_image` / `manage_vision_backend` / `describe_image`。

## 配置项（插件 `config`，均有默认值）

| 键 | 默认值 | 说明 |
|---|---|---|
| `python` | `E:\conda\envs\sdenv\python.exe`（或 `DSH_VISIT_PYTHON`） | 本地推理解释器 |
| `modelsDir` | `<项目根>/models`（或 `DSH_VISIT_MODELS_DIR`） | 模型目录 |
| `dataDir` | `<项目根>/data`（或 `DSH_VISIT_DATA_DIR`） | 数据集目录 |
| `provider` | `deepseek` | describe_image 后端：`deepseek` / `qwen` |
| `baseUrl` | provider 默认（deepseek: `https://api.deepseek.com`） | describe_image 网关（显式覆盖） |
| `model` | provider 默认（deepseek: `deepseek-v4-flash-vision-exp`） | describe_image 模型（显式覆盖） |
| `apiKeyRef` | provider 默认（deepseek: `DEEPSEEK_API_KEY`） | 凭据名（显式覆盖） |

`describe_image` 凭据：`DEEPSEEK_API_KEY`（默认）/ `QWEN_VISION_API_KEY`（qwen 时），
见 DSH Settings → Credentials 或 `$DSH_HOME/.credentials.yaml`。

## 目录

```
index.js           插件入口（注册 7 工具）
cordis.patch.yml   bundle patch（挂载行）
src/backend.js     常驻后端桥（daemon + 行式 JSON-RPC）
src/shared.js      路径校验/渲染辅助
src/describe-image.js   ⑥ 云端（多 provider：deepseek/qwen）
src/tools/         ①~⑤ 本地工具 + ⑦ manage_vision_backend
```
