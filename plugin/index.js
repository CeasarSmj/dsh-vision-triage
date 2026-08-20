/**
 * dsh-vision-triage — DSH 视觉分诊插件入口。
 *
 * 注册 6 个工具（验收标准 §5-1）：
 *   ① classify_image          L1 大分类 content vs structure（本地，yolo-classify）
 *   ② classify_structure      L2 细分 ui / text / form（本地，yolo-classify）
 *   ③ detect_natural_image    内容图像目标检测（本地，YOLO11 / YOLO-World）
 *   ④ parse_ui_screenshot     UI 结构化解析（本地，OmniParser v2）
 *   ⑤ ocr_image               OCR 文本提取（本地，RapidOCR）
 *   ⑥ describe_image          云端 Qwen-VL 语义追问（按需，融合自 dsh-vision-mcp）
 *
 * 插件配置（cordis.patch.yml 行 `config`，均有默认值）：
 *   - python:    本地推理 Python 解释器（默认 E:\conda\envs\sdenv\python.exe，
 *                环境变量 DSH_VISIT_PYTHON 优先）
 *   - modelsDir: 模型目录（默认 <项目根>/models）
 *   - dataDir:   数据集目录（默认 <项目根>/data）
 *   - baseUrl / model: describe_image 的云端网关与模型
 */

import { createClassifyImageTool } from './src/tools/classify-image.js'
import { createClassifyStructureTool } from './src/tools/classify-structure.js'
import { createDetectNaturalImageTool } from './src/tools/detect-natural-image.js'
import { createParseUiScreenshotTool } from './src/tools/parse-ui-screenshot.js'
import { createOcrImageTool } from './src/tools/ocr-image.js'
import { createDescribeImageTool } from './src/describe-image.js'

export const name = 'dsh-vision-triage'
export const inject = ['tools', 'credentials']

const DEFAULT_CONFIG = {
  python: process.env.DSH_VISIT_PYTHON || 'E:\\conda\\envs\\sdenv\\python.exe',
  modelsDir: process.env.DSH_VISIT_MODELS_DIR || undefined,
  dataDir: process.env.DSH_VISIT_DATA_DIR || undefined,
}

export function apply(ctx, config = {}) {
  const cfg = { ...DEFAULT_CONFIG, ...config }

  // 本地工具（桥接 Python 后端）
  for (const tool of [
    createClassifyImageTool(cfg),
    createClassifyStructureTool(cfg),
    createDetectNaturalImageTool(cfg),
    createParseUiScreenshotTool(cfg),
    createOcrImageTool(cfg),
  ]) {
    ctx.tools.register(tool)
  }

  // 云端工具（需要 credentials 注入）
  ctx.tools.register(createDescribeImageTool(ctx, cfg))
}
