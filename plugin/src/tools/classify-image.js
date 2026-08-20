/**
 * ① classify_image — L1 大分类（本地，yolo-classify，毫秒级）。
 * content（内容承载：照片/插画/CG/画作） vs structure（结构承载：文本/表单/UI/网页/文档）。
 */

import { defineTool } from '@deepseek-ai/dsh-tools'
import { callBackend } from '../backend.js'
import { resolveImagePath, renderJson } from '../shared.js'

export function createClassifyImageTool(config) {
  return defineTool({
    name: 'classify_image',
    description:
      'L1 大分类（本地，毫秒级，零云端成本）：判断图片是 content（内容承载：照片/插画/CG/画作/海报主体）' +
      '还是 structure（结构承载：纯文本/表单/软件 UI/网页/文档）。' +
      '推荐作为任何图片任务的第一步：content → detect_natural_image（需要细节/语义时再 describe_image）；' +
      'structure → classify_structure。若返回 degraded=true（置信度 <0.6），结果不可靠，' +
      '请改用 describe_image 交叉验证，避免错误路由。',
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
            enum: ['content', 'structure'],
            description: 'L1 分类结果',
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
        text: `L1 分类: ${value.category}（置信度 ${value.confidence}）` +
          (value.degraded ? ' ⚠ degraded：置信度不足，建议用 describe_image 交叉验证' : ''),
      }],
    },
    timeoutMs: 30_000,
    async execute(args, exec) {
      const filePath = resolveImagePath(args.file_path)
      return callBackend(config, 'classify_image', { input: filePath }, { timeoutMs: 30_000, signal: exec.signal })
    },
  })
}
