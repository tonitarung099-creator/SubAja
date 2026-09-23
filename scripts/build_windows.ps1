$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt
python scripts/download_models.py
python -m pytest -q
python -m PyInstaller --noconfirm --clean build/SubAja.spec

Write-Host "Build selesai: dist/SubAja.exe"
