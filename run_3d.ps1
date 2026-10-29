$ErrorActionPreference = 'Stop'
$apiProcess = $null
$frontendPath = Join-Path $PSScriptRoot 'frontend'

function Test-CityMindApi {
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/' -TimeoutSec 2
        return $health.status -eq 'CityMind backend running'
    } catch { return $false }
}

try {
    if (-not (Test-Path -LiteralPath (Join-Path $frontendPath 'node_modules'))) {
        throw 'Install frontend dependencies first: cd frontend; npm install'
    }
    if (-not (Test-CityMindApi)) {
        $pythonExe = (Get-Command python -ErrorAction Stop).Source
        $logPath = Join-Path $PSScriptRoot 'logs'
        New-Item -ItemType Directory -Path $logPath -Force | Out-Null
        $apiProcess = Start-Process -FilePath $pythonExe -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru `
            -ArgumentList @('-m', 'uvicorn', 'backend.api.main:app', '--host', '127.0.0.1', '--port', '8000') `
            -RedirectStandardOutput (Join-Path $logPath 'react-api.stdout.log') `
            -RedirectStandardError (Join-Path $logPath 'react-api.stderr.log')
        $ready = $false
        for ($attempt = 0; $attempt -lt 45; $attempt++) {
            if ($apiProcess.HasExited) { throw 'Backend could not start. See logs/react-api.stderr.log.' }
            if (Test-CityMindApi) { $ready = $true; break }
            Start-Sleep -Seconds 1
        }
        if (-not $ready) { throw 'Backend startup timed out. See logs/react-api.stderr.log.' }
    }
    Write-Host 'CityMind 3D: open http://127.0.0.1:5173. Press Ctrl+C here to stop.' -ForegroundColor Cyan
    Push-Location $frontendPath
    try { npm run dev -- --host 127.0.0.1 --port 5173 --strictPort }
    finally { Pop-Location }
} finally {
    # Only stop the API process started by this launcher; preserve an existing shared API.
    if ($apiProcess -and -not $apiProcess.HasExited) { Stop-Process -Id $apiProcess.Id }
}
