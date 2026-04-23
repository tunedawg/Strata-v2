param(
  [string]$Configuration = "Release",
  [string]$Runtime = "win10-x64",
  [string]$EmbeddedPythonDir = "",
  [string]$TesseractDir = "",
  [string]$PopplerDir = "",
  [string]$LibreOfficeDir = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$desktopProject = Join-Path $root "desktop\Strata.Desktop\Strata.Desktop.csproj"
$publishDir = Join-Path $root "dist\desktop-publish"

dotnet publish $desktopProject -c $Configuration -r $Runtime -p:PublishSingleFile=false -p:SelfContained=false -o $publishDir

& (Join-Path $PSScriptRoot "stage_runtime.ps1") `
  -EmbeddedPythonDir $EmbeddedPythonDir `
  -TesseractDir $TesseractDir `
  -PopplerDir $PopplerDir `
  -LibreOfficeDir $LibreOfficeDir `
  -OutputDir (Join-Path $root "dist\msix-layout")

Write-Host "Desktop host published to $publishDir"
Write-Host "Backend/runtime staged to dist\msix-layout"
Write-Host "Next step: package the publish output plus staged runtime with your enterprise signing/MSIX pipeline."
