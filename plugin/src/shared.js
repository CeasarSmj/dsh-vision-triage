/**
 * 通用辅助：图片路径校验、结果渲染。
 */

import { existsSync, statSync } from 'node:fs'
import { extname, resolve } from 'node:path'

export const IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.webp', '.bmp']

/** 校验并绝对化图片路径；非法则抛错（由注册表转为 isError）。 */
export function resolveImagePath(filePath) {
  const p = resolve(filePath)
  if (!existsSync(p)) throw new Error(`file not found: ${filePath}`)
  if (!statSync(p).isFile()) throw new Error(`not a regular file: ${p}`)
  const ext = extname(p).toLowerCase()
  if (!IMAGE_EXTS.includes(ext)) {
    throw new Error(`unsupported image extension "${ext || '(none)'}" (supported: ${IMAGE_EXTS.join(', ')})`)
  }
  return p
}

/** 渲染：格式化 JSON（适合结构化输出）。 */
export function renderJson(_args, value) {
  return [{ type: 'text', text: JSON.stringify(value, null, 2) }]
}
