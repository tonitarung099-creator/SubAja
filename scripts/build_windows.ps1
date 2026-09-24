$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt
python scripts/download_models.py
python -m pytest -q
python -m PyInstaller --noconfirm --clean build/SubAja.spec

if (!(Test-Path "dist/SubAja/SubAja.exe")) {
    throw "Build gagal: dist/SubAja/SubAja.exe tidak ditemukan"
}

@"
SubAja Portable

Cara pakai:
1. Extract seluruh folder SubAja.
2. Jalankan SubAja.exe.
3. Jangan hapus folder _internal.
4. Tidak perlu installer atau hak Administrator.
"@ | Set-Content -Path "dist/SubAja/BACA_DULU.txt" -Encoding UTF8

$zip = "dist/SubAja-Portable.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path "dist/SubAja" -DestinationPath $zip -CompressionLevel Optimal

Write-Host "Build selesai:"
Write-Host "  Folder : dist/SubAja/"
Write-Host "  EXE    : dist/SubAja/SubAja.exe"
Write-Host "  ZIP    : dist/SubAja-Portable.zip"
