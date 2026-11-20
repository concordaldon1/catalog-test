@echo off
title Concord Aldon - Update Inventory
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 update_inventory.py
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        python update_inventory.py
    ) else (
        echo Python was not found. Install Python 3, then try again.
        echo During installation, enable "Add Python to PATH".
        pause
        exit /b 1
    )
)

echo.
pause
