param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Version
)

$ErrorActionPreference = "Stop"

$Project = Split-Path -Parent $MyInvocation.MyCommand.Path
$Prepare = Join-Path $Project "prepare_windows_release.py"
$Work = Join-Path $Project ".release_work"
$Stage = Join-Path $Work "source_stage"
$AppBuild = Join-Path $Work "app_build"
$AppDist = Join-Path $Work "app_dist"
$SpecDir = Join-Path $Work "spec"
$PackageRoot = Join-Path $Work "package"
$ReleaseDir = Join-Path $Project "release"

if ($Version -match '[\\/:*?"<>|\s]') {
    throw "Version contains characters unsafe in a release filename."
}

$VenvPython = Join-Path $Project ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "Creating isolated public-release virtual environment..."
    python -m venv (Join-Path $Project ".venv")

    if ($LASTEXITCODE -ne 0) {
        throw "Could not create the public-release virtual environment."
    }
}

$Python = $VenvPython

foreach ($Required in @(
    $Prepare,
    (Join-Path $Project "requirements.txt"),
    (Join-Path $Project "LICENSE"),
    (Join-Path $Project "README.md"),
    (Join-Path $Project "assets\wyrmmango_icon.png"),
    (Join-Path $Project "src\app.py"),
    (Join-Path $Project "src\database.py"),
    (Join-Path $Project "src\import_archive.py"),
    (Join-Path $Project "src\import_chatgpt.py"),
    (Join-Path $Project "src\import_claude.py"),
    (Join-Path $Project "src\import_gmail.py")
)) {
    if (-not (Test-Path -LiteralPath $Required)) {
        throw "Required release source is missing: $Required"
    }
}

Write-Host "===== RELEASE BUILD ENVIRONMENT ====="

& $Python --version

if ($LASTEXITCODE -ne 0) {
    throw "Release Python is not available."
}

Write-Host "Installing/verifying declared application requirements..."

& $Python -m pip install -r (Join-Path $Project "requirements.txt")

if ($LASTEXITCODE -ne 0) {
    throw "Application dependency installation failed."
}

Write-Host "Installing/verifying pinned PyInstaller 6.21.0..."

& $Python -m pip install "pyinstaller==6.21.0"

if ($LASTEXITCODE -ne 0) {
    throw "Pinned PyInstaller installation failed."
}

$PyInstallerHelp = (& $Python -m PyInstaller --help 2>&1) -join "`n"

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is not available."
}

if ($PyInstallerHelp -notmatch "--hide-console") {
    throw "Installed PyInstaller does not support --hide-console."
}

& $Python -m PyInstaller --version

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller version query failed."
}

Write-Host "Console-enabled hidden-console packaging support: PASS"

if (Test-Path -LiteralPath $Work) {
    Remove-Item -LiteralPath $Work -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $Work | Out-Null
New-Item -ItemType Directory -Force -Path $SpecDir | Out-Null
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null

Write-Host ""
Write-Host "===== PREPARE DISPOSABLE BUILD STAGE ====="

& $Python $Prepare --stage $Stage

if ($LASTEXITCODE -ne 0) {
    throw "Windows release stage preparation failed."
}

Write-Host ""
Write-Host "===== BUILD SINGLE-EXECUTABLE WYRM MANGO ====="

$IconIco = Join-Path $Stage "assets\wyrmmango.ico"
$IconPng = Join-Path $Stage "assets\wyrmmango_icon.png"

$AppArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--console",
    "--hide-console", "hide-early",
    "--name", "WyrmMango",
    "--distpath", $AppDist,
    "--workpath", $AppBuild,
    "--specpath", $SpecDir,
    "--paths", (Join-Path $Stage "src"),
    "--hidden-import", "database",
    "--hidden-import", "import_archive",
    "--hidden-import", "import_chatgpt",
    "--hidden-import", "import_claude",
    "--hidden-import", "import_gmail",
    "--add-data", ($IconPng + ";assets")
)

if (Test-Path -LiteralPath $IconIco) {
    $AppArgs += @(
        "--icon",
        $IconIco
    )
}

$AppArgs += @(
    (Join-Path $Stage "src\app.py")
)

& $Python @AppArgs

if ($LASTEXITCODE -ne 0) {
    throw "WyrmMango application PyInstaller build failed."
}

$AppExe = Join-Path $AppDist "WyrmMango.exe"

if (-not (Test-Path -LiteralPath $AppExe)) {
    throw "WyrmMango EXE was not produced."
}

Write-Host "WyrmMango single EXE: PASS"

Write-Host ""
Write-Host "===== SAME-EXE IMPORTER SELF-DISPATCH SMOKE TEST ====="

$SelfDispatchOutput = @(
    & $AppExe "--wyrmmango-importer" "--self-test" 2>&1
)

$SelfDispatchExit = $LASTEXITCODE

$SelfDispatchOutput | ForEach-Object {
    Write-Host $_
}

if ($SelfDispatchExit -ne 0) {
    throw "Built WyrmMango.exe importer self-dispatch failed."
}

$SelfDispatchText = $SelfDispatchOutput -join "`n"

if (
    $SelfDispatchText -notmatch
    "Unified importer dispatcher self-test: PASS"
) {
    throw "Built WyrmMango.exe importer self-dispatch output gate failed."
}

Write-Host "Same-executable importer child launch: PASS"
Write-Host "Separate helper executable required: NO"

Write-Host ""
Write-Host "===== PACKAGE RELEASE CANDIDATE ====="

$PackageName = "WyrmMango-$Version-Windows-x64"
$PackageDir = Join-Path $PackageRoot $PackageName
$ZipPath = Join-Path $ReleaseDir ($PackageName + ".zip")

New-Item -ItemType Directory -Force -Path $PackageDir | Out-Null

Copy-Item `
    -LiteralPath $AppExe `
    -Destination (Join-Path $PackageDir "WyrmMango.exe") `
    -Force

Copy-Item `
    -LiteralPath (Join-Path $Project "LICENSE") `
    -Destination (Join-Path $PackageDir "LICENSE") `
    -Force

Copy-Item `
    -LiteralPath (Join-Path $Project "README.md") `
    -Destination (Join-Path $PackageDir "README.md") `
    -Force

$ExeHash = (
    Get-FileHash `
        -LiteralPath $AppExe `
        -Algorithm SHA256
).Hash

$ChecksumPath = Join-Path $PackageDir "SHA256.txt"

$ChecksumText = @"
WyrmMango $Version Windows x64
SHA256  $ExeHash  WyrmMango.exe
"@

[System.IO.File]::WriteAllText(
    $ChecksumPath,
    $ChecksumText,
    [System.Text.Encoding]::ASCII
)

if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

Compress-Archive `
    -Path (Join-Path $PackageDir "*") `
    -DestinationPath $ZipPath `
    -CompressionLevel Optimal

$ZipHash = (
    Get-FileHash `
        -LiteralPath $ZipPath `
        -Algorithm SHA256
).Hash

Write-Host ""
Write-Host "============================================"
Write-Host "WYRM MANGO WINDOWS BUILD COMPLETE"
Write-Host "============================================"
Write-Host "Version:     $Version"
Write-Host "Architecture: single EXE / same-executable importer dispatch"
Write-Host "Executable:  $AppExe"
Write-Host "EXE SHA256:  $ExeHash"
Write-Host "Release ZIP: $ZipPath"
Write-Host "ZIP SHA256:  $ZipHash"
Write-Host ""
Write-Host "Do NOT publish yet. Run packaged Gmail regression acceptance first."
