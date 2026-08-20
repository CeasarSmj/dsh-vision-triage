<#
.SYNOPSIS
  修补 Florence-2 的 HF 缓存 remote code（modeling_florence2.py），使其兼容 transformers 4.5x/4.6x。

.DESCRIPTION
  背景（ADR-8）：OmniParser 依赖的 Florence-2 使用 trust_remote_code 从 HF 拉取旧版
  modeling_florence2.py；transformers>=4.5x 的新 generate 流程会传入 EncoderDecoderCache /
  空缓存元组等新结构，旧代码直接解引用 past_key_values[0][0] 会崩溃
  （AttributeError / IndexError）。

  修补内容（幂等，按标记跳过已修补文件）：
  1. prepare_inputs_for_generation（两处）：空缓存（None/()/含 None 结构）归一为 None
  2. past_length 取值改为维度安全（ndim>=3 才取 shape[2]）
  3. forward 中 past_key_values_length 同样改为 try/except 安全取值

  调用时机：安装 OmniParser 后执行（setup-omniparser.ps1 会自动调用本脚本）。
#>

$ErrorActionPreference = "Stop"
$cacheRoot = Join-Path $env:USERPROFILE ".cache\huggingface\modules\transformers_modules\microsoft"

$targets = Get-ChildItem -Path $cacheRoot -Recurse -Filter "modeling_florence2.py" -ErrorAction SilentlyContinue
if (-not $targets) {
    Write-Host "未找到 modeling_florence2.py（可能尚未加载过 Florence-2，先运行一次 parse-ui 触发下载）" -ForegroundColor Yellow
    exit 0
}

foreach ($t in $targets) {
    $text = [System.IO.File]::ReadAllText($t.FullName, [System.Text.Encoding]::UTF8)
    if ($text.Contains("dsh-vision-triage")) {
        Write-Host "  [跳过] 已修补: $($t.FullName)"
        continue
    }
    Write-Host "  修补: $($t.FullName)"

    # 1) prepare_inputs_for_generation：空缓存归一为 None（两处同构块）
    $nl = "`r`n"
    $oldBlock = @(
        "        # cut decoder_input_ids if past_key_values is used",
        "        if past_key_values is not None:",
        "            past_length = past_key_values[0][0].shape[2]",
        "",
        "            # Some generation methods already pass only the last input ID",
        "            if decoder_input_ids.shape[1] > past_length:",
        "                remove_prefix_length = past_length",
        "            else:",
        "                # Default to old behavior: keep only final ID",
        "                remove_prefix_length = decoder_input_ids.shape[1] - 1",
        "",
        "            decoder_input_ids = decoder_input_ids[:, remove_prefix_length:]"
    ) -join $nl
    $newBlock = @(
        "        # cut decoder_input_ids if past_key_values is used",
        "        # [dsh-vision-triage 修补] transformers>=4.5x 新 generate 传入空缓存结构",
        "        # （None/()/含 None 元素/EncoderDecoderCache），旧代码直接解引用会崩溃。",
        "        past_length = 0",
        "        try:",
        "            inner = past_key_values[0][0] if past_key_values else None",
        "        except (IndexError, TypeError, AttributeError):",
        "            inner = None",
        "        if inner is not None:",
        "            past_length = int(inner.shape[2]) if getattr(inner, 'ndim', 0) >= 3 else 0",
        "",
        "            # Some generation methods already pass only the last input ID",
        "            if decoder_input_ids.shape[1] > past_length:",
        "                remove_prefix_length = past_length",
        "            else:",
        "                # Default to old behavior: keep only final ID",
        "                remove_prefix_length = decoder_input_ids.shape[1] - 1",
        "",
        "            decoder_input_ids = decoder_input_ids[:, remove_prefix_length:]",
        "        else:",
        "            # 空缓存归一为 None，避免 forward 收到非 None 的空缓存后在 attention 层崩溃",
        "            past_key_values = None"
    ) -join $nl
    if ($text.Contains($oldBlock)) {
        $text = $text.Replace($oldBlock, $newBlock)
    } else {
        Write-Host "    [警告] 标准块未匹配（版本可能不同），尝试行级修补" -ForegroundColor Yellow
        $text = $text -replace 'past_length = past_key_values\[0\]\[0\]\.shape\[2\]', 'past_length = int(past_key_values[0][0].shape[2]) if past_key_values and getattr(past_key_values[0][0], "ndim", 0) >= 3 else 0'
    }

    # 2) forward 中 past_key_values_length 安全取值
    $oldLen = 'past_key_values_length = past_key_values[0][0].shape[2] if past_key_values is not None else 0'
    if ($text.Contains($oldLen)) {
        $text = $text.Replace($oldLen,
            'past_key_values_length = past_key_values[0][0].shape[2] if past_key_values and getattr(past_key_values[0][0], "ndim", 0) >= 3 else 0  # [dsh-vision-triage 修补]')
    }

    [System.IO.File]::WriteAllText($t.FullName, $text, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "    OK"
}

Write-Host "Florence-2 remote code 修补完成。"
