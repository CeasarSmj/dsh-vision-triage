<#
.SYNOPSIS
  安装并修补 OmniParser v2（models/omniparser/），供 parse_ui_screenshot 使用。

.DESCRIPTION
  1. git clone microsoft/OmniParser → models/omniparser/OmniParser（已存在则跳过）
  2. 下载权重（hf-mirror 优先，失败回退 huggingface.co）→ models/omniparser/weights/
     - icon_detect/model.pt（38.7MB，YOLO 元素检测）
     - icon_caption_florence/*（约 1.03GB，Florence-2 语义描述）
  3. 幂等修补 util/utils.py（ADR-9 裁剪 paddle / ADR-10 空 OCR 崩溃 / 中英文 OCR）
  4. 预下载 Florence-2 processor（transformers 4.x remote code，经 hf-mirror）

  依赖：sdenv（torch + transformers 4.57.2 + easyocr + supervision 等，见 python/requirements.txt）
#>
[CmdletBinding()]
param(
    [string]$OmniDir = (Join-Path $PSScriptRoot "..\models\omniparser\OmniParser"),
    [string]$WeightsDir = (Join-Path $PSScriptRoot "..\models\omniparser\weights")
)

$ErrorActionPreference = "Stop"
$OmniDir = (Resolve-Path (Split-Path $OmniDir)).Path + "\" + (Split-Path $OmniDir -Leaf)
$utilsFile = Join-Path $OmniDir "util\utils.py"
$weightsRoot = Join-Path $WeightsDir ".." # 规范化

Write-Host "== 1/4 克隆 OmniParser =="
if (-not (Test-Path (Join-Path $OmniDir "util\utils.py"))) {
    New-Item -ItemType Directory -Force -Path (Split-Path $OmniDir) | Out-Null
    git clone --depth 1 https://github.com/microsoft/OmniParser.git $OmniDir
    Write-Host "  已克隆: $OmniDir"
} else {
    Write-Host "  已存在: $OmniDir"
}

Write-Host "== 2/4 下载权重（约 1.1GB，镜像优先）=="
$base = "https://hf-mirror.com/microsoft/OmniParser-v2.0/resolve/main"
$files = @(
    @{ Name = "icon_detect/model.pt";             Dst = "icon_detect\model.pt" },
    @{ Name = "icon_caption/model.safetensors";   Dst = "icon_caption_florence\model.safetensors" },
    @{ Name = "icon_caption/config.json";         Dst = "icon_caption_florence\config.json" },
    @{ Name = "icon_caption/generation_config.json"; Dst = "icon_caption_florence\generation_config.json" },
    @{ Name = "icon_caption/LICENSE";             Dst = "icon_caption_florence\LICENSE" }
)
foreach ($f in $files) {
    $dst = Join-Path $WeightsDir $f.Dst
    if (Test-Path $dst) { Write-Host "  已存在: $($f.Dst)"; continue }
    New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null
    Write-Host "  下载: $($f.Dst) ..."
    curl.exe -sSL --retry 3 -o $dst "$base/$($f.Name)"
    if (-not (Test-Path $dst) -or (Get-Item $dst).Length -eq 0) {
        Write-Host "  镜像失败，回退 huggingface.co ..." -ForegroundColor Yellow
        Remove-Item $dst -Force -ErrorAction SilentlyContinue
        curl.exe -sSL --retry 2 -o $dst "https://huggingface.co/microsoft/OmniParser-v2.0/resolve/main/$($f.Name)"
    }
    if (-not (Test-Path $dst) -or (Get-Item $dst).Length -eq 0) { throw "下载失败: $($f.Name)" }
}

Write-Host "== 3/4 修补 util/utils.py（ADR-9/10 + 中英文 OCR）=="
$utils = Get-Content $utilsFile -Raw -Encoding UTF8
if ($utils -notmatch "dsh-vision-triage 修补 ADR-9") {
    $pattern = '(?s)from paddleocr import PaddleOCR.*?use_gpu=False,.*?\n\)\n'
    if ($utils -match $pattern) {
        $utils = $utils -replace $pattern, ""
        $utils = $utils -replace "reader = easyocr\.Reader\(\['en'\]\)", "reader = easyocr.Reader(['ch_sim', 'en'])  # [dsh-vision-triage 修补] 中英文"
        Write-Host "  [修补] 已裁剪 paddle 硬依赖"
    } else { Write-Host "  [跳过] paddle 块未匹配（可能已修补或版本不同）" -ForegroundColor Yellow }
}
if ($utils -notmatch "dsh-vision-triage 修补 ADR-10") {
    $utils = $utils -replace "ocr_bbox = None", "ocr_bbox = []  # [dsh-vision-triage 修补 ADR-10] 空 OCR 用 [] 而非 None"
    Write-Host "  [修补] 已修复空 OCR 崩溃（zip(None)）"
}
Set-Content -Path $utilsFile -Value $utils -Encoding UTF8

Write-Host "== 4/4 预下载 Florence-2 processor + 修补 remote code =="
$env:HF_ENDPOINT = "https://hf-mirror.com"
& E:\conda\envs\sdenv\python.exe -c "from transformers import AutoProcessor; AutoProcessor.from_pretrained('microsoft/Florence-2-base', trust_remote_code=True); print('processor OK')" 2>&1 | Select-Object -Last 1
& (Join-Path $PSScriptRoot "patch-florence-remote-code.ps1")

Write-Host ""
Write-Host "OmniParser 安装完成。验证："
Write-Host "  & E:\conda\envs\sdenv\python.exe -m dsh_visit parse-ui --input <截图路径>"
Write-Host "  node scripts/smoke-bridge.mjs <截图路径>"
