/**
 * describe_image（云端 Qwen-VL）实测脚本。
 *
 * 从 $DSH_HOME/.credentials.yaml 读取 QWEN_VISION_API_KEY（与 DSH 凭据存储同源），
 * 通过插件定义直接调用 execute，验证云端链路可用。
 *
 * 用法：node scripts/smoke-describe.mjs <图片路径> [追问prompt]
 */

import { readFileSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { apply } from '../plugin/index.js'

const imgArg = process.argv[2]
if (!imgArg || !existsSync(resolve(imgArg))) {
  console.error('用法: node scripts/smoke-describe.mjs <图片路径> [prompt]')
  process.exit(2)
}
const img = resolve(imgArg)
const prompt = process.argv[3]

// 读取凭据（与 DSH 相同的文件）
const dshHome = process.env.DSH_HOME || `${process.env.USERPROFILE}\\.dsh`
const credFile = resolve(dshHome, '.credentials.yaml')
if (!existsSync(credFile)) {
  console.error(`凭据文件不存在: ${credFile}`)
  process.exit(2)
}
const credRaw = readFileSync(credFile, 'utf8')
const m = credRaw.match(/^QWEN_VISION_API_KEY:\s*(\S+)/m)
if (!m) {
  console.error('凭据文件中未找到 QWEN_VISION_API_KEY')
  process.exit(2)
}

const defs = []
const ctx = {
  tools: { register: (d) => defs.push(d) },
  credentials: { resolve: async () => ({ value: m[1] }) },
}
apply(ctx, {})
const tool = defs.find((d) => d.name === 'describe_image')

console.log(`== describe_image: ${img} ==`)
console.log(`prompt: ${prompt || '(默认详细描述)'}`)
const t0 = Date.now()
try {
  const value = await tool.execute(
    { file_path: img, ...(prompt ? { prompt } : {}) },
    { signal: new AbortController().signal },
  )
  console.log(`耗时 ${((Date.now() - t0) / 1000).toFixed(1)}s`)
  console.log('--- 返回内容 ---')
  console.log(value)
} catch (err) {
  console.error(`FAIL: ${err.message}`)
  process.exit(1)
}
