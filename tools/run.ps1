param(
    [ValidateSet('paths','p1','research','mcp')][string]$Mode='paths',
    [Parameter(ValueFromRemainingArguments=$true)][string[]]$CommandArguments
)
$ErrorActionPreference='Stop'
$runProject=Split-Path -Parent $PSScriptRoot
$runResearch=Join-Path (Split-Path -Parent $runProject) 'FutsalMOT_Research'
$runPython=Join-Path $runProject 'python/.venv/Scripts/python.exe'
$runSettings=Join-Path $runProject 'Saved/Local/paths.json'
$runResearchPython='D:/projects/FutsalMOT/.venv/Scripts/python.exe'
if (Test-Path -LiteralPath $runSettings) {
    $runLocal=Get-Content -LiteralPath $runSettings -Raw | ConvertFrom-Json
    if ($runLocal.research_python) { $runResearchPython=$runLocal.research_python }
}
if ($Mode -eq 'paths') {
    @{project=$runProject;python=(Join-Path $runProject 'python');saved=(Join-Path $runProject 'Saved');research=$runResearch;dataset='G:/FutsalMOT_Dataset';p1_python=$runPython;research_python=$runResearchPython} | ConvertTo-Json
    exit 0
}
$runPriorPythonPath=$env:PYTHONPATH
$runPriorUTF8=$env:PYTHONUTF8
$env:PYTHONUTF8='1'
Push-Location -LiteralPath $runProject
try {
    if ($Mode -eq 'research') {
        if (-not $CommandArguments.Count) { throw 'research需要experiments下的脚本路径' }
        $runEntry=(Resolve-Path -LiteralPath $CommandArguments[0]).Path
        $runAllowed=[IO.Path]::GetFullPath((Join-Path $runProject 'experiments'))+[IO.Path]::DirectorySeparatorChar
        $runBundleAllowed=[IO.Path]::GetFullPath((Join-Path $runResearch 'code'))+[IO.Path]::DirectorySeparatorChar
        $runFromSource=$runEntry.StartsWith($runAllowed,[StringComparison]::OrdinalIgnoreCase)
        $runFromBundle=$runEntry.StartsWith($runBundleAllowed,[StringComparison]::OrdinalIgnoreCase)
        if (-not $runFromSource -and -not $runFromBundle) { throw '研究入口必须来自experiments帮助或DResearch/code/<SHA>执行bundle' }
        if ($CommandArguments -notcontains '--help') {
            if (-not $runFromBundle) { throw '正式研究执行须使用已冻结DResearch/code/<SHA>，源码目录仅允许--help' }
            $runBundleRel=$runEntry.Substring($runBundleAllowed.Length).Split([IO.Path]::DirectorySeparatorChar)
            if ($runBundleRel[0] -notmatch '^[0-9a-f]{64}$') { throw '执行bundle目录必须为内容清单SHA' }
            $runEditors=@(Get-CimInstance Win32_Process -Filter "Name='UnrealEditor.exe'")
            if ($runEditors.Count) { throw 'Editor仍在运行；GPU研究必须等UE安全退出后再执行' }
        }
        & $runResearchPython -c 'import sys;assert sys.version_info[:2]==(3,10),"研究环境必须Python3.10"'
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        $runImportRoot=Join-Path $runProject 'python/src'
        if ($runFromBundle) {
            $runBundlePart=$runEntry.Substring($runBundleAllowed.Length).Split([IO.Path]::DirectorySeparatorChar)[0]
            $runImportRoot=Join-Path (Join-Path $runResearch 'code') ($runBundlePart+'/python/src')
        }
        $env:PYTHONPATH=$runImportRoot+';'+(Join-Path $runResearch 'runtime_dependencies')
        & $runResearchPython $runEntry @($CommandArguments | Select-Object -Skip 1)
    } else {
        & $runPython -c 'import sys;assert sys.version_info[:2]==(3,9),"P1环境必须Python3.9"'
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        if ($Mode -eq 'mcp') { & $runPython (Join-Path $runProject 'tools/mcp_cli.py') @CommandArguments }
        else { & $runPython -m grf_ue_bridge.cli @CommandArguments }
    }
    $runExit=$LASTEXITCODE
} finally {
    $env:PYTHONPATH=$runPriorPythonPath
    $env:PYTHONUTF8=$runPriorUTF8
    Pop-Location
}
exit $runExit
