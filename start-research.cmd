@echo off
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (
  python research_server.py
) else (
  "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" research_server.py
)
pause
