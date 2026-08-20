/**
 * 工具输出 schema 真实验证：注册全部工具，用真实 execute 结果（含边界 case）
 * 跑 DSH 框架的 validateJsonSchemaValue，确保输出不再被拒。
 *
 * 边界 case（本轮修复）：
 *   - ocr_image with_table=false → table 为 null
 *   - manage_vision_backend status 未运行时 → process/backend/models/gpu 为 null
 *   - manage_vision_backend release → was_running/clean_exit
 *
 * 用法：node scripts/smoke-output-schema.mjs
 */

import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { apply } from '../plugin/index.js'

// 以 plugin 目录为基准解析 @deepseek-ai/dsh-tools（依赖 junction 在 plugin/node_modules）
const require = createRequire(resolve(dirname(fileURLToPath(import.meta.url)), '../plugin/index.js'))
const { validateJsonSchemaValue } = require('@deepseek-ai/dsh-tools')

const defs = []
const ctx = {
  tools: { register: (d) => defs.push(d) },
  credentials: { resolve: async () => ({ value: 'smoke-test-key' }) },
}
apply(ctx, {})
const byName = new Map(defs.map((d) => [d.name, d]))
const signal = new AbortController().signal

const UI_IMG = 'D:/temple/dsh-vision-triage/python/tests/.smoke-tmp/ui_screenshot.png'
const TABLE_IMG = 'D:/temple/dsh-vision-triage/python/tests/.smoke-tmp/table_test.png'

let failures = 0
const check = (cond, label, detail = '') => {
  console.log(`  [${cond ? 'PASS' : 'FAIL'}] ${label} ${detail}`)
  if (!cond) failures++
}

async function validateTool(name, value, label) {
  const def = byName.get(name)
  check(def !== undefined, `工具存在: ${name}`)
  const violations = validateJsonSchemaValue(def.output.schema, value)
  check(violations.length === 0, `输出通过校验: ${label}`, violations.join('; ').slice(0, 200))
}

// ---- 边界 case（无需真实后端）----
console.log('== 边界 case（schema 直接校验）==')
// ocr table=null（手工构造，等价后端 with_table=false 返回）
await validateTool('ocr_image', {
  status: 'ok', text: 'hello', lines: [], table: null,
}, 'ocr with_table=false（table=null）')
// manage status 未运行（nulls）
await validateTool('manage_vision_backend', {
  action: 'status', running: false, process: null, backend: null, models: null, gpu: null,
}, 'manage status 未运行（null 字段）')
// manage release（was_running / clean_exit）
await validateTool('manage_vision_backend', {
  action: 'release', running: false, released: true, was_running: true, clean_exit: true,
}, 'manage release')
// manage restart
await validateTool('manage_vision_backend', {
  action: 'restart', running: true, restarted: true, was_running: true,
}, 'manage restart')

// ---- 真实 execute（拉起常驻后端）----
console.log('== 真实 execute ==')
await validateTool('classify_image',
  await byName.get('classify_image').execute({ file_path: UI_IMG }, { signal }), 'classify_image')
await validateTool('classify_structure',
  await byName.get('classify_structure').execute({ file_path: UI_IMG }, { signal }), 'classify_structure')
await validateTool('detect_natural_image',
  await byName.get('detect_natural_image').execute({ file_path: UI_IMG }, { signal }), 'detect_natural_image')
await validateTool('ocr_image',
  await byName.get('ocr_image').execute({ file_path: UI_IMG, with_table: false }, { signal }), 'ocr with_table=false（真实）')
await validateTool('ocr_image',
  await byName.get('ocr_image').execute({ file_path: TABLE_IMG, with_table: true }, { signal }), 'ocr with_table=true（真实）')
await validateTool('manage_vision_backend',
  await byName.get('manage_vision_backend').execute({ action: 'status' }, { signal }), 'manage status（运行中，真实）')
await validateTool('manage_vision_backend',
  await byName.get('manage_vision_backend').execute({ action: 'release' }, { signal }), 'manage release（真实）')
await validateTool('manage_vision_backend',
  await byName.get('manage_vision_backend').execute({ action: 'status' }, { signal }), 'manage status（释放后，真实）')

console.log(failures === 0 ? '\n全部通过：所有工具输出通过 DSH 框架校验。' : `\n${failures} 项失败。`)
process.exit(failures === 0 ? 0 : 1)
