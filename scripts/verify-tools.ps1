<#
.SYNOPSIS
  验证 dsh-vision-triage 安装状态（结构检查，不依赖 DSH 运行时）。

.DESCRIPTION
  检查：
  1. profile node_modules 中的插件 junction 存在且指向本仓库 plugin/
  2. plugin/node_modules junction 指向共享模块（@deepseek-ai/dsh-tools 可解析）
  3. profile cordis.patch.yml 含挂载行
  4. Python 后端 status 命令可运行（环境/模型就绪度）
#>
[CmdletBinding()]
param(
    [string]$Profile = "web",
    [string]$DSHHome = "$env:USERPROFILE\.dsh",
    [string]$PluginDir = (Join-Path $PSScriptRoot "..\plugin"),
    [string]$Python = $env:DSH_VISIT_PYTHON
)

$ErrorActionPreference = "Stop"
$PluginDir = (Resolve-Path $PluginDir).Path
$fail = 0

function Check([string]$Name, [bool]$Ok, [string]$Detail = "") {
    if ($Ok) { Write-Host "  [PASS] $Name" -ForegroundColor Green }
    else     { Write-Host "  [FAIL] $Name $Detail" -ForegroundColor Red; $script:fail++ }
}

Write-Host "== 1/4 插件 junction =="
$pluginJunction = Join-Path $DSHHome "profiles\$Profile\node_modules\dsh-vision-triage"
if (Test-Path $pluginJunction) {
    $item = Get-Item $pluginJunction
    Check "插件 junction" ($item.LinkType -eq "Junction") "link=$($item.LinkType)"
    Check "目标指向本仓库" (@($item.Target) -contains $PluginDir) "target=$($item.Target -join ', ')"
} else {
    Check "插件 junction" $false "缺失: $pluginJunction（运行 install-plugin.ps1）"
}

Write-Host "== 2/4 依赖解析 junction =="
$depJunction = Join-Path $PluginDir "node_modules"
if (Test-Path $depJunction) {
    $item = Get-Item $depJunction
    Check "依赖 junction" ($item.LinkType -eq "Junction") "link=$($item.LinkType)"
    Check "dsh-tools 可解析" (Test-Path (Join-Path $depJunction "@deepseek-ai\dsh-tools"))
} else {
    Check "依赖 junction" $false "缺失: $depJunction（运行 install-plugin.ps1）"
}

Write-Host "== 3/4 cordis.patch.yml 挂载行 =="
$patchFile = Join-Path $DSHHome "profiles\$Profile\cordis.patch.yml"
if (Test-Path $patchFile) {
    Check "挂载行存在" (Select-String -Path $patchFile -Pattern "dsh-vision-triage" -Quiet) $patchFile
} else {
    Check "挂载行存在" $false "缺失: $patchFile"
}

Write-Host "== 4/4 Python 后端自检 =="
if (-not $Python) { $Python = "E:\conda\envs\sdenv\python.exe" }
if (Test-Path $Python) {
    $env:DSH_VISIT_ROOT = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    $env:PYTHONPATH = (Join-Path $env:DSH_VISIT_ROOT "python")
    try {
        $out = & $Python -m dsh_visit status 2>&1
        if ($LASTEXITCODE -eq 0) {
            Check "后端 status" $true
            Write-Host "  $($out -join ' ')"
        } else {
            Check "后端 status" $false ($out -join " ")
        }
    } catch {
        Check "后端 status" $false $_.Exception.Message
    }
} else {
    Check "后端 Python" $false "未找到: $Python（可用 DSH_VISIT_PYTHON 覆盖）"
}

Write-Host ""
if ($fail -eq 0) { Write-Host "全部通过。重启 DSH 后应出现 6 个工具。" -ForegroundColor Green }
else { Write-Host "$fail 项未通过，请按提示处理。" -ForegroundColor Red; exit 1 }
