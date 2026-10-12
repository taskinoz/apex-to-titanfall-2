param([ValidateRange(1024,65535)][int]$Port = 4173)
$ErrorActionPreference = 'Stop'
$siteDirectory = Join-Path $PSScriptRoot 'site/dist'
$sitePython = 'C:/Users/tristan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
if (-not (Test-Path -LiteralPath $sitePython)) {
    $sitePython = (Get-Command python -ErrorAction Stop).Source
}
Write-Host "Map comparison site: http://127.0.0.1:$Port/"
Write-Host 'Open that address in a browser. Press Ctrl+C here to close the preview.'
& $sitePython -m http.server $Port --bind 127.0.0.1 --directory $siteDirectory
exit $LASTEXITCODE
