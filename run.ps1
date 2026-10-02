$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $taskPython) {
    & $taskPython -m streamlit run app.py --server.address=127.0.0.1
} else {
    $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    $taskDeps = Join-Path (Split-Path $PSScriptRoot -Parent) '.codex_tmp\quote-deps'
    if ((Test-Path -LiteralPath $bundledPython) -and (Test-Path -LiteralPath $taskDeps)) {
        & $bundledPython (Join-Path $PSScriptRoot 'dev_runner.py')
    } else {
        Write-Host 'Create a Python 3.12+ virtual environment and install requirements.txt first. See README.md.'
        exit 1
    }
}
