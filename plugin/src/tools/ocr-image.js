/**
 * ⑤ ocr_image — OCR 文本提取（本地，RapidOCR）。
 * 返回全部文本与逐行识别结果；可选表格结构识别（M3 起）。
 */

import { defineTool } from '@deepseek-ai/dsh-tools'
import { callBackend } from '../backend.js'
import { resolveImagePath } from '../shared.js'

export function createOcrImageTool(config) {
  return defineTool({
    name: 'ocr_image',
    description:
      'OCR 文本提取（本地，RapidOCR，零云端成本）：返回图片中全部文本行（内容 + 置信度 + 位置）。' +
      '用于 classify_structure 判定为 text/form 的图像（纯文本截图、文档页、表单表格）。' +
      '对 UI 截图应优先用 parse_ui_screenshot（布局信息更全），而非直接 OCR。' +
      '表单/表格截图建议传 with_table=true 获得结构化表格（HTML + 单元格数）。' +
      '识别文本过少或置信度低（如手写体、艺术字）时，改用 describe_image 做语义识别。',
    parameters: {
      file_path: {
        type: 'string',
        required: true,
        description: '图片绝对路径（png/jpg/jpeg/webp/bmp）',
      },
      with_table: {
        type: 'boolean',
        description: '是否做表格结构识别（RapidAI TableStructureRec/SLANet+），默认 false',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          status: { type: 'string', enum: ['ok', 'error'], description: '识别状态' },
          text: { type: 'string', description: '全部文本（行间用换行分隔）' },
          lines: {
            type: 'array',
            description: '逐行识别结果',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                text: { type: 'string', description: '行文本' },
                confidence: { type: 'number', description: '置信度 0~1' },
                bbox: {
                  type: 'array',
                  description: '[x1, y1, x2, y2] 像素坐标',
                  items: { type: 'number' },
                },
              },
            },
          },
          table: { type: 'object', additionalProperties: true, description: '表格结构识别结果（with_table=true 且可用时）' },
          message: { type: 'string', description: '错误说明' },
        },
      },
      render: (_args, value) => [{
        type: 'text',
        text: value.status === 'ok'
          ? `OCR 识别 ${value.lines.length} 行文本：\n${value.text}`
          : `OCR 失败：${value.message || '未知错误'}`,
      }],
    },
    timeoutMs: 120_000,
    async execute(args, exec) {
      const filePath = resolveImagePath(args.file_path)
      return callBackend(config, 'ocr', { input: filePath, with_table: !!args.with_table }, { timeoutMs: 120_000, signal: exec.signal })
    },
  })
}
