param([ValidateRange(1024, 65535)][int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $PythonPath)) {
    throw 'Create .venv and install the requirements first. See README.md.'
}
$ExistingListener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($ExistingListener) {
    Write-Output "Port $Port is already in use. Open http://127.0.0.1:$Port or choose another port."
    exit 0
}
$LogDirectory = Join-Path $ProjectRoot 'artifacts'
New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
$ServerProcess = Start-Process -FilePath $PythonPath -WorkingDirectory $ProjectRoot `
    -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$Port") `
    -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $LogDirectory 'server-output.log') `
    -RedirectStandardError (Join-Path $LogDirectory 'server-error.log')
Write-Output "CanopyOS starting at http://127.0.0.1:$Port (process $($ServerProcess.Id))."
