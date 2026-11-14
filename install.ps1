# pico installer — Windows PowerShell. No admin, no pip, no network.
$ErrorActionPreference = "Stop"
$src  = Split-Path -Parent $MyInvocation.MyCommand.Path
$dest = if ($env:PICO_HOME) { $env:PICO_HOME } else { Join-Path $HOME ".pico" }

$py = (python --version) 2>&1
if ($LASTEXITCODE -ne 0) { throw "python is required on PATH" }
Write-Host "found $py"

New-Item -ItemType Directory -Force -Path "$dest\rules","$dest\templates" | Out-Null
Copy-Item -Force "$src\pico.py" (Join-Path $HOME "pico.py")
Copy-Item -Recurse -Force "$src\pico" "$dest\pkg"
Copy-Item -Force "$src\packs\*.py" "$dest\rules\"
Copy-Item -Force "$src\templates\*.txt" "$dest\templates\"
Copy-Item -Recurse -Force "$src\web" "$dest\web"

Write-Host "installed to $dest"
Write-Host "run:  python $HOME\pico.py"
Write-Host "ui:   python $HOME\pico.py --ui"
