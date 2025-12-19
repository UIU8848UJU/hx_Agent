# 启动此文件会停留在命令行
$ErrorActionPreference = 'Stop'
cd (Split-Path $MyInvocation.MyCommand.Path)\..
& .\\.venv\Scripts\Activate.ps1
Write-Host "✅ venv activated. Try: hx-agent --help"
pwsh -NoExit
