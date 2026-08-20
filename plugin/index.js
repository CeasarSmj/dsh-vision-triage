/**
 * dsh-vision-triage — DSH 视觉分诊插件入口。
 *
 * 注册 7 个工具：
 *   ① classify_image          L1 大分类 content vs structure（本地，yolo-classify，常驻后端）
 *   ② classify_structure      L2 细分 ui / text / form（本地，yolo-classify，常驻后端）
 *   ③ detect_natural_image    内容图像目标检测（本地，YOLO11 / YOLO-World，常驻后端）
 *   ④ parse_ui_screenshot     UI 结构化解析（本地，OmniParser v2，常驻后端）
 *   ⑤ ocr_image               OCR 文本提取 + 表格识别（本地，RapidOCR，常驻后端）
 *   ⑥ describe_image          云端 Qwen-VL 语义追问（按需，融合自 dsh-vision-mcp）
 *   ⑦ manage_vision_backend   常驻后端生命周期管理（status / release 释放 GPU / restart）
 *
 * 常驻后端：本地工具经 `spawn python -m dsh_visit daemon` 常驻进程 + 行式 JSON-RPC 调用，
 * 模型进程内缓存（parse-ui 首次 15-25s，之后秒级）；插件 dispose（DSH 关闭）自动关闭
 * 常驻进程归还 GPU，崩溃后下次调用自动重启。
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
import { createManageVisionBackendTool } from './src/tools/manage-vision-backend.js'
import { createDescribeImageTool } from './src/describe-image.js'
import { releaseDaemon } from './src/backend.js'

export const name = 'dsh-vision-triage'
export const inject = ['tools', 'credentials']

const DEFAULT_CONFIG = {
  python: process.env.DSH_VISIT_PYTHON || 'E:\\conda\\envs\\sdenv\\python.exe',
  modelsDir: process.env.DSH_VISIT_MODELS_DIR || undefined,
  dataDir: process.env.DSH_VISIT_DATA_DIR || undefined,
}

export function apply(ctx, config = {}) {
  const cfg = { ...DEFAULT_CONFIG, ...config }

  // 本地工具（常驻 Python 后端 RPC）
  for (const tool of [
    createClassifyImageTool(cfg),
    createClassifyStructureTool(cfg),
    createDetectNaturalImageTool(cfg),
    createParseUiScreenshotTool(cfg),
    createOcrImageTool(cfg),
    createManageVisionBackendTool(cfg),
  ]) {
    ctx.tools.register(tool)
  }

  // 云端工具（需要 credentials 注入）
  ctx.tools.register(createDescribeImageTool(ctx, cfg))

  // 插件卸载（DSH 关闭/重载）时关闭常驻后端，避免僵尸进程占用 GPU（cordis effect 约定）
  return () => {
    releaseDaemon(cfg).catch(() => {})
  }
}
