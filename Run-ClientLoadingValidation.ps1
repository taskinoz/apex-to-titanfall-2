param([string]$PackageDirectory='northstar/PhaseRunner.Preview',[string]$GameMode='ffa',[switch]$RunTransitions)
$ErrorActionPreference='Stop'
$taskPackage=Join-Path $PSScriptRoot $PackageDirectory
$taskProfile='D:/Games/Titanfall2/R2CollisionLab/mods/PhaseRunner.CollisionLab'
$taskExisting=Get-CimInstance Win32_Process -Filter "name = 'NorthstarLauncher.exe'" | Where-Object { $_.CommandLine -like '*-profile=R2CollisionLab*' }
for ($taskAttempt=0; $taskExisting -and $taskAttempt -lt 10; $taskAttempt++) {
 Start-Sleep -Milliseconds 500
 $taskExisting=Get-CimInstance Win32_Process -Filter "name = 'NorthstarLauncher.exe'" | Where-Object { $_.CommandLine -like '*-profile=R2CollisionLab*' }
}
if($taskExisting){throw 'The isolated test profile is already running.'}
foreach($taskFile in Get-ChildItem -LiteralPath $taskPackage -Recurse -File){
 $taskRelative=$taskFile.FullName.Substring($taskPackage.Length).TrimStart('\')
 $taskTarget=Join-Path $taskProfile $taskRelative
 New-Item -ItemType Directory -Path (Split-Path -Parent $taskTarget) -Force | Out-Null
 Copy-Item -LiteralPath $taskFile.FullName -Destination $taskTarget -Force
}
$taskTestSource=Join-Path $PSScriptRoot 'northstar/PhaseRunner.LoadingTransitionTest'
$taskTestTarget='D:/Games/Titanfall2/R2CollisionLab/mods/PhaseRunner.LoadingTransitionTest'
if ($RunTransitions) {
 foreach ($taskFile in Get-ChildItem -LiteralPath $taskTestSource -Recurse -File) {
  $taskRelative=$taskFile.FullName.Substring($taskTestSource.Length).TrimStart('\')
  $taskTarget=Join-Path $taskTestTarget $taskRelative
  New-Item -ItemType Directory -Path (Split-Path -Parent $taskTarget) -Force | Out-Null
  Copy-Item -LiteralPath $taskFile.FullName -Destination $taskTarget -Force
 }
}
$taskEnabledPath='D:/Games/Titanfall2/R2CollisionLab/enabledmods.json'
$taskEnabled=Get-Content -LiteralPath $taskEnabledPath -Raw | ConvertFrom-Json -AsHashtable
$taskEnabled['PhaseRunner.LoadingTransitionTest']=@{'0.0.1'=[bool]$RunTransitions}
$taskEnabled | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskEnabledPath
if($GameMode -notin @('ffa','tdm')){throw 'Invalid test mode'}
$taskClient=Start-Process 'D:/Games/Titanfall2/NorthstarLauncher.exe' -WorkingDirectory 'D:/Games/Titanfall2' -ArgumentList "-profile=R2CollisionLab -multiple -novid -nosound -windowed -w 1280 -h 720 +ip 127.0.0.1 +hostport 37031 +sv_lan 1 +ns_report_server_to_masterserver 0 +ns_report_sp_server_to_masterserver 0 +phase_runner_local_test 1 +setplaylist private_match +mp_gamemode $GameMode +map mp_phase_runner" -WindowStyle Hidden -PassThru
$taskClient.Id | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'logs/client-loading-validation-pid.txt')
Write-Output "Isolated client PID: $($taskClient.Id)"
