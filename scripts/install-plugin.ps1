<#
.SYNOPSIS
  安装 dsh-vision-triage 插件到指定 DSH profile（junction + cordis.patch.yml 挂载行）。

.DESCRIPTION
  1. $DSH_HOME/profiles/<Profile>/node_modules/dsh-vision-triage → junction → 本仓库 plugin/
  2. plugin/node_modules → junction → $DSH_HOME/profiles/node_modules（解析 @deepseek-ai/dsh-tools）
  3. 在 profile 的 cordis.patch.yml 追加挂载行（已存在则跳过）

  与 dsh-vision-mcp 相同的安装方式（需求文档 §4.1、§4.3-5）。
#>
[CmdletBinding()]
param(
    [string]$Profile = "web",
    [string]$DSHHome = "$env:USERPROFILE\.dsh",
    [string]$PluginDir = (Join-Path $PSScriptRoot "..\plugin")
)

$ErrorActionPreference = "Stop"
$PluginDir = (Resolve-Path $PluginDir).Path
$profileNodeModules = Join-Path $DSHHome "profiles\$Profile\node_modules"
$sharedNodeModules  = Join-Path $DSHHome "profiles\node_modules"
$patchFile          = Join-Path $DSHHome "profiles\$Profile\cordis.patch.yml"

if (-not (Test-Path $profileNodeModules)) { throw "profile node_modules 不存在: $profileNodeModules" }
if (-not (Test-Path $sharedNodeModules))  { throw "共享 node_modules 不存在: $sharedNodeModules（DSH 未安装？）" }
if (-not (Test-Path (Join-Path $PluginDir "package.json"))) { throw "插件目录缺少 package.json: $PluginDir" }

function New-Junction([string]$Path, [string]$Target) {
    if (Test-Path $Path) {
        $item = Get-Item $Path
        if ($item.LinkType -eq "Junction" -and $item.Target -eq $Target) {
            Write-Host "  已存在（正确）: $Path"
            return
        }
        throw "路径已存在且非目标 junction，请手动处理: $Path"
    }
    New-Item -ItemType Junction -Path $Path -Target $Target | Out-Null
    Write-Host "  已创建 junction: $Path -> $Target"
}

Write-Host "== 1/3 挂载插件包 =="
New-Junction (Join-Path $profileNodeModules "dsh-vision-triage") $PluginDir

Write-Host "== 2/3 插件依赖解析 =="
New-Junction (Join-Path $PluginDir "node_modules") $sharedNodeModules

Write-Host "== 3/3 追加 cordis.patch.yml 挂载行 =="
$mountBlock = @"

- insert:
    - id: dsh-vision-triage
      name: dsh-vision-triage
      config:
        baseUrl: https://dashscope.aliyuncs.com/compatible-mode/v1
        model: qwen-vl-max
"@

if (-not (Test-Path $patchFile)) {
    Set-Content -Path $patchFile -Value ($mountBlock.TrimStart() + "`n") -Encoding UTF8
    Write-Host "  已创建 $patchFile"
} elseif (Select-String -Path $patchFile -Pattern "dsh-vision-triage" -Quiet) {
    Write-Host "  已包含挂载行，跳过（$patchFile）"
} else {
    Add-Content -Path $patchFile -Value $mountBlock -Encoding UTF8
    Write-Host "  已追加挂载行到 $patchFile"
}

Write-Host ""
Write-Host "安装完成。请重启 DSH（或等待配置 HMR）后验证 6 个工具："
Write-Host "  classify_image / classify_structure / detect_natural_image /"
Write-Host "  parse_ui_screenshot / ocr_image / describe_image"
Write-Host "（describe_image 需要凭据 QWEN_VISION_API_KEY，见 plugin/README.md）"
