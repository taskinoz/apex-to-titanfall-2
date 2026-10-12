param([Parameter(ValueFromRemainingArguments=$true)][string[]]$HarnessArgs)
$ErrorActionPreference = 'Stop'
$pythonRuntime = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
if (!(Test-Path -LiteralPath $pythonRuntime)) { $pythonRuntime = 'python' }
& $pythonRuntime (Join-Path $PSScriptRoot 'r5-harness/harness.py') @HarnessArgs
exit $LASTEXITCODE
