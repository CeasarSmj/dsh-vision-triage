/**
 * ⑥ describe_image — 云端语义追问（多 provider）。
 *
 * 融合自 dsh-vision-mcp（reference/dsh-vision-mcp/index.js），OpenAI 兼容
 * chat/completions 实现，凭据走 DSH 凭据存储。支持两个视觉后端：
 *   - qwen    ：阿里云 DashScope Qwen-VL（QWEN_VISION_API_KEY）
 *   - deepseek（默认）：DeepSeek-V4-Flash-Vision-Exp（DEEPSEEK_API_KEY，
 *                      base_url https://api.deepseek.com，OpenAI 兼容）
 *
 * 插件配置（cordis.patch.yml 行 `config`）：
 *   - provider: 'deepseek' | 'qwen'（默认 deepseek）
 *   - baseUrl / model / apiKeyRef：显式覆盖（优先于 provider 默认值）
 */

import { defineTool } from '@deepseek-ai/dsh-tools'
import { readFileSync, existsSync, statSync } from 'node:fs'
import { extname, resolve } from 'node:path'

const IMAGE_MIME = {
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.gif': 'image/gif',
}

const PROVIDERS = {
  qwen: {
    label: 'Qwen-VL',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    model: 'qwen-vl-max',
    credential: 'QWEN_VISION_API_KEY',
  },
  deepseek: {
    label: 'DeepSeek-V4-Flash-Vision',
    baseUrl: 'https://api.deepseek.com',
    model: 'deepseek-v4-flash-vision-exp',
    credential: 'DEEPSEEK_API_KEY',
  },
}

const DEFAULT_PROMPT = '请详细描述这张图片的内容，包括主体、布局、文字、颜色和细节。'

export function createDescribeImageTool(ctx, config = {}) {
  const providerName = String(config.provider || 'deepseek')
  const provider = PROVIDERS[providerName]
  if (!provider) {
    throw new Error(`describe_image 未知 provider: ${providerName}（支持: ${Object.keys(PROVIDERS).join(', ')}）`)
  }
  const baseUrl = String(config.baseUrl || provider.baseUrl).replace(/\/+$/, '')
  const model = String(config.model || provider.model)
  const credentialRef = String(config.apiKeyRef || provider.credential)

  return defineTool({
    name: 'describe_image',
    description:
      'Send one image file (PNG/JPEG/WebP/GIF) to a cloud vision model and return its text description. ' +
      '云端语义追问，仅在以下场景按需调用：(1) 需要语义理解（如"图里讲的故事/趋势"）；' +
      '(2) 本地分类置信度不足（classify_image/classify_structure 返回 degraded=true，<0.6）需交叉验证；' +
      '(3) 本地工具（detect_natural_image/ocr_image/parse_ui_screenshot）无法覆盖的追问。' +
      '简单/确定的任务（识别文本、数目标、判类型）应先用本地工具，避免云端 token 成本。' +
      `当前后端: ${provider.label}（${model}）。`,
    parameters: {
      file_path: {
        type: 'string',
        required: true,
        description: 'Path of the image file to describe (absolute, or relative to the harness working directory).',
      },
      prompt: {
        type: 'string',
        description: 'Optional instruction controlling what to extract or focus on. Defaults to a detailed description.',
      },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    timeoutMs: 120_000,
    async execute(args, exec) {
      const filePath = resolve(args.file_path)
      if (!existsSync(filePath)) throw new Error(`file not found: ${args.file_path}`)
      if (!statSync(filePath).isFile()) throw new Error(`not a regular file: ${filePath}`)
      const ext = extname(filePath).toLowerCase()
      const mime = IMAGE_MIME[ext]
      if (!mime) {
        throw new Error(`unsupported image extension "${ext || '(none)'}" (supported: png/jpg/jpeg/webp/gif)`)
      }
      const dataUrl = `data:${mime};base64,${readFileSync(filePath).toString('base64')}`

      const credential = await ctx.credentials.resolve(credentialRef)
      if (!credential) {
        throw new Error(
          `${credentialRef} is not configured: add it in Settings → Credentials or to $DSH_HOME/.credentials.yaml`,
        )
      }

      const prompt = typeof args.prompt === 'string' && args.prompt.trim()
        ? args.prompt.trim()
        : DEFAULT_PROMPT

      const response = await fetch(`${baseUrl}/chat/completions`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${credential.value}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model,
          messages: [{
            role: 'user',
            content: [
              { type: 'text', text: prompt },
              { type: 'image_url', image_url: { url: dataUrl } },
            ],
          }],
          max_tokens: 2048,
        }),
        signal: AbortSignal.any([exec.signal, AbortSignal.timeout(120_000)]),
      })
      if (!response.ok) {
        const detail = (await response.text()).slice(0, 2000)
        throw new Error(`${provider.label} API ${response.status} ${response.statusText}: ${detail}`)
      }
      const json = await response.json()
      const content = json?.choices?.[0]?.message?.content
      if (typeof content !== 'string' || !content.trim()) {
        throw new Error(`${provider.label} API returned no text content: ${JSON.stringify(json).slice(0, 500)}`)
      }
      return content.trim()
    },
  })
}
