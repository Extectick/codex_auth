$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

$running = Get-Process -Name "ChatGPTSessionManager" -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "Stopping ChatGPTSessionManager.exe process id(s): $($running.Id -join ', ')"
    $running | Stop-Process -Force
    Start-Sleep -Milliseconds 500
}

if (Test-Path ".\dist\ChatGPTSessionManager") {
    Remove-Item -Recurse -Force ".\dist\ChatGPTSessionManager"
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\pyinstaller.exe .\updater\updater.py --onefile --name updater --distpath .\dist --workpath .\build\updater --specpath .\build\updater --clean --noconfirm
.\.venv\Scripts\pyinstaller.exe .\pyinstaller.spec --clean --noconfirm

Write-Host "Build complete: dist\ChatGPTSessionManager.exe and dist\updater.exe"
