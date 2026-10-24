param(
    [string]$EngineRoot,
    [ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$RunName=('manual_'+(Get-Date -Format 'yyyyMMdd_HHmmss')),
    [switch]$ValidateOnly,
    [switch]$Visible
)
$ErrorActionPreference='Stop'
$editorProject=Split-Path -Parent $PSScriptRoot
$editorProjectFile=Join-Path $editorProject 'FustalMOT_UEDataset.uproject'
$editorDescriptor=Get-Content -LiteralPath $editorProjectFile -Raw | ConvertFrom-Json
if (-not $EngineRoot) {
    $editorAssociation=Get-ItemProperty -LiteralPath ('HKLM:/SOFTWARE/EpicGames/Unreal Engine/'+$editorDescriptor.EngineAssociation)
    $EngineRoot=$editorAssociation.InstalledDirectory
}
$editorExecutable=Join-Path $EngineRoot 'Engine/Binaries/Win64/UnrealEditor.exe'
$editorEngineManifest=Get-Content -LiteralPath (Join-Path $EngineRoot 'Engine/Binaries/Win64/UnrealEditor.modules') -Raw | ConvertFrom-Json
$editorProjectManifest=Get-Content -LiteralPath (Join-Path $editorProject 'Binaries/Win64/UnrealEditor.modules') -Raw | ConvertFrom-Json
if ($editorProjectManifest.BuildId -ne $editorEngineManifest.BuildId) { throw '项目模块与引擎BuildId不符，需使用当前引擎编译，不能忽略提示继续' }
foreach ($editorModule in $editorDescriptor.Modules) {
    $editorModuleFile=$editorProjectManifest.Modules.($editorModule.Name)
    if (-not $editorModuleFile -or -not (Test-Path -LiteralPath (Join-Path $editorProject ('Binaries/Win64/'+$editorModuleFile)))) { throw ('缺少项目编译模块：'+$editorModule.Name) }
}
if ($ValidateOnly) {
    @{status='project_and_engine_modules_match';project=$editorProjectFile;engine=$editorExecutable;build_id=$editorEngineManifest.BuildId} | ConvertTo-Json
    exit 0
}
if (@(Get-CimInstance Win32_Process -Filter "Name='UnrealEditor.exe'").Count) { throw '已有Editor实例；请核验并复用，不重复启动' }
$editorResearchJobs=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -match 'FutsalMOT.*(train_|run_poseonly|run_v4)|FutsalMOT_Research' })
if ($editorResearchJobs.Count) { throw '检测到项目研究进程，UE与GPU任务必须串行' }
$editorMemory=Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
$editorHeadroom=[double]$editorMemory.CommitLimit-[double]$editorMemory.CommittedBytes
if ($editorHeadroom -lt 20GB) { throw '系统提交内存余量不足20GiB，暂不启动Editor' }
$editorSaved=Get-Item -LiteralPath (Join-Path $editorProject 'Saved')
if (($editorSaved.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Saved必须为项目原物理目录' }
$editorRun=Join-Path $editorProject ('Saved/EditorStartup/'+$RunName)
if (Test-Path -LiteralPath $editorRun) { throw '启动目录已存在，请使用新RunName' }
New-Item -ItemType Directory -Path $editorRun | Out-Null
$editorLog=Join-Path $editorRun 'editor.log'
$editorArguments=@(('"'+$editorProjectFile+'"'),'-norecentproject','-NoLiveCoding','-ModelContextProtocolStartServer',('-abslog="'+$editorLog+'"'),'-LogCmds="LogModuleManager Verbose"')
$editorWindow=if ($Visible) { 'Normal' } else { 'Hidden' }
$editorProcess=Start-Process -FilePath $editorExecutable -ArgumentList $editorArguments -WorkingDirectory $editorProject -WindowStyle $editorWindow -PassThru
$editorReceipt=@{status='launched_wait_live_verification';pid=$editorProcess.Id;project=$editorProjectFile;executable=$editorExecutable;arguments=$editorArguments;log=$editorLog;build_id=$editorEngineManifest.BuildId;commit_headroom_GiB=([math]::Round($editorHeadroom/1GB,2));module_sha256=(Get-FileHash -LiteralPath (Join-Path $editorProject 'Binaries/Win64/UnrealEditor-FutsalMOT.dll')).Hash}
$editorReceipt | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $editorRun 'launch.json') -Encoding utf8
$editorReceipt | ConvertTo-Json -Depth 4
exit 0
