param(
  [string]$EmbeddedPythonDir = "",
  [string]$TesseractDir = "",
  [string]$PopplerDir = "",
  [string]$LibreOfficeDir = "",
  [string]$OutputDir = ".\dist\staged"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
$output = (Resolve-Path -LiteralPath $OutputDir).Path

$backendDir = Join-Path $output "backend"
$runtimeDir = Join-Path $output "runtime"
$toolsDir = Join-Path $output "tools"

New-Item -ItemType Directory -Force -Path $backendDir, $runtimeDir, $toolsDir | Out-Null

$backendFiles = @(
  "app.py",
  "app_flask.py",
  "run_waitress.py",
  "requirements.txt",
  "strata",
  "static",
  "templates",
  "assets"
)

foreach ($item in $backendFiles) {
  $source = Join-Path $root $item
  if (Test-Path $source) {
    Copy-Item -Path $source -Destination $backendDir -Recurse -Force
  }
}

if ($EmbeddedPythonDir) {
  Copy-Item -Path $EmbeddedPythonDir -Destination (Join-Path $runtimeDir "python") -Recurse -Force
}

if ($TesseractDir) {
  Copy-Item -Path $TesseractDir -Destination (Join-Path $toolsDir "tesseract") -Recurse -Force
}

if ($PopplerDir) {
  Copy-Item -Path $PopplerDir -Destination (Join-Path $toolsDir "poppler") -Recurse -Force
}

if ($LibreOfficeDir) {
  Copy-Item -Path $LibreOfficeDir -Destination (Join-Path $toolsDir "libreoffice") -Recurse -Force
}

Write-Host "Staged backend, runtime, and optional tools to $output"
