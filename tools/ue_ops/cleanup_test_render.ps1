param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$testRoot = 'G:\FutsalMOT_Dataset\test'
if (-not (Test-Path -LiteralPath $testRoot)) { Write-Output '测试目录不存在，无需清理'; exit 0 }
$resolvedRoot = (Resolve-Path -LiteralPath $testRoot).Path.TrimEnd('\')
if ($resolvedRoot -ne $testRoot) { throw '测试目录物理路径不符合白名单' }
foreach ($ancestor in @('G:\', 'G:\FutsalMOT_Dataset', $testRoot)) {
    if ((Get-Item -Force -LiteralPath $ancestor).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw '测试根禁止junction/reparse point' }
}
$removed = @()
$eligible = @()
foreach ($candidate in Get-ChildItem -Force -Directory -LiteralPath $testRoot) {
    $absolute = [IO.Path]::GetFullPath($candidate.FullName)
    if (-not $absolute.StartsWith($testRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw '目标超出测试根' }
    if ($candidate.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
    $receiptPath = Join-Path $absolute '_test_lifecycle.json'
    if (-not (Test-Path -LiteralPath $receiptPath -PathType Leaf)) { continue }
    $receipt = Get-Content -Raw -LiteralPath $receiptPath | ConvertFrom-Json
    if ($receipt.schema -ne 'futsalmot_test_render_lifecycle_v1' -or $receipt.state -notin @('complete', 'failed_stopped')) { continue }
    if ($receipt.active -ne $false -or -not $receipt.expires_at_utc) { continue }
    if ([DateTimeOffset]::Parse($receipt.expires_at_utc) -gt [DateTimeOffset]::UtcNow) { continue }
    # 手工遍历普通目录，任何重解析点都会使本attempt整项跳过。
    $pending = [Collections.Generic.Stack[string]]::new()
    $pending.Push($absolute)
    $hasLink = $false
    while ($pending.Count -gt 0 -and -not $hasLink) {
        foreach ($item in Get-ChildItem -Force -LiteralPath $pending.Pop()) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { $hasLink = $true; break }
            if ($item.PSIsContainer) { $pending.Push($item.FullName) }
        }
    }
    if ($hasLink) { continue }
    $eligible += $absolute
    if ($Apply) { Remove-Item -LiteralPath $absolute -Recurse -Force; $removed += $absolute }
}
[ordered]@{ apply=[bool]$Apply; root=$testRoot; eligible=$eligible; removed=$removed } | ConvertTo-Json -Depth 4
