@echo off
REM GridShare_Setup.exe builder
REM Run this on your main Windows machine to produce the .exe
REM Requires Python 3.10+ and internet access

echo.
echo ============================================
echo   GridShare Setup .exe Builder
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install from python.org
    pause
    exit /b 1
)

echo [1/3] Installing PyInstaller...
pip install pyinstaller -q
if errorlevel 1 (
    echo ERROR: PyInstaller install failed
    pause
    exit /b 1
)
echo       Done.

echo.
echo [2/3] Building GridShare_Setup.exe...
echo       (This takes 30-60 seconds)
echo.
pyinstaller gridshare_setup.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: Build failed. Check output above.
    pause
    exit /b 1
)

echo.
echo [3/3] Checking output...
if exist "dist\GridShare_Setup.exe" (
    echo       SUCCESS
    for %%A in ("dist\GridShare_Setup.exe") do echo       Size: %%~zA bytes
    echo.
    echo ============================================
    echo   dist\GridShare_Setup.exe is ready.
    echo   Copy it to the spare machine and run it.
    echo ============================================
) else (
    echo ERROR: dist\GridShare_Setup.exe not found
)

echo.
pause
