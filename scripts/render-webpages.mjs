/**
 * 真实网页渲染数据收集：用 headless Chromium 渲染真实站点页面截图，
 * 作为 L1 structure / L2 ui/text/form 的训练数据（ADR-3：真实数据）。
 *
 * 用法：
 *   set NODE_PATH=C:\Users\<user>\.dsh\profiles\node_modules
 *   node scripts/render-webpages.mjs [--max-per-class N] [--concurrency C]
 *
 * 输出：
 *   data/raw/l2/<cls>/<cls>_<seq>_<vw>_<scroll>.png
 *   并硬链接到 data/raw/l1/structure/（L1 structure = ui+text+form 并集）
 */

import { mkdirSync, linkSync, copyFileSync, existsSync, readdirSync } from 'node:fs'
import { dirname, resolve, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'
import { readFile } from 'node:fs/promises'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const require = createRequire(resolve(ROOT, 'plugin/index.js'))
const { chromium } = require('playwright')

const URLS_DIR = join(ROOT, 'data', 'urls')
const OUT_ROOT = join(ROOT, 'data', 'raw')
const CLASSES = ['ui', 'text', 'form']
const VIEWPORTS = [
  { width: 1280, height: 800 },
  { width: 1440, height: 900 },
  { width: 1366, height: 768 },
  { width: 1920, height: 1080 },
]
const SCROLLS = [0, 0.45] // 首屏 + 中部，每 URL 2 张

const maxIdx = process.argv.indexOf('--max-per-class')
const maxPerClass = maxIdx >= 0 ? parseInt(process.argv[maxIdx + 1] || '100000', 10) : 100000
const concIdx = process.argv.indexOf('--concurrency')
const concurrency = concIdx >= 0 ? parseInt(process.argv[concIdx + 1] || '3', 10) : 3

let seq = 0
const stats = {}

async function renderOne(browser, cls, url, destDir, structureDir) {
  const vp = VIEWPORTS[Math.floor(Math.random() * VIEWPORTS.length)]
  const context = await browser.newContext({ viewport: vp, locale: 'zh-CN', userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36' })
  const page = await context.newPage()
  const shots = []
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 25000 })
    await page.waitForTimeout(3500) // 等布局/图片稳定
    const height = await page.evaluate(() => document.body.scrollHeight).catch(() => vp.height)
    for (const ratio of SCROLLS) {
      const y = Math.max(0, Math.min(height - vp.height, Math.floor(height * ratio)))
      await page.evaluate((yy) => window.scrollTo(0, yy), y).catch(() => {})
      await page.waitForTimeout(600)
      seq += 1
      const name = `${cls}_${String(seq).padStart(5, '0')}_${vp.width}_${ratio}.png`
      const dest = join(destDir, name)
      await page.screenshot({ path: dest, type: 'png' })
      // 硬链接到 L1 structure（失败则复制）
      const linkDest = join(structureDir, name)
      try { linkSync(dest, linkDest) } catch { copyFileSync(dest, linkDest) }
      shots.push(name)
    }
  } catch (err) {
    return { url, ok: false, reason: err.message.slice(0, 120) }
  } finally {
    await context.close().catch(() => {})
  }
  return { url, ok: true, shots }
}

async function main() {
  mkdirSync(OUT_ROOT, { recursive: true })
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] })

  for (const cls of CLASSES) {
    stats[cls] = { total: 0, ok: 0, fail: [] }
    const urls = readFile(join(URLS_DIR, `${cls}.txt`), 'utf8')
      .then((t) => t.split('\n').map((s) => s.trim()).filter((s) => s && !s.startsWith('#')))
    const list = (await urls).slice(0, maxPerClass)
    stats[cls].total = list.length
    const destDir = join(OUT_ROOT, 'l2', cls)
    const structureDir = join(OUT_ROOT, 'l1', 'structure')
    mkdirSync(destDir, { recursive: true })
    mkdirSync(structureDir, { recursive: true })

    console.log(`\n== 渲染 ${cls}: ${list.length} 个 URL ==`)
    let idx = 0
    while (idx < list.length) {
      const batch = list.slice(idx, idx + concurrency)
      const results = await Promise.all(batch.map((u) => renderOne(browser, cls, u, destDir, structureDir)))
      for (const r of results) {
        if (r.ok) stats[cls].ok += 1
        else stats[cls].fail.push(`${r.url} (${r.reason})`)
      }
      idx += concurrency
      if (idx % 15 === 0 || idx >= list.length) {
        console.log(`  进度: ${Math.min(idx, list.length)}/${list.length}（成功 ${stats[cls].ok}）`)
      }
    }
  }

  await browser.close()
  console.log('\n=== 统计 ===')
  for (const cls of CLASSES) {
    const s = stats[cls]
    const files = readdirSync(join(OUT_ROOT, 'l2', cls)).length
    console.log(`${cls}: URL ${s.total}，成功 ${s.ok}，产出文件 ${files}，失败 ${s.fail.length}`)
    for (const f of s.fail.slice(0, 8)) console.log(`    ✗ ${f}`)
  }
}

main().catch((e) => { console.error('渲染失败:', e); process.exit(1) })
