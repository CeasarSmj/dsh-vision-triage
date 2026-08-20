/**
 * ② classify_structure — L2 细分（本地，yolo-classify，毫秒级）。
 * 仅在 classify_image 返回 structure 时使用：ui（软件界面）/ text（纯文本）/ form（表单表格）。
 */

import { defineTool } from '@deepseek-ai/dsh-tools'
import { callBackend } from '../backend.js'
import { resolveImagePath, renderJson } from '../shared.js'

export function createClassifyStructureTool(config) {
  return defineTool({
    name: 'classify_structure',
    description:
      'L2 细分（本地，毫秒级，零云端成本）：仅在 classify_image 返回 structure 时使用，' +
      '细分 ui（软件界面/网页）/ text（纯文本/文档页）/ form（表单/表格）。' +
      'ui → parse_ui_screenshot（结构化元素解析）；text/form → ocr_image（文本提取）。' +
      '若返回 degraded=true（置信度 <0.6），结果不可靠，请改用 describe_image 交叉验证。',
    parameters: {
      file_path: {
        type: 'string',
        required: true,
        description: '图片绝对路径（png/jpg/jpeg/webp/bmp）',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          category: {
            type: 'string',
            enum: ['ui', 'text', 'form'],
            description: 'L2 分类结果',
          },
          confidence: {
            type: 'number',
            description: '置信度 0~1；<0.6 视为不可靠',
          },
          degraded: {
            type: 'boolean',
            description: 'true=置信度不足或模型未训练（启发式占位），结果仅供参考，应交叉验证',
          },
          model: {
            type: 'string',
            description: '实际使用的模型标识',
          },
          note: {
            type: 'string',
            description: '补充说明',
          },
        },
      },
      render: (_args, value) => [{
        type: 'text',
        text: `L2 细分: ${value.category}（置信度 ${value.confidence}）` +
          (value.degraded ? ' ⚠ degraded：置信度不足，建议用 describe_image 交叉验证' : ''),
      }],
    },
    timeoutMs: 30_000,
    async execute(args, exec) {
      const filePath = resolveImagePath(args.file_path)
      return callBackend(config, 'classify_structure', { input: filePath }, { timeoutMs: 30_000, signal: exec.signal })
    },
  })
}
