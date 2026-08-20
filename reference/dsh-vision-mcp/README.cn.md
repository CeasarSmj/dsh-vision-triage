# dsh-vision-mcp

[English](README.md) | 中文

给 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) 用的第一方插件：提供一个 `describe_image` 工具，把图片文件（PNG/JPEG/WebP/GIF）发送给 **Qwen-VL** 视觉模型，返回图片内容的文本描述。

- **零侵入**：按 DSH 标准工具 DSL（`defineTool`）注册，插件加载后模型即可调用
- **密钥安全**：API Key 走 DSH 凭据接缝（`ctx.credentials.resolve('QWEN_VISION_API_KEY')`），**每次调用实时解析**，不写入任何配置文件，轮换密钥无需重启
- **热加载**：通过 `cordis.patch.yml`（用户 patch 层）挂载，DSH 配置级 HMR 即时生效，无需重启宿主

## 兼容性

在 DeepSeek Harness `0.1.0-rc.5`（commit `47f9438`）上开发并验证。

DSH 处于开发者预览阶段，会包含破坏兼容性的更新（见根 README）。本插件只使用了两个长期稳定的扩展点——工具 DSL（`defineTool` / `ctx.tools.register`）与凭据接缝（`ctx.credentials.resolve`）——整个插件生态都依赖它们，因此预计在大多数版本更新后仍可正常工作。DSH 升级后请验证：`describe_image` 工具仍出现在模型工具列表中并能正常回答。

## 安装

### 方式一：让您的 DSH 引导安装（推荐）

您可以把下面的内容发送给您的DSH以让它引导您进行安装：

> 请参考这个文件 https://github.com/CeasarSmj/dsh-vision-mcp/blob/master/docs/INSTALL.md 来安装对应的插件

DSH 会按照 [docs/INSTALL.md](docs/INSTALL.md) 中的步骤自动完成：配置凭据 → 安装插件包 → 挂载配置 → 验证工具。

### 方式二：官方渠道（`dsh plugin` CLI）

仓库发布后，在任何装有 DSH CLI 的机器上：

```sh
# 从 GitHub 安装（自动注册为 bundle 并加入 profile 的 bundles 列表）
dsh plugin --profile <profile-name> add github:CeasarSmj/dsh-vision-mcp

# 或从 npm 安装（发布后）
dsh plugin --profile <profile-name> add dsh-vision-mcp
```

该 bundle 的 `cordis.patch.yml` 会自动插入插件行；新 profile 或重启后生效。

### 方式三：手动（现有运行中的 profile，热生效）

1. 把本包放入 profile 的 `node_modules`（`C:\Users\Administrator\.dsh\profiles\node_modules\dsh-vision-mcp`，目录或 junction 均可）；
2. 在 profile 的 `cordis.patch.yml` 追加：

```yaml
- insert:
    - id: dsh-vision-mcp
      name: dsh-vision-mcp
      config:
        baseUrl: https://dashscope.aliyuncs.com/compatible-mode/v1
        model: qwen-vl-max
```

3. 保存后 DSH 的 HMR 立即加载插件，无需重启。

## 配置

| 项 | 位置 | 说明 |
|---|---|---|
| API Key | DSH 凭据存储（`$DSH_HOME/.credentials.yaml`）或 Settings → Credentials | 键名 **`QWEN_VISION_API_KEY`** |
| `baseUrl` | 插件行 `config.baseUrl` | OpenAI 兼容接口地址，默认 `https://dashscope.aliyuncs.com/compatible-mode/v1`；使用阿里云百炼 MaaS 网关时改成自己的网关地址 |
| `model` | 插件行 `config.model` | 默认 `qwen-vl-max`（可选 `qwen-vl-plus`、`qwen2.5-vl-72b-instruct` 等） |

凭据示例（`$DSH_HOME/.credentials.yaml`）：

```yaml
QWEN_VISION_API_KEY: sk-xxxxxxxx
```

## 工具：`describe_image`

- `file_path`（必填）：图片路径（绝对路径，或相对宿主工作目录）
- `prompt`（可选）：定制关注点（如"提取图中文字"、"描述界面布局"）；缺省为详细描述

模型看到该工具后，任何需要看图的任务（截图、图表、照片、文档页）都会自动调用它。

## 开发

```sh
git clone https://github.com/CeasarSmj/dsh-vision-mcp
cd dsh-vision-mcp
# 无构建步骤：纯 ESM，直接由 DSH loader 加载
```

- `index.js` — 插件本体（`defineTool` 注册 + Qwen-VL 调用）
- `cordis.patch.yml` — bundle 配置层
- `docs/INSTALL.md` — 对话引导安装文档

## License

MIT
