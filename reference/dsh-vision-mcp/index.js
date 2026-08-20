/**
 * dsh-vision-mcp — a first-party DeepSeek Harness plugin exposing a
 * `describe_image` tool backed by a Qwen-VL vision model (OpenAI-compatible
 * chat completions).
 *
 * Registered through the standard tool DSL (`defineTool` from
 * `@deepseek-ai/dsh-tools`); the API key is resolved per call through the DSH
 * credential seam (`ctx.credentials.resolve('QWEN_VISION_API_KEY')`), so
 * rotating the key needs no restart and no config edit.
 *
 * Plugin config (cordis.yml row `config`):
 *   - baseUrl: OpenAI-compatible base URL (default: DashScope compatible-mode).
 *   - model:   Qwen-VL model id (default: qwen-vl-max).
 */

import { defineTool } from '@deepseek-ai/dsh-tools'
import { readFileSync, existsSync, statSync } from 'node:fs'
import { extname, resolve } from 'node:path'

export const name = 'dsh-vision-mcp'
export const inject = ['tools', 'credentials']

const IMAGE_MIME = {
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.gif': 'image/gif',
}

const DEFAULT_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
const DEFAULT_MODEL = 'qwen-vl-max'
const DEFAULT_PROMPT = '请详细描述这张图片的内容，包括主体、布局、文字、颜色和细节。'
const CREDENTIAL_REF = 'QWEN_VISION_API_KEY'

export function apply(ctx, config = {}) {
  const baseUrl = String(config.baseUrl || DEFAULT_BASE_URL).replace(/\/+$/, '')
  const model = String(config.model || DEFAULT_MODEL)

  ctx.tools.register(defineTool({
    name: 'describe_image',
    description:
      'Send one image file (PNG/JPEG/WebP/GIF) to a Qwen-VL vision model and return its text description. ' +
      'Use this whenever you need the content of an image (screenshot, chart, photo, document page) as text.',
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

      const credential = await ctx.credentials.resolve(CREDENTIAL_REF)
      if (!credential) {
        throw new Error(
          `${CREDENTIAL_REF} is not configured: add it in Settings → Credentials or to $DSH_HOME/.credentials.yaml`,
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
        throw new Error(`Qwen-VL API ${response.status} ${response.statusText}: ${detail}`)
      }
      const json = await response.json()
      const content = json?.choices?.[0]?.message?.content
      if (typeof content !== 'string' || !content.trim()) {
        throw new Error(`Qwen-VL API returned no text content: ${JSON.stringify(json).slice(0, 500)}`)
      }
      return content.trim()
    },
  }))
}
