<#
.SYNOPSIS
  M2 数据收集占位脚本：网络真实数据下载（ADR-3）。

.DESCRIPTION
  目标：natural(content)/UI/text/form 各 1000 张（train 800 + val 200），
  全部用网络真实数据（软件名搜索截图 / 真实照片），不用合成数据。

  占位说明：搜索引擎/来源站各有反爬与条款限制，数据收集需要人工半自动完成。
  本脚本预留目录结构与提示；M2 实施时在此填充具体抓取/筛选逻辑。

  目录约定（见 data/README.md）：
    data/raw/l1/content | data/raw/l1/structure
    data/raw/l2/ui | data/raw/l2/text | data/raw/l2/form
#>
[CmdletBinding()]
param(
    [string]$DataDir = (Join-Path $PSScriptRoot "..\data")
)

$ErrorActionPreference = "Stop"
$DataDir = (Resolve-Path $DataDir).Path

$dirs = @(
    "raw\l1\content", "raw\l1\structure",
    "raw\l2\ui", "raw\l2\text", "raw\l2\form"
)

foreach ($d in $dirs) {
    $full = Join-Path $DataDir $d
    New-Item -ItemType Directory -Force -Path $full | Out-Null
}

Write-Host "目录结构已就绪："
$dirs | ForEach-Object { Write-Host "  $DataDir\$_" }
Write-Host ""
Write-Host "M2 数据收集建议："
Write-Host "  1. content：搜索引擎图片（自然风景/人物/动物/建筑等关键词）、公共照片数据集子集"
Write-Host "  2. ui：本机各软件窗口真实截图（PrintScreen/工具）、软件官网宣传图"
Write-Host "  3. text：代码/文档/文章长截图、PDF 页面渲染"
Write-Host "  4. form：登录/注册/调查问卷截图、表格页面（Excel/网页表格）"
Write-Host "  （具体抓取脚本在 M2 里程碑补充，见 python/dsh_visit/train/data.py）"
