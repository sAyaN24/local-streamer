# Builds dist\streammark-publisher.exe -- a single-file, double-clickable
# publisher: auto-detects the capture card and starts publishing, no Python
# install required on the target machine. The primary build target is Linux
# (see build_linux.sh / .github/workflows/build-publisher.yml); this script
# is for building/testing a Windows build of the same executable.
#
# Usage (from anywhere):
#   powershell -ExecutionPolicy Bypass -File stream-publisher\packaging\build_windows.ps1 [-Clean]

param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PublisherDir = Split-Path -Parent $ScriptDir
$RepoRoot = Split-Path -Parent $PublisherDir
$Venv = Join-Path $PublisherDir ".venv"
$VenvPy = Join-Path $Venv "Scripts\python.exe"

if (-not (Test-Path $VenvPy)) {
    Write-Host "==> Creating venv at $Venv (needs Python >= 3.12)"
    python -m venv $Venv
}

Write-Host "==> Installing streammark-shared + streammark-publisher[build]"
& $VenvPy -m pip install --upgrade pip --quiet
Push-Location $RepoRoot
& $VenvPy -m pip install -e ./shared -e "./stream-publisher[build]" --quiet
if ($LASTEXITCODE -ne 0) { Pop-Location; exit 1 }
Pop-Location

if ($Clean) {
    Write-Host "==> Cleaning previous build artifacts"
    Remove-Item -Recurse -Force (Join-Path $ScriptDir "build") -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $ScriptDir "dist") -ErrorAction SilentlyContinue
}

Write-Host "==> Building StreamMarkPublisher.exe with PyInstaller"
Push-Location $ScriptDir
& $VenvPy -m PyInstaller --noconfirm streammark_publisher.spec
$BuildExitCode = $LASTEXITCODE
Pop-Location
if ($BuildExitCode -ne 0) { exit $BuildExitCode }

$DistExe = Join-Path $ScriptDir "dist\streammark-publisher.exe"
if (Test-Path $DistExe) {
    Copy-Item (Join-Path $ScriptDir ".env.example") (Join-Path $ScriptDir "dist\.env.example") -Force
    Write-Host ""
    Write-Host "==> Done: $DistExe"
    Write-Host "    Copy dist\.env.example to dist\.env next to it and fill in"
    Write-Host "    LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET / DEFAULT_ROOM_NAME,"
    Write-Host "    then run the exe (or double-click it)."
} else {
    Write-Host "Build failed -- see PyInstaller output above."
    exit 1
}
