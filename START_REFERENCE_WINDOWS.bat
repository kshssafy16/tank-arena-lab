@echo off
cd /d "%~dp0"
call scripts\start.bat --profile private %*
if errorlevel 1 pause
