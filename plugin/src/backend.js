/**
 * Python 桥接层：以子进程方式调用本地推理后端 `python -m dsh_visit <cmd>`。
 *
 * 协议（见 docs/architecture.md §6）：
 *   - stdout 输出单个 JSON 对象（utf-8）；错误走 stderr + 非零退出码
 *   - 退出码：0 成功 / 1 参数或 IO 错误 / 2 推理层错误
 *   - 取消：exec.signal 透传给子进程（registry 超时/取消即杀掉子进程）
 */

import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

// 本文件位于 <项目根>/plugin/src/backend.js
const PLUGIN_SRC_DIR = dirname(fileURLToPath(import.meta.url))
const PROJECT_ROOT = resolve(PLUGIN_SRC_DIR, '..', '..')

/** 解析插件配置中与路径相关的项。 */
export function resolvePaths(config) {
  return {
    python: config.python,
    root: config.root || process.env.DSH_VISIT_ROOT || PROJECT_ROOT,
    pythonDir: resolve(PROJECT_ROOT, 'python'),
    modelsDir: config.modelsDir || process.env.DSH_VISIT_MODELS_DIR || resolve(PROJECT_ROOT, 'models'),
    dataDir: config.dataDir || process.env.DSH_VISIT_DATA_DIR || resolve(PROJECT_ROOT, 'data'),
  }
}

/**
 * 调用一次 Python 后端，返回解析后的 JSON。
 * @param {object} config 插件配置（python/modelsDir/dataDir）
 * @param {string} command dsh_visit 子命令名
 * @param {string[]} args 子命令参数（--input 等）
 * @param {object} [opts] { signal: AbortSignal }
 */
export async function runPython(config, command, args, { signal } = {}) {
  const paths = resolvePaths(config)
  if (!existsSync(paths.python)) {
    throw new Error(
      `本地推理 Python 不存在: ${paths.python}（可用环境变量 DSH_VISIT_PYTHON 覆盖）`,
    )
  }

  return new Promise((resolvePromise, rejectPromise) => {
    const child = spawn(paths.python, ['-m', 'dsh_visit', command, ...args], {
      cwd: paths.root,
      env: {
        ...process.env,
        DSH_VISIT_ROOT: paths.root,
        DSH_VISIT_MODELS_DIR: paths.modelsDir,
        DSH_VISIT_DATA_DIR: paths.dataDir,
        PYTHONPATH: paths.pythonDir,
        PYTHONIOENCODING: 'utf-8',
        PYTHONUTF8: '1',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
      signal,
    })

    let stdout = ''
    let stderr = ''
    child.stdout.on('data', (d) => { stdout += d })
    child.stderr.on('data', (d) => { stderr += d })

    child.on('error', (err) => {
      if (err.name === 'AbortError' || signal?.aborted) {
        rejectPromise(new DOMException('The operation was aborted.', 'AbortError'))
      } else {
        rejectPromise(new Error(`无法启动 Python 子进程: ${err.message}`))
      }
    })

    child.on('close', (code) => {
      if (signal?.aborted) {
        rejectPromise(new DOMException('The operation was aborted.', 'AbortError'))
        return
      }
      if (code !== 0) {
        const tail = stderr.trim().split('\n').slice(-8).join('\n')
        rejectPromise(new Error(`dsh_visit ${command} 退出码 ${code}: ${tail || '(无 stderr)'}`))
        return
      }
      try {
        // 后端约定：stdout 输出单个 JSON 对象；个别命令（如 parse-ui 加载 OmniParser）
        // 会有框架进度输出混入 stdout，因此取最后一行可解析 JSON，向前兼容噪音输出。
        const lines = stdout.trim().split('\n').map((l) => l.trim()).filter(Boolean)
        let parsed = null
        for (let i = lines.length - 1; i >= 0; i--) {
          try { parsed = JSON.parse(lines[i]); break } catch { /* 非 JSON 行，跳过 */ }
        }
        if (parsed === null) throw new Error('no JSON line')
        resolvePromise(parsed)
      } catch {
        rejectPromise(new Error(`dsh_visit ${command} 输出非法 JSON: ${stdout.slice(0, 500)}`))
      }
    })
  })
}
