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
try {
    if (-not (Test-Path "node_modules")) {
        pnpm install
    }
    pnpm dev
}
finally {
    Pop-Location
}
