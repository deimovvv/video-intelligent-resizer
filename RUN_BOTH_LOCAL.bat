@echo off
setlocal ENABLEEXTENSIONS
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"

if not exist "logs" mkdir "logs"

echo [INFO] Activating venv (if present)...
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"

echo [CHECK] FFmpeg...
ffmpeg -hide_banner -version >nul 2>&1 || (
  echo [ERROR] FFmpeg not found in PATH. Install it or add to PATH.
  echo. & pause & goto :eof
)

echo [STEP 1/2] RESIZE (FFmpeg)...
python -Xutf8 "scripts\batch_resize_min.py" 1> "logs\resize.out.log" 2> "logs\resize.err.log"
if errorlevel 1 (
  echo [ERROR] Resize step failed. See logs\resize.err.log
  if exist "logs\resize.err.log" (
    echo -------- resize.err.log (last 80 lines) --------
    powershell -NoProfile -Command "Get-Content -Path 'logs\\resize.err.log' -Tail 80"
    echo -----------------------------------------------
  )
  echo. & pause & goto :eof
)
echo [OK] Resize done.

echo.
echo [STEP 2/2] TRACKED (YOLO+CSRT)...
call "RUN_TRACKED_LOCAL.bat"

echo.
echo [DONE] Both steps finished.
pause
