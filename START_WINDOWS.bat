@echo off
cd /d "%~dp0"
call scripts\start.bat %*
if errorlevel 1 pause
