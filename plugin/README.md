# dsh-vision-triage（插件）

DSH 视觉分诊插件：注册 6 个工具（①~⑥），本地工具经 Python 子进程桥接推理后端。

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
        baseUrl: https://dashscope.aliyuncs.com/compatible-mode/v1
        model: qwen-vl-max
```

## 验证

```powershell
.\scripts\verify-tools.ps1                    # 结构检查（junction/patch 行）
node .\scripts\smoke-register.mjs             # 6 工具注册冒烟测试（不依赖 DSH 运行时）
```

重启 DSH（或等待配置 HMR）后，模型工具目录应出现 6 个工具：
`classify_image` / `classify_structure` / `detect_natural_image` / `parse_ui_screenshot` / `ocr_image` / `describe_image`。

## 配置项（插件 `config`，均有默认值）

| 键 | 默认值 | 说明 |
|---|---|---|
| `python` | `E:\conda\envs\sdenv\python.exe`（或 `DSH_VISIT_PYTHON`） | 本地推理解释器 |
| `modelsDir` | `<项目根>/models`（或 `DSH_VISIT_MODELS_DIR`） | 模型目录 |
| `dataDir` | `<项目根>/data`（或 `DSH_VISIT_DATA_DIR`） | 数据集目录 |
| `baseUrl` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | describe_image 网关 |
| `model` | `qwen-vl-max` | describe_image 模型 |

`describe_image` 需要凭据 `QWEN_VISION_API_KEY`（DSH Settings → Credentials，或 `$DSH_HOME/.credentials.yaml`）。

## 目录

```
index.js           插件入口（注册 6 工具）
cordis.patch.yml   bundle patch（挂载行）
src/backend.js     Python 子进程桥
src/shared.js      路径校验/渲染辅助
src/describe-image.js   ⑥ 云端（融合自 dsh-vision-mcp）
src/tools/         ①~⑤ 本地工具定义
```
