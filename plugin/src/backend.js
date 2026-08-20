/**
 * Python 常驻后端桥接：`spawn python -m dsh_visit daemon` + 行式 JSON-RPC。
 *
 * 与旧"每次 spawn 单次进程"的区别：
 *   - 常驻进程在插件生命周期内保持运行，模型引擎（OmniParser/OCR/YOLO/分类器）
 *     进程内缓存，首次调用加载、之后秒级响应（parse-ui：25s → ~1s）。
 *   - 懒加载：进程拉起时零 GPU 占用，模型按需加载。
 *   - 生命周期：`releaseDaemon()`（manage_vision_backend 工具 / 插件 dispose）
 *     关闭进程归还 GPU；进程崩溃后下次调用自动重启。
 *
 * 协议（python/dsh_visit/daemon.py）：
 *   请求（stdin 每行）：{id, method, params}
 *   响应（stdout 每行）：{id, ok: true, result} | {id, ok: false, error}
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

/** 常驻后端状态（模块级单例）。 */
let daemon = null // { proc, nextId, pending: Map, ready, stopping, startedAt }

function daemonEnv(paths) {
  return {
    ...process.env,
    DSH_VISIT_ROOT: paths.root,
    DSH_VISIT_MODELS_DIR: paths.modelsDir,
    DSH_VISIT_DATA_DIR: paths.dataDir,
    PYTHONPATH: paths.pythonDir,
    PYTHONIOENCODING: 'utf-8',
    PYTHONUTF8: '1',
  }
}

/** 确保常驻进程存在；不存在（首次/崩溃后/release 后）则拉起。 */
export function ensureDaemon(config) {
  const paths = resolvePaths(config)
  if (daemon && daemon.proc.exitCode == null && !daemon.stopping) return daemon.ready

  if (!existsSync(paths.python)) {
    return Promise.reject(new Error(`本地推理 Python 不存在: ${paths.python}（可用环境变量 DSH_VISIT_PYTHON 覆盖）`))
  }

  const state = { proc: null, nextId: 1, pending: new Map(), stopping: false, startedAt: Date.now() }
  daemon = state

  state.ready = new Promise((resolveReady, rejectReady) => {
    const child = spawn(paths.python, ['-m', 'dsh_visit', 'daemon'], {
      cwd: paths.root,
      env: daemonEnv(paths),
      stdio: ['pipe', 'pipe', 'pipe'],
    })
    state.proc = child

    let buf = ''
    child.stdout.on('data', (d) => {
      buf += d
      let idx
      while ((idx = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, idx)
        buf = buf.slice(idx + 1)
        let resp
        try { resp = JSON.parse(line) } catch { continue }
        const p = state.pending.get(resp?.id)
        if (!p) continue
        state.pending.delete(resp.id)
        clearTimeout(p.timer)
        if (resp.ok) p.resolve(resp.result)
        else p.reject(new Error(resp.error || '后端调用失败'))
      }
    })
    child.stderr.on('data', () => { /* 模型进度输出，丢弃 */ })

    child.on('error', (err) => {
      rejectReady(err)
      state.ready = Promise.reject(err)
      state.stopping = true
    })

    child.on('exit', (code) => {
      state.stopping = true
      const err = new Error(`视觉推理后端已退出（exit=${code}）；下次调用会自动重启`)
      for (const p of state.pending.values()) {
        clearTimeout(p.timer)
        p.reject(err)
      }
      state.pending.clear()
      if (daemon === state) daemon = null
    })

    resolveReady(child)
  })
  return state.ready
}

/** 调用后端方法；opts: { timeoutMs, signal }。signal 触发时拒绝并丢弃迟到响应。 */
export async function callBackend(config, method, params, { timeoutMs = 120_000, signal } = {}) {
  await ensureDaemon(config)
  const state = daemon
  if (!state) throw new Error('视觉推理后端不可用')

  const id = state.nextId++
  return new Promise((resolvePromise, rejectPromise) => {
    const timer = setTimeout(() => {
      if (state.pending.delete(id)) {
        rejectPromise(new Error(`后端方法 ${method} 超时（${timeoutMs}ms）`))
      }
    }, timeoutMs)
    state.pending.set(id, { resolve: resolvePromise, reject: rejectPromise, timer })

    const onAbort = () => {
      if (state.pending.delete(id)) {
        clearTimeout(timer)
        rejectPromise(new DOMException('The operation was aborted.', 'AbortError'))
      }
    }
    if (signal) {
      if (signal.aborted) { onAbort(); return }
      signal.addEventListener('abort', onAbort, { once: true })
    }

    state.proc.stdin.write(JSON.stringify({ id, method, params: params || {} }) + '\n')
  })
}

/** 关闭常驻后端（释放 GPU 显存）。返回是否曾运行与是否优雅退出。 */
export async function releaseDaemon(config, { waitMs = 5000 } = {}) {
  const state = daemon
  if (!state || state.proc.exitCode != null) return { released: false, wasRunning: false }
  state.stopping = true

  const exited = new Promise((resolveExit) => {
    const t = setTimeout(() => {
      try { state.proc.kill() } catch { /* 已退出 */ }
      resolveExit(false)
    }, waitMs)
    state.proc.once('exit', () => { clearTimeout(t); resolveExit(true) })
  })

  try {
    state.proc.stdin.write(JSON.stringify({ id: state.nextId++, method: 'shutdown', params: {} }) + '\n')
  } catch { /* stdin 已关闭 */ }
  const cleanExit = await exited
  return { released: true, wasRunning: true, cleanExit }
}

/** 后端状态摘要（manage_vision_backend status 用）。 */
export async function backendStatus(config) {
  const state = daemon
  const running = !!(state && state.proc.exitCode == null && !state.stopping)
  if (!running) {
    return { running: false, process: null, backend: null, models: null, gpu: null }
  }
  let ping
  try {
    ping = await callBackend(config, 'ping', {}, { timeoutMs: 10_000 })
  } catch (err) {
    return { running: true, process: { pid: state.proc.pid }, backend: { error: err.message }, models: null, gpu: null }
  }
  return {
    running: true,
    process: { pid: state.proc.pid, started_at: state.startedAt, uptime_s: ping.uptime_s },
    backend: { python: ping.pong ? 'ok' : 'unknown' },
    models: ping.models_loaded,
    gpu: ping.gpu,
  }
}
