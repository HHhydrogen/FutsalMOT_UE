param([Parameter(Mandatory=$true)][string]$RunName,
 [ValidateRange(1,12)][int]$WriteConcurrency = 8,
 [ValidateRange(1,12)][int]$WriteQueueSize = 8)
$ErrorActionPreference = 'Stop'
if ($RunName -notmatch '^[a-z0-9_]+$') { throw 'Invalid run name' }
$poseProject = 'D:/projects/FutsalMOT_UEDataset'
$poseExisting = @(Get-CimInstance Win32_Process -Filter "Name='UnrealEditor.exe'")
if ($poseExisting.Count -ne 0) { throw 'Editor already exists; inspect before launch' }
$poseLog = Join-Path $poseProject ('Saved/Pose17Development/editor_' + $RunName + '.log')
$poseReceipt = Join-Path $poseProject ('Saved/Pose17Development/editor_' + $RunName + '_launch.json')
if ((Test-Path -LiteralPath $poseLog) -or (Test-Path -LiteralPath $poseReceipt)) { throw 'Use a new run name' }
$poseArgs = @(
    ('"' + $poseProject + '/FustalMOT_UEDataset.uproject"'),
    '/Game/FutsalMOT/Maps/L_FutsalCourt', '-NoLiveCoding', '-NoSound', '-NoSplash',
    '-ModelContextProtocolStartServer', ('-abslog="' + $poseLog + '"'),
    '-LogCmds="LogModuleManager Verbose"',
    ('-ExecCmds="ImageWriteQueue.MaxConcurrency ' + $WriteConcurrency + ',ImageWriteQueue.MaxQueueSize ' + $WriteQueueSize + '"')
)
$poseEditor = Start-Process -FilePath 'E:/UE_5.8/Engine/Binaries/Win64/UnrealEditor.exe' -ArgumentList $poseArgs -WindowStyle Hidden -PassThru
@{pid=$poseEditor.Id;log=$poseLog;dll_sha256=(Get-FileHash -LiteralPath (Join-Path $poseProject 'Binaries/Win64/UnrealEditor-FutsalMOT.dll') -Algorithm SHA256).Hash} | ConvertTo-Json | Set-Content -LiteralPath $poseReceipt -Encoding ascii
Get-Content -LiteralPath $poseReceipt
