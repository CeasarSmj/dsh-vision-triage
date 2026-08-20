# dsh-vision-mcp

中文readme参考[README.cn.md](README.cn.md)

A first-party plugin for [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) that provides a `describe_image` tool: send an image file (PNG/JPEG/WebP/GIF) to a **Qwen-VL** vision model and get back a text description of the image content.

- **Zero-intrusion**: registered through the standard DSH tool DSL (`defineTool`) — the model can call it as soon as the plugin loads.
- **Secret-safe**: the API key is resolved per call through the DSH credential seam (`ctx.credentials.resolve('QWEN_VISION_API_KEY')`); it never lives in a config file, and rotating the key needs no restart.
- **Hot-reload**: mounted via `cordis.patch.yml` (the user patch layer); DSH's config-level HMR applies it immediately without restarting the host.

## Compatibility

Developed and verified against DeepSeek Harness `0.1.0-rc.5` (commit `47f9438`).

DSH is in developer preview and ships compatibility-breaking changes (see the root README). This plugin only uses two long-lived extension points — the tool DSL (`defineTool` / `ctx.tools.register`) and the credential seam (`ctx.credentials.resolve`) — which the entire plugin ecosystem depends on, so it is expected to keep working across most updates. After a DSH upgrade, verify: the `describe_image` tool still appears in the model's catalog and answers successfully.

## Installation

### Option 1: Let your DSH guide you (recommended)

Send the following to your DSH and it will walk you through the install:

> Please refer to this file https://github.com/CeasarSmj/dsh-vision-mcp/blob/master/docs/INSTALL.md to install the plugin

Your DSH follows [docs/INSTALL.md](docs/INSTALL.md) automatically: configure the credential → install the package → mount the config → verify the tool.

### Option 2: Official channel (`dsh plugin` CLI)

On any machine with the DSH CLI:

```sh
# Install from GitHub (registers the bundle and appends it to the profile's bundles list)
dsh plugin --profile <profile-name> add github:CeasarSmj/dsh-vision-mcp

# Or from npm (once published)
dsh plugin --profile <profile-name> add dsh-vision-mcp
```

The bundle's `cordis.patch.yml` inserts the plugin row automatically; it takes effect in new profiles or after a restart.

### Option 3: Manual (hot-reload on a running profile)

1. Put this package into the profile's `node_modules` (`C:\Users\Administrator\.dsh\profiles\node_modules\dsh-vision-mcp` — a real directory or a junction both work);
2. Append to the profile's `cordis.patch.yml`:

```yaml
- insert:
    - id: dsh-vision-mcp
      name: dsh-vision-mcp
      config:
        baseUrl: https://dashscope.aliyuncs.com/compatible-mode/v1
        model: qwen-vl-max
```

3. DSH's HMR loads the plugin on save — no restart needed.

## Configuration

| Item | Where | Description |
|---|---|---|
| API key | DSH credential store (`$DSH_HOME/.credentials.yaml`) or Settings → Credentials | Key name **`QWEN_VISION_API_KEY`** |
| `baseUrl` | plugin row `config.baseUrl` | OpenAI-compatible base URL; defaults to `https://dashscope.aliyuncs.com/compatible-mode/v1`. Point it at your own gateway when using Alibaba Cloud Bailian MaaS |
| `model` | plugin row `config.model` | Defaults to `qwen-vl-max` (`qwen-vl-plus`, `qwen2.5-vl-72b-instruct`, … also work) |

Credential example (`$DSH_HOME/.credentials.yaml`):

```yaml
QWEN_VISION_API_KEY: sk-xxxxxxxx
```

## Tool: `describe_image`

- `file_path` (required): path of the image (absolute, or relative to the harness working directory)
- `prompt` (optional): what to focus on (e.g. "extract the text in this image", "describe the UI layout"); defaults to a detailed description

Once the model sees the tool, any task that needs to look at an image (screenshots, charts, photos, document pages) triggers it automatically.

## Development

```sh
git clone https://github.com/CeasarSmj/dsh-vision-mcp
cd dsh-vision-mcp
# No build step: plain ESM, loaded directly by the DSH loader
```

- `index.js` — the plugin itself (`defineTool` registration + Qwen-VL call)
- `cordis.patch.yml` — the bundle config layer
- `docs/INSTALL.md` — the conversation-guided installation doc

## License

MIT
