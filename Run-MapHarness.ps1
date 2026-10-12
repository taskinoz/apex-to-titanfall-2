param([Parameter(ValueFromRemainingArguments=$true)][string[]]$HarnessArguments)
$ErrorActionPreference='Stop'
$taskPython='C:/Users/tristan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
if(-not(Test-Path -LiteralPath $taskPython)){
    $taskPython=(Get-Command python -ErrorAction Stop).Source
}
& $taskPython (Join-Path $PSScriptRoot 'test-harness/harness.py') @HarnessArguments
exit $LASTEXITCODE
