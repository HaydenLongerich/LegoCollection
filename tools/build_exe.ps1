# Builds BrickLedger.exe.
#
#   tools\build_exe.ps1            Local exe in the project folder. It runs main.py and
#                                  brickfolio\ from this folder on every start, so normal
#                                  code changes do NOT need a rebuild.
#   tools\build_exe.ps1 -Release   Standalone exe in dist\ for GitHub Releases. Code,
#                                  Sets catalogue and assets are packed inside; rebuild it
#                                  whenever you publish a new version.
#
# Rebuild the local exe only after changing tools\launcher.py, the logo, or when
# tests\test_launcher.py says a new import must be bundled.
param([switch]$Release)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

python -m PyInstaller --version *> $null
if (-not $?) { python -m pip install --disable-pip-version-check "pyinstaller==6.11.1" }

if (-not (Test-Path "assets\brickledger.ico")) { python tools\make_logo.py }

$common = @(
    "--noconfirm", "--clean", "--onefile", "--windowed",
    "--name", "BrickLedger",
    "--icon", "$root\assets\brickledger.ico",
    "--workpath", "$root\build",
    "--specpath", "$root\build"
)

if ($Release) {
    # Only public, read-only files go inside. Never data\ or exports\.
    $extra = @(
        "--paths", "$root",
        "--collect-submodules", "brickfolio",
        "--add-data", "$root\Sets\sets.csv.gz;Sets",
        "--add-data", "$root\Sets\themes.csv.gz;Sets",
        "--add-data", "$root\assets\brickledger.ico;assets",
        "--add-data", "$root\assets\set-images;assets\set-images",
        "--distpath", "$root\dist"
    )
    $output = "$root\dist\BrickLedger.exe"
} else {
    $extra = @("--exclude-module", "brickfolio", "--distpath", "$root")
    $output = "$root\BrickLedger.exe"
}

python -m PyInstaller @common @extra "$root\tools\launcher.py"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

Remove-Item -Recurse -Force "$root\build" -ErrorAction SilentlyContinue
Write-Host "Built $output" -ForegroundColor Green
