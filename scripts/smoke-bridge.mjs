/**
 * 插件桥接链路冒烟测试：真实执行本地工具的 execute（Node → Python 子进程 → JSON）。
 *
 * 前置：plugin/node_modules junction 已指向共享模块；Python 后端可运行。
 * 用法：node scripts/smoke-bridge.mjs <图片路径>
 *
 * 覆盖：classify_image / classify_structure / parse_ui_screenshot
 *       （detect/ocr 依赖联网或首次下载，见 python/tests/smoke_cli.py）
 */

import { apply } from '../plugin/index.js'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'

const imgArg = process.argv[2]
if (!imgArg || !existsSync(resolve(imgArg))) {
  console.error('用法: node scripts/smoke-bridge.mjs <图片路径>')
  process.exit(2)
}
const img = resolve(imgArg)

const defs = []
const ctx = {
  tools: { register: (d) => defs.push(d) },
  credentials: { resolve: async () => ({ value: 'smoke-test-key' }) },
}
apply(ctx, {})
const byName = new Map(defs.map((d) => [d.name, d]))
const signal = new AbortController().signal

let failures = 0
const check = (cond, label, detail = '') => {
  console.log(`  [${cond ? 'PASS' : 'FAIL'}] ${label} ${detail}`)
  if (!cond) failures++
}

for (const name of ['classify_image', 'classify_structure', 'parse_ui_screenshot']) {
  try {
    const value = await byName.get(name).execute({ file_path: img }, { signal })
    console.log(`  ${name} => ${JSON.stringify(value)}`)
    check(value && typeof value === 'object', `${name} 返回对象`)
  } catch (err) {
    check(false, `${name} 执行`, String(err.message))
  }
}

console.log(failures === 0 ? '\n桥接链路通过。' : `\n${failures} 项失败。`)
process.exit(failures === 0 ? 0 : 1)
