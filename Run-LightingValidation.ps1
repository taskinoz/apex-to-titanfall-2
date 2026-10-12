param([string]$PackageDirectory='northstar/PhaseRunner.EnvironmentRelease',[string]$MapName='mp_phase_runner_preview')
$ErrorActionPreference='Stop'
$taskPackage=Join-Path $PSScriptRoot $PackageDirectory
$taskProfile='D:/Games/Titanfall2/R2CollisionLab/mods/PhaseRunner.CollisionLab'
$taskExisting=Get-CimInstance Win32_Process -Filter "name = 'NorthstarLauncher.exe'" | Where-Object { $_.CommandLine -like '*-profile=R2CollisionLab*' -and $_.CommandLine -like '*+hostport 37031*' }
if($taskExisting){throw 'The isolated test profile is already running.'}
foreach($taskFile in Get-ChildItem -LiteralPath $taskPackage -Recurse -File){
 $taskRelative=$taskFile.FullName.Substring($taskPackage.Length).TrimStart('\')
 $taskTarget=Join-Path $taskProfile $taskRelative
 New-Item -ItemType Directory -Path (Split-Path -Parent $taskTarget) -Force | Out-Null
 Copy-Item -LiteralPath $taskFile.FullName -Destination $taskTarget -Force
}
if($MapName -notmatch '^mp_[a-z0-9_]+$'){throw 'Invalid test map name'}
$taskServer=Start-Process 'D:/Games/Titanfall2/NorthstarLauncher.exe' -WorkingDirectory 'D:/Games/Titanfall2' -ArgumentList "-profile=R2CollisionLab -dedicated -multiple -novid -nosound +ip 127.0.0.1 +hostport 37031 +sv_lan 1 +ns_report_server_to_masterserver 0 +ns_report_sp_server_to_masterserver 0 +phase_runner_local_test 1 +setplaylist private_match +mp_gamemode ffa +map $MapName" -WindowStyle Hidden -PassThru
$taskServer.Id | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'logs/environment-validation-pid.txt')
Write-Output "Lighting validation server PID: $($taskServer.Id)"
