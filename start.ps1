# ──────────────────────────────────────────────────────────────
#  DataCleaner AI — Windows Startup Script (PowerShell)
#  Usage:  .\start.ps1              (starts both backend + frontend)
#          .\start.ps1 backend      (backend only)
#          .\start.ps1 frontend     (frontend only)
#          .\start.ps1 install      (install all dependencies)
#          .\start.ps1 stop         (kill running servers)
# ──────────────────────────────────────────────────────────────

param(
    [Parameter(Position=0)]
    [ValidateSet("all", "start", "backend", "frontend", "install", "stop", "help")]
    [string]$Command = "all"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir  = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$BackendPort = 8000
$FrontendPort = 3000

# ── Helpers ──
function Write-Banner {
    Write-Host ""
    Write-Host "  ✨ DataCleaner AI" -ForegroundColor Magenta
    Write-Host "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host "  AI-Powered Data Cleaning & EDA Pipeline"
    Write-Host "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step($msg)    { Write-Host "`n  ▶ $msg" -ForegroundColor Cyan }
function Write-Ok($msg)      { Write-Host "  ✔ $msg" -ForegroundColor Green }
function Write-Warn($msg)    { Write-Host "  ⚠ $msg" -ForegroundColor Yellow }
function Write-Err($msg)     { Write-Host "  ✖ $msg" -ForegroundColor Red }
function Write-Info($msg)    { Write-Host "  ℹ $msg" -ForegroundColor Blue }

# ── Prereqs ──
function Test-Prerequisites {
    Write-Step "Checking prerequisites..."

    # Python
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) {
        Write-Err "Python 3.11+ required. Install from https://python.org"
        exit 1
    }
    $pyVer = (python --version 2>&1) -replace "Python ",""
    Write-Ok "Python $pyVer found"

    # Node
    $nd = Get-Command node -ErrorAction SilentlyContinue
    if (-not $nd) {
        Write-Err "Node.js 18+ required. Install from https://nodejs.org"
        exit 1
    }
    Write-Ok "Node.js $(node --version) found"

    # npm
    $np = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $np) {
        Write-Err "npm is required."
        exit 1
    }
    Write-Ok "npm $(npm --version) found"
}

# ── Env Check ──
function Test-Environment {
    Write-Step "Checking environment..."

    $envFile = Join-Path $BackendDir ".env"
    $envExample = Join-Path $BackendDir ".env.example"

    if (-not (Test-Path $envFile)) {
        if (Test-Path $envExample) {
            Copy-Item $envExample $envFile
            Write-Warn "Created backend/.env from .env.example"
            Write-Warn "→ Add your GROQ_API_KEY to backend/.env"
        } else {
            Write-Err "No .env or .env.example in backend/"
            exit 1
        }
    } else {
        $content = Get-Content $envFile -Raw
        if ($content -match "GROQ_API_KEY=your_" -or $content -match "GROQ_API_KEY=`$") {
            Write-Warn "GROQ_API_KEY not configured — pipeline will use fallback mode"
        } else {
            Write-Ok "backend/.env configured"
        }
    }
}

# ── Install ──
function Install-Dependencies {
    Write-Step "Installing backend dependencies..."
    Push-Location $BackendDir

    # Create venv if needed
    if (-not (Test-Path "venv") -and -not (Test-Path ".venv")) {
        python -m venv venv
        Write-Ok "Created Python virtual environment"
    }

    # Activate venv
    $activateScript = Join-Path $BackendDir "venv\Scripts\Activate.ps1"
    if (-not (Test-Path $activateScript)) {
        $activateScript = Join-Path $BackendDir ".venv\Scripts\Activate.ps1"
    }
    if (Test-Path $activateScript) {
        & $activateScript
    }

    pip install -r requirements.txt --quiet 2>&1 | Out-Null
    Write-Ok "Backend dependencies installed"
    Pop-Location

    Write-Step "Installing frontend dependencies..."
    Push-Location $FrontendDir
    npm install --silent 2>&1 | Out-Null
    Write-Ok "Frontend dependencies installed"
    Pop-Location
}

# ── Start Backend ──
function Start-Backend {
    Write-Step "Starting backend (FastAPI on port $BackendPort)..."

    # Kill existing
    $existing = Get-NetTCPConnection -LocalPort $BackendPort -ErrorAction SilentlyContinue
    if ($existing) {
        $existing | ForEach-Object {
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
        }
        Write-Warn "Killed existing process on port $BackendPort"
        Start-Sleep -Seconds 1
    }

    # Activate venv
    $activateScript = Join-Path $BackendDir "venv\Scripts\Activate.ps1"
    if (-not (Test-Path $activateScript)) {
        $activateScript = Join-Path $BackendDir ".venv\Scripts\Activate.ps1"
    }
    if (Test-Path $activateScript) {
        & $activateScript
    }

    # Start uvicorn as a background job
    $job = Start-Job -ScriptBlock {
        param($dir, $port)
        Set-Location $dir
        # Activate venv inside job
        $activate = Join-Path $dir "venv\Scripts\Activate.ps1"
        if (-not (Test-Path $activate)) { $activate = Join-Path $dir ".venv\Scripts\Activate.ps1" }
        if (Test-Path $activate) { & $activate }
        python -m uvicorn main:app --reload --host 0.0.0.0 --port $port 2>&1
    } -ArgumentList $BackendDir, $BackendPort

    $job.Id | Out-File (Join-Path $ProjectRoot ".backend.jobid") -Force
    Start-Sleep -Seconds 3

    Write-Ok "Backend running  → http://localhost:$BackendPort"
    Write-Ok "API Docs         → http://localhost:$BackendPort/docs"

    return $job
}

