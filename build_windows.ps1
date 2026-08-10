$ErrorActionPreference = "Stop"

$Project = (Get-Location).Path
$Version = "0.1.0"
$Py = Join-Path $Project ".venv\Scripts\python.exe"

if (-not (Test-Path ".\src\app.py")) {
    throw "Run this script from the root of D:\WyrmMango-Public."
}

if (-not (Test-Path ".\.venv")) {
    Write-Host "Creating clean release virtual environment..."
    python -m venv .venv
}

Write-Host "Installing build dependencies..."
& $Py -m pip install --upgrade pip
& $Py -m pip install -r .\requirements.txt
& $Py -m pip install pyinstaller

Write-Host "Cleaning old build output..."
Remove-Item .\build -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item .\dist -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item .\release -Recurse -Force -ErrorAction SilentlyContinue

New-Item -ItemType Directory -Path .\build\helper -Force | Out-Null
New-Item -ItemType Directory -Path .\build\specs -Force | Out-Null

Write-Host ""
Write-Host "Building embedded importer..."
& $Py -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --console `
    --name WyrmMangoImporter `
    --distpath .\build\helper `
    --workpath .\build\importer-work `
    .\src\import_chatgpt.py

$ImporterExe = ".\build\helper\WyrmMangoImporter.exe"
if (-not (Test-Path $ImporterExe)) {
    throw "Importer build failed: $ImporterExe not found."
}

Write-Host ""
Write-Host "Building WyrmMango.exe..."
& $Py -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name WyrmMango `
    --icon .\assets\wyrmmango.ico `
    --add-data ".\assets\wyrmmango_icon.png;assets" `
    --add-binary "$ImporterExe;." `
    --distpath .\dist `
    --workpath .\build\app-work `
    .\src\app.py

$Exe = ".\dist\WyrmMango.exe"
if (-not (Test-Path $Exe)) {
    throw "Application build failed: $Exe not found."
}

Write-Host ""
Write-Host "Creating release package..."
$ReleaseDir = ".\release\WyrmMango-$Version-Windows-x64"
New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null

Copy-Item $Exe "$ReleaseDir\WyrmMango.exe" -Force
Copy-Item .\LICENSE "$ReleaseDir\LICENSE" -Force
Copy-Item .\README.md "$ReleaseDir\README.md" -Force

$Hash = (Get-FileHash $Exe -Algorithm SHA256).Hash
@"
WyrmMango $Version Windows x64
SHA256  $Hash  WyrmMango.exe
"@ | Set-Content "$ReleaseDir\SHA256.txt"

$Zip = ".\release\WyrmMango-$Version-Windows-x64.zip"
Compress-Archive -Path "$ReleaseDir\*" -DestinationPath $Zip -Force

Write-Host ""
Write-Host "============================================"
Write-Host "WYRM MANGO WINDOWS BUILD COMPLETE"
Write-Host "============================================"
Write-Host "Executable: $Project\dist\WyrmMango.exe"
Write-Host "Release ZIP: $Project\release\WyrmMango-$Version-Windows-x64.zip"
Write-Host "SHA256: $Hash"
Write-Host ""
Write-Host "Do NOT publish yet. Test the EXE first."
