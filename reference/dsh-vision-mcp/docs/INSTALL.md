# dsh-vision-mcp 对话引导安装

> 本文件供 DSH（DeepSeek Harness）代理阅读并执行。用户把下面这句话发给 DSH 即可触发引导：
>
> **"请参考这个文件 https://github.com/CeasarSmj/dsh-vision-mcp/blob/master/docs/INSTALL.md 来安装对应的插件"**

## 目标

在目标机器上安装 `dsh-vision-mcp` 插件，使模型获得 `describe_image` 工具（Qwen-VL 识图）。

## 前置条件

1. DeepSeek Harness 正在运行（Web GUI 或 CLI）；
2. 有一个可用的 Qwen-VL API Key（阿里云百炼 DashScope，或兼容的 OpenAI 兼容网关）；
3. 若使用阿里云百炼 MaaS 网关（非官方域名），请准备好网关的 Base URL。

## 步骤 1：写入凭据

把 API Key 写入 DSH 凭据存储。文件位置：`$DSH_HOME/.credentials.yaml`（默认 `C:\Users\<用户名>\.dsh\.credentials.yaml`）。

追加一行（不要覆盖已有内容）：

```yaml
QWEN_VISION_API_KEY: sk-你的密钥
```

> 凭据存储由 DSH 热监听：写入后无需重启即可生效。也可以在 Web GUI 的 Settings → Credentials 里添加。

## 步骤 2：安装插件包

把插件包放入当前 profile 的 `node_modules`。包名 `dsh-vision-mcp`，内容即本仓库（`index.js` + `cordis.patch.yml` + `package.json`）。

任选其一：

- **从 GitHub 克隆后链接**（推荐，无需 npm registry）：
  ```sh
  git clone https://github.com/CeasarSmj/dsh-vision-mcp <临时目录>
  # 在 profile 的 node_modules 下创建 junction 指向该目录：
  #   Windows:  New-Item -ItemType Junction -Path "$DSH_HOME\profiles\<profile>\node_modules\dsh-vision-mcp" -Target "<临时目录>"
  ```
- **官方 CLI**（仓库发布后）：`dsh plugin --profile <profile> add github:CeasarSmj/dsh-vision-mcp`
- **npm**（发布后）：`dsh plugin --profile <profile> add dsh-vision-mcp`

## 步骤 3：挂载插件行

编辑 profile 的 `cordis.patch.yml`（`$DSH_HOME/profiles/<profile>/cordis.patch.yml`），在数组末尾追加：

```yaml
- insert:
    - id: dsh-vision-mcp
      name: dsh-vision-mcp
      config:
        baseUrl: https://dashscope.aliyuncs.com/compatible-mode/v1
        model: qwen-vl-max
```

- 使用阿里云百炼 MaaS 网关时，把 `baseUrl` 换成网关地址（如 `https://llm-xxx.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`）；
- 保存文件即可：DSH 对 `cordis.patch.yml` 有配置级 HMR，**无需重启宿主**。

## 步骤 4：验证

1. 向当前会话发送任意消息（让下一轮请求带上新工具目录）；
2. 调用 `describe_image`，参数 `file_path` 指向一张本地图片；
3. 确认返回图片内容的文本描述。

## 故障排查

| 症状 | 原因 | 处理 |
|---|---|---|
| 工具未出现 | patch 行未生效 / 包未解析 | 确认 junction/包存在于 profile 的 node_modules；确认 `cordis.patch.yml` 语法正确 |
| 报错 `QWEN_VISION_API_KEY is not configured` | 凭据缺失 | 检查 `.credentials.yaml` 键名拼写，或 Settings → Credentials |
| 报错 `Qwen-VL API 4xx` | Key 与网关不匹配 | 确认 `baseUrl` 与 Key 属于同一服务商/工作空间 |
| 报错 `unsupported image extension` | 格式不支持 | 仅支持 png/jpg/jpeg/webp/gif |
