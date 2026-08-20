/**
 * 管理工具：本地视觉推理常驻后端生命周期（status / release / restart）。
 *
 * 常驻后端承载 OmniParser/OCR/YOLO/分类器，模型进程内缓存、首次加载后秒级响应；
 * 但模型常驻会占用 GPU 显存（OmniParser ≈ 2.4GB）。本工具给 agent 提供：
 *   - status：进程/模型加载/GPU 显存
 *   - release：关闭常驻后端，归还 GPU 显存（下一次任一视觉工具调用会自动重新拉起并懒加载）
 *   - restart：立即重启
 */

import { defineTool } from '@deepseek-ai/dsh-tools'
import { backendStatus, releaseDaemon, ensureDaemon } from '../backend.js'

export function createManageVisionBackendTool(config) {
  return defineTool({
    name: 'manage_vision_backend',
    description:
      '管理本地视觉推理常驻后端（承载 OmniParser/OCR/YOLO/分类器模型；进程内缓存，' +
      '首次加载后秒级响应，但常驻会占用 GPU 显存约 2.4GB）。' +
      'action=status：查看后端是否运行、已加载模型、GPU 显存占用；' +
      'action=release：关闭常驻后端释放 GPU 显存（后续调用任一视觉工具会自动重新拉起并懒加载模型，' +
      'OmniParser 首次调用需 15-25s）；' +
      'action=restart：立即重启。当 GPU 显存不足或暂时不需要视觉处理时，建议 release。',
    parameters: {
      action: {
        type: 'string',
        required: true,
        enum: ['status', 'release', 'restart'],
        description: '操作：status 查看 / release 释放 / restart 重启',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          action: { type: 'string', enum: ['status', 'release', 'restart'], description: '执行的操作' },
          running: { type: 'boolean', description: '后端进程是否运行中' },
          released: { type: 'boolean', description: 'release 时：是否曾释放' },
          restarted: { type: 'boolean', description: 'restart 时：是否已重启' },
          was_running: { type: 'boolean', description: 'restart 时：重启前是否在运行' },
          process: { type: 'object', additionalProperties: true, description: '进程信息（pid/uptime）' },
          models: { type: 'object', additionalProperties: true, description: '已加载模型状态（omniparser/ocr/table 等）' },
          gpu: { type: 'object', additionalProperties: true, description: 'GPU 信息（名称/显存占用 MB）' },
          error: { type: 'string', description: '错误信息' },
        },
      },
      render: (_args, value) => [{
        type: 'text',
        text: value.action === 'status'
          ? value.running
            ? `视觉后端运行中（pid ${value.process?.pid}）｜模型: ${Object.entries(value.models || {}).filter(([, v]) => v).map(([k]) => k).join(', ') || '无'}｜GPU 显存占用 ${value.gpu?.used_mb ?? '?'}MB`
            : '视觉后端未运行（任何视觉工具调用时会自动拉起）'
          : value.action === 'release'
            ? (value.released ? `已释放常驻后端${value.cleanExit === false ? '（强制终止）' : ''}，GPU 显存已归还` : '后端本就未运行')
            : `已重启视觉后端${value.was_running ? '（原进程已释放）' : ''}`,
      }],
    },
    timeoutMs: 30_000,
    async execute(args, exec) {
      if (args.action === 'status') {
        return { action: 'status', ...(await backendStatus(config)) }
      }
      if (args.action === 'release') {
        const r = await releaseDaemon(config)
        return { action: 'release', running: false, released: r.released, wasRunning: r.wasRunning, cleanExit: r.cleanExit }
      }
      // restart
      const before = await backendStatus(config)
      await releaseDaemon(config)
      await ensureDaemon(config)
      return { action: 'restart', running: true, restarted: true, was_running: before.running }
    },
  })
}
