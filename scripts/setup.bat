@echo off
setlocal
cd /d "%~dp0.."
py -3 -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11+ required'" || exit /b 1
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -c "import socket, http.server; print('Ready: no packages to download.')"
