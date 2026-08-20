/**
 * ④ parse_ui_screenshot — UI 结构化解析（本地，OmniParser v2，常驻后端）。
 * 返回 UI 元素（类型/文本/边框/语义描述）。首次调用加载约 1.1GB 模型（15-25s），
 * 之后常驻后端缓存，秒级响应；可用 manage_vision_backend release 释放。
 */

import { defineTool } from '@deepseek-ai/dsh-tools'
import { callBackend } from '../backend.js'
import { resolveImagePath } from '../shared.js'

export function createParseUiScreenshotTool(config) {
  return defineTool({
    name: 'parse_ui_screenshot',
    description:
      'UI 结构化解析（本地，OmniParser v2）：返回截图的 UI 元素列表——类型（按钮/输入框/图片等）、' +
      '文本、边框坐标、Florence-2 语义描述。' +
      '仅在 classify_structure 判定为 ui 的截图使用。内嵌图片会被识别为元素并附带语义描述，无需单独分类。' +
      '注意：首次运行需下载模型（约 1.3GB）并加载 15-25s；未就绪时返回 { status: "not_ready" } 与安装指引。' +
      '元素结构不足以回答问题时，改用 describe_image 做语义追问。',
    parameters: {
      file_path: {
        type: 'string',
        required: true,
        description: '截图绝对路径（png/jpg/jpeg/webp/bmp）',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          status: { type: 'string', enum: ['ok', 'not_ready', 'error'], description: '解析状态' },
          element_count: { type: 'integer', description: '元素数量（status=ok 时）' },
          elements: {
            type: 'array',
            description: 'UI 元素列表',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                type: { type: 'string', description: '元素类型（button/input/image/text/icon 等）' },
                text: { type: 'string', description: '元素内文本（可能为空）' },
                bbox: {
                  type: 'array',
                  description: '[x1, y1, x2, y2] 像素坐标',
                  items: { type: 'number' },
                },
                description: { type: 'string', description: 'Florence-2 语义描述（图片类元素）' },
              },
            },
          },
          texts: { type: 'array', description: '截图中识别出的全部文本', items: { type: 'string' } },
          inverted: { type: 'boolean', description: '深色 UI 是否已自动反色预处理（ADR-15）' },
          message: { type: 'string', description: 'not_ready/error 时的说明' },
        },
      },
      render: (_args, value) => [{
        type: 'text',
        text: value.status === 'ok'
          ? `解析出 ${value.element_count} 个 UI 元素；文本 ${value.texts.length} 条。`
          : `UI 解析未就绪：${value.message || value.status}`,
      }],
    },
    timeoutMs: 360_000,
    async execute(args, exec) {
      const filePath = resolveImagePath(args.file_path)
      return callBackend(config, 'parse_ui', { input: filePath }, { timeoutMs: 360_000, signal: exec.signal })
    },
  })
}
