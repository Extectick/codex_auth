$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

$running = Get-Process -Name "ChatGPTSessionManager" -ErrorAction SilentlyContinue
if ($running) {
    throw "Close ChatGPTSessionManager.exe before building. Running process id(s): $($running.Id -join ', ')"
}

if (Test-Path ".\dist\ChatGPTSessionManager") {
    Remove-Item -Recurse -Force ".\dist\ChatGPTSessionManager"
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\pyinstaller.exe .\pyinstaller.spec --clean --noconfirm

Write-Host "Build complete: dist\ChatGPTSessionManager.exe"
