param(
    [string]$PythonExecutable,
    [int]$Port = 7860
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $PythonExecutable) {
    $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundledPython) {
        $PythonExecutable = $bundledPython
    } else {
        $PythonExecutable = (Get-Command python -ErrorAction Stop).Source
    }
}
Push-Location -LiteralPath $projectRoot
try {
    & $PythonExecutable -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
    if ($LASTEXITCODE -ne 0) { throw 'Select Python 3.11+ using -PythonExecutable.' }
    & $PythonExecutable -m recursa.experiments --config configs/smoke.json --output runs
    if ($LASTEXITCODE -ne 0) { throw 'CPU experiment failed; inspect its checkpoint.' }
    & $PythonExecutable -m recursa.server --port $Port
} finally {
    Pop-Location
}
