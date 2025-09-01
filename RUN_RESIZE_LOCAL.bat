@echo off
setlocal ENABLEEXTENSIONS
title Batch Resize (FFmpeg) - Local

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

echo [INFO] Activando venv (si existe)...
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"

echo [CHECK] FFmpeg...
ffmpeg -version >nul 2>&1 || (echo [ERROR] Falta FFmpeg en PATH & pause & exit /b 1)

echo [INFO] Instalando deps minimos (si faltan)...
python -c "import numpy"  >nul 2>&1 || python -m pip install --upgrade pip
python -c "import numpy"  >nul 2>&1 || python -m pip install numpy
python -c "import cv2"    >nul 2>&1 || python -m pip install opencv-python-headless

echo.
echo [INFO] Procesando videos de .\input hacia .\output (FFmpeg center-crop)...
python "scripts\batch_resize_min.py"
set "ERR=%ERRORLEVEL%"

echo.
if "%ERR%"=="0" (echo [DONE] Resize completado.) else (echo [WARN] Codigo %ERR%)
pause
