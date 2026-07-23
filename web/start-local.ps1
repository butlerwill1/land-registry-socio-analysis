$ErrorActionPreference = "Stop"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    $bundledNode = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin"
    if (-not (Test-Path (Join-Path $bundledNode "node.exe"))) {
        throw "Node.js 20.19 or newer is required. Install Node.js, then run this script again."
    }
    $env:PATH = "$bundledNode;$env:PATH"
}

if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
    throw "pnpm is required. Install it with 'corepack enable', then run this script again."
}

Push-Location $PSScriptRoot
$apiProcess = $null
try {
    if (-not (Test-Path "node_modules")) {
        pnpm install
    }
    $python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        throw "The repository Python environment is missing. Create .venv and install backend[test]."
    }
    $env:ATLAS_ALLOW_DEV_ENTITLEMENTS = "true"
    $env:ATLAS_PRO_ACCESS_CODE = "local-pro"
    $env:ATLAS_PRO_ACCESS_SIGNING_SECRET = "local-development-signing-secret-at-least-32-chars"
    $env:ATLAS_PRO_ACCESS_EXPIRES_AT = "2099-01-01T00:00:00Z"
    $apiProcess = Start-Process `
        -FilePath $python `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--app-dir", "..\backend", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $PSScriptRoot `
        -WindowStyle Hidden `
        -PassThru
    $apiReady = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($apiProcess.HasExited) {
            throw "FastAPI exited before it became ready."
        }
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 1
            if ($health.status -eq "ok") {
                $apiReady = $true
                break
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $apiReady) {
        throw "FastAPI did not become ready within 30 seconds."
    }
    pnpm dev
}
finally {
    if ($null -ne $apiProcess -and -not $apiProcess.HasExited) {
        Stop-Process -Id $apiProcess.Id
    }
    Pop-Location
}
