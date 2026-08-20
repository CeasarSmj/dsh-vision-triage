/**
 * ③ detect_natural_image — 内容图像目标检测（本地，YOLO11 / YOLO-World）。
 * COCO 80 类预训练；传 text_prompts 时切换 YOLO-World 开放词汇零样本检测。
 */

import { defineTool } from '@deepseek-ai/dsh-tools'
import { runPython } from '../backend.js'
import { resolveImagePath } from '../shared.js'

export function createDetectNaturalImageTool(config) {
  return defineTool({
    name: 'detect_natural_image',
    description:
      '内容图像目标检测（本地，YOLO11，COCO 80 类）：返回检测到的目标类别、置信度与边框坐标。' +
      '仅用于 classify_image 判定为 content 的图像（照片/插画/CG）；不适用于文本/UI 图像' +
      '（应走 ocr_image / parse_ui_screenshot）。' +
      '开放词汇：需要检测 COCO 之外的类别时传 text_prompts（逗号分隔，如 "person, dog"），' +
      '自动切换 YOLO-World 零样本检测。检测结果不足以回答问题时，改用 describe_image 做语义描述。',
    parameters: {
      file_path: {
        type: 'string',
        required: true,
        description: '图片绝对路径（png/jpg/jpeg/webp/bmp）',
      },
      text_prompts: {
        type: 'string',
        description: '逗号分隔的开放词汇提示（YOLO-World）；缺省使用 COCO 80 类',
      },
      conf_threshold: {
        type: 'number',
        description: '置信度阈值，默认 0.25',
      },
      max_detections: {
        type: 'integer',
        description: '最多返回的检测框数，默认 100',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          count: { type: 'integer', description: '检测框数量' },
          model: { type: 'string', description: '实际使用的模型标识' },
          detections: {
            type: 'array',
            description: '检测框列表',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                label: { type: 'string', description: '目标类别' },
                confidence: { type: 'number', description: '置信度 0~1' },
                bbox: {
                  type: 'array',
                  description: '[x1, y1, x2, y2] 像素坐标（左上/右下）',
                  items: { type: 'number' },
                },
              },
            },
          },
        },
      },
      render: (_args, value) => [{
        type: 'text',
        text: `检测到 ${value.count} 个目标（${value.model}）` +
          (value.detections.length
            ? `：${value.detections.map((d) => `${d.label}(${Math.round(d.confidence * 100)}%)`).join(', ')}`
            : ''),
      }],
    },
    timeoutMs: 120_000,
    async execute(args, exec) {
      const filePath = resolveImagePath(args.file_path)
      const passthrough = []
      if (args.text_prompts) passthrough.push('--text-prompts', args.text_prompts)
      if (args.conf_threshold != null) passthrough.push('--conf', String(args.conf_threshold))
      if (args.max_detections != null) passthrough.push('--max-detections', String(args.max_detections))
      return runPython(config, 'detect-image', ['--input', filePath, ...passthrough], { signal: exec.signal })
    },
  })
}