# ── Start Frontend ──
function Start-Frontend {
    Write-Step "Starting frontend (Next.js on port $FrontendPort)..."

    # Kill existing
    $existing = Get-NetTCPConnection -LocalPort $FrontendPort -ErrorAction SilentlyContinue
    if ($existing) {
        $existing | ForEach-Object {
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
        }
        Write-Warn "Killed existing process on port $FrontendPort"
        Start-Sleep -Seconds 1
    }

    $job = Start-Job -ScriptBlock {
        param($dir)
        Set-Location $dir
        npm run dev 2>&1
    } -ArgumentList $FrontendDir

    $job.Id | Out-File (Join-Path $ProjectRoot ".frontend.jobid") -Force
    Start-Sleep -Seconds 4

    Write-Ok "Frontend running → http://localhost:$FrontendPort"

    return $job
}

# ── Stop ──
function Stop-Servers {
    Write-Step "Stopping servers..."

    $bjFile = Join-Path $ProjectRoot ".backend.jobid"
    $fjFile = Join-Path $ProjectRoot ".frontend.jobid"

    if (Test-Path $bjFile) {
        $id = Get-Content $bjFile
        Stop-Job -Id $id -ErrorAction SilentlyContinue
        Remove-Job -Id $id -Force -ErrorAction SilentlyContinue
        Remove-Item $bjFile -Force
        Write-Ok "Backend job stopped"
    }

    if (Test-Path $fjFile) {
        $id = Get-Content $fjFile
        Stop-Job -Id $id -ErrorAction SilentlyContinue
        Remove-Job -Id $id -Force -ErrorAction SilentlyContinue
        Remove-Item $fjFile -Force
        Write-Ok "Frontend job stopped"
    }

    # Kill by port
    @($BackendPort, $FrontendPort) | ForEach-Object {
        $conns = Get-NetTCPConnection -LocalPort $_ -ErrorAction SilentlyContinue
        $conns | ForEach-Object {
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }

    Write-Ok "All servers stopped"
}

# ── Main ──
Write-Banner

switch ($Command) {
    "install" {
        Test-Prerequisites
        Install-Dependencies
        Test-Environment
        Write-Host ""
        Write-Ok "All dependencies installed!"
        Write-Info "Run .\start.ps1 to start the project."
    }

    "backend" {
        Test-Prerequisites
        Test-Environment
        $job = Start-Backend
        Write-Host ""
        Write-Ok "Backend is running!"
        Write-Host "  Press Ctrl+C to stop.`n"
        try { Wait-Job $job } catch { Stop-Servers }
    }

    "frontend" {
        $job = Start-Frontend
        Write-Host ""
        Write-Ok "Frontend is running!"
        Write-Host "  Press Ctrl+C to stop.`n"
        try { Wait-Job $job } catch { Stop-Servers }
    }

    "stop" {
        Stop-Servers
    }

    "help" {
        Write-Host "Usage: .\start.ps1 [command]"
        Write-Host ""
        Write-Host "  install    Install all dependencies (pip + npm)"
        Write-Host "  backend    Start backend only"
        Write-Host "  frontend   Start frontend only"
        Write-Host "  stop       Stop all running servers"
        Write-Host "  start/all  Start both (default)"
        Write-Host ""
    }

    { $_ -in "all", "start" } {
        Test-Prerequisites
        Test-Environment

        # Auto-install if missing
        if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
            Write-Warn "Dependencies not found — installing..."
            Install-Dependencies
        }

        $bJob = Start-Backend
        $fJob = Start-Frontend

        Write-Host ""
        Write-Host "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
        Write-Host "   🚀 DataCleaner AI is ready!" -ForegroundColor Green
        Write-Host "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
        Write-Host ""
        Write-Host "  Frontend  → http://localhost:$FrontendPort" -ForegroundColor White
        Write-Host "  Backend   → http://localhost:$BackendPort" -ForegroundColor White
        Write-Host "  API Docs  → http://localhost:$BackendPort/docs" -ForegroundColor White
        Write-Host ""
        Write-Host "  Press Ctrl+C to stop both servers.`n"

        # Wait and handle Ctrl+C
        try {
            while ($true) {
                Start-Sleep -Seconds 2

                # Stream job output
                @($bJob, $fJob) | ForEach-Object {
                    if ($_) { Receive-Job $_ -ErrorAction SilentlyContinue }
                }
            }
        }
        catch {
            # Ctrl+C pressed
        }
        finally {
            Write-Host ""
            Stop-Servers
        }
    }
}
