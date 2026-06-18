@echo off
title Leo Auto Registration Task Manager
cd /d "%~dp0"
set "DATA_DIR=%~dp0data"
echo Starting server...
echo.
echo If you want to close the program, just close this black console window.
echo.

REM Wait 1 second
timeout /t 1 >nobreak 

REM Open browser
start http://localhost:8000

REM Run python server
python server.py

pause
