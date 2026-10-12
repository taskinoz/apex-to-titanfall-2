param([string]$Package='PhaseRunner.CollisionLab')
$ErrorActionPreference='Stop'
$taskPidPath=Join-Path $PSScriptRoot 'logs/triangle-lab-pid.txt'
if(Test-Path -LiteralPath $taskPidPath){
 $taskPid=[int](Get-Content -LiteralPath $taskPidPath)
 $taskProcess=Get-Process -Id $taskPid -ErrorAction SilentlyContinue
 if($taskProcess -and $taskProcess.ProcessName -eq 'NorthstarLauncher'){Stop-Process -Id $taskPid}
}
foreach($taskRelative in @('mod/maps/mp_phase_runner_preview.bsp','mod/scripts/vscripts/_phase_runner_preview.nut')){
 Copy-Item -LiteralPath (Join-Path $PSScriptRoot "northstar/$Package/$taskRelative") -Destination "D:/Games/Titanfall2/R2CollisionLab/mods/PhaseRunner.CollisionLab/$taskRelative" -Force
}
$taskServer=Start-Process 'D:/Games/Titanfall2/NorthstarLauncher.exe' -WorkingDirectory 'D:/Games/Titanfall2' -ArgumentList '-profile=R2CollisionLab -dedicated -multiple -novid -nosound +ip 127.0.0.1 +hostport 37031 +sv_lan 1 +ns_report_server_to_masterserver 0 +ns_report_sp_server_to_masterserver 0 +phase_runner_local_test 1 +setplaylist private_match +mp_gamemode ffa +map mp_phase_runner_preview' -WindowStyle Hidden -PassThru
$taskServer.Id | Set-Content -LiteralPath $taskPidPath
Write-Output $taskServer.Id
Wait-Process -Id $taskServer.Id
