<#
APEX standalone local Windows bootstrap.
Run from apex-animation-engine with:
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_local_windows.ps1
Or for tests and a short render:
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_local_windows.ps1 -QuickTests -RenderSmoke

This script uses a virtual environment in THIS clone only. It does not deploy,
touch Claude's branch, run paid AI calls, or alter other local projects.
#>
param(
    [switch]$QuickTests,
    [switch]$FullTests,
    [switch]$RenderSmoke
)
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

function Assert-Exit([string]$Description) {
    if ($LASTEXITCODE -ne 0) { throw "$Description failed (exit $LASTEXITCODE)" }
}
function Requires([string]$CommandName, [string]$InstallHint) {
    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        throw "$CommandName is missing. $InstallHint. Restart PowerShell afterward."
    }
}

if ($env:OS -ne "Windows_NT") { throw "This script targets Windows PowerShell. Use the README Linux/macOS instructions on other systems." }
Requires "py" "Run: winget install -e --id Python.Python.3.12"
Requires "ffmpeg" "Run: winget install -e --id Gyan.FFmpeg"
Requires "ffprobe" "Install FFmpeg (winget install -e --id Gyan.FFmpeg)"
& py -3.12 --version
Assert-Exit "Python 3.12 selection"

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating isolated APEX Python environment..."
    & py -3.12 -m venv ".venv"
    Assert-Exit "Virtual environment creation"
}
Write-Host "Installing APEX and test dependencies into .venv..."
& $VenvPython -m pip install --upgrade pip
Assert-Exit "pip upgrade"
& $VenvPython -m pip install -e ".[dev]"
Assert-Exit "APEX dependency installation"

New-Item -ItemType Directory -Force (Join-Path $Root "out") | Out-Null
Write-Host "Checking CORE RUN project schema and local CLI..."
& $VenvPython -m apex.cli validate "examples\core_run.json"
Assert-Exit "CORE RUN schema validation"
& $VenvPython -m apex.cli ai-budget
Assert-Exit "AI budget command"

if ($QuickTests) {
    Write-Host "Running focused engine tests..."
    & $VenvPython -m pytest -q "tests\test_runtime.py"
    Assert-Exit "Focused engine tests"
}
if ($FullTests) {
    Write-Host "Running complete engine tests; this can take several minutes..."
    & $VenvPython -m pytest -q
    Assert-Exit "Full engine test suite"
}
if ($RenderSmoke) {
    Write-Host "Rendering a SHORT smoke-test animation, not the full CORE RUN film..."
    & $VenvPython -m apex.cli render "examples\motion_test.json" -o "out\local_smoke.mp4" --preset draft --qa-json "out\local_smoke_qa.json"
    Assert-Exit "Smoke render and QA"
    if (-not (Test-Path "out\local_smoke.mp4")) { throw "Render exited without creating out\local_smoke.mp4" }
    & ffprobe -v error -show_entries format=duration,size -of json "out\local_smoke.mp4"
    Assert-Exit "Smoke MP4 decode metadata"
}
Write-Host ""
Write-Host "APEX local bootstrap completed."
Write-Host "Open this folder in Codex: $Root"
Write-Host "Run the API: .\.venv\Scripts\apex.exe serve --port 8077"
Write-Host "API docs: http://127.0.0.1:8077/docs"
Write-Host "Preview: .\.venv\Scripts\apex.exe film examples\core_run.json -o out\core_run_draft.mp4 --preset draft"
Write-Host "Paid AI planning is OFF unless you explicitly enable/configure it."
