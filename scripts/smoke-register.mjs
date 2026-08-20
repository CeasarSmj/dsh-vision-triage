/**
 * 6 工具注册冒烟测试（不依赖 DSH 运行时，不修改 live profile）。
 *
 * 前置：plugin/node_modules junction 已指向共享模块
 *       （运行 install-plugin.ps1 或手动创建，见 README）。
 *
 * 用法：node scripts/smoke-register.mjs
 *
 * 说明：defineTool 在创建定义时即编译/校验参数与输出 schema，
 *       因此"成功注册 6 个工具"同时验证了所有 schema 结构合法。
 */

import { apply, name } from '../plugin/index.js'

const registered = []
const ctx = {
  tools: {
    register: (definition) => registered.push(definition),
  },
  credentials: {
    resolve: async () => ({ value: 'smoke-test-key' }),
  },
}

apply(ctx, {})

const expected = [
  'classify_image',
  'classify_structure',
  'detect_natural_image',
  'parse_ui_screenshot',
  'ocr_image',
  'describe_image',
]

let failures = 0
const check = (cond, label, detail = '') => {
  console.log(`  [${cond ? 'PASS' : 'FAIL'}] ${label} ${detail}`)
  if (!cond) failures++
}

console.log(`== 插件名: ${name} ==`)
check(registered.length === expected.length, '注册工具数 = 6', `实际 ${registered.length}`)

const byName = new Map(registered.map((d) => [d.name, d]))
for (const n of expected) {
  check(byName.has(n), `工具存在: ${n}`)
}

// 结构抽查：每个工具都有参数/输出/执行体
for (const d of registered) {
  check(d.parameters && typeof d.parameters === 'object', `${d.name} 参数 schema`)
  check(d.output?.schema && typeof d.output.schema === 'object', `${d.name} 输出 schema`)
  check(typeof d.execute === 'function', `${d.name} execute`)
  check(Number.isFinite(d.timeoutMs) && d.timeoutMs > 0, `${d.name} timeoutMs`, `=${d.timeoutMs}`)
  check(typeof d.description === 'string' && d.description.length > 40, `${d.name} description 足够详细`, `(${d.description.length} chars)`)
}

console.log(failures === 0 ? '\n全部通过：6 个工具可注册。' : `\n${failures} 项失败。`)
process.exit(failures === 0 ? 0 : 1)
