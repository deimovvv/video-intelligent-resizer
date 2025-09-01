@echo on
setlocal ENABLEEXTENSIONS
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"

ffmpeg -version || (echo [ERROR] Falta FFmpeg en PATH & pause & exit /b 1)
python -V || (echo [ERROR] Falta Python en PATH & pause & exit /b 1)

REM --- prueba rápida: 1 ratio y modelo local ---
python scripts\batch_reframe_track_yolo.py ^
  --input .\input ^
  --output .\output ^
  --ratios 9x16 ^
  --detect-every 12 ^
  --ema-alpha 0.08 ^
  --pan-cap-px 16 ^
  --model ".\yolov8n.pt" ^
  --conf 0.35 ^
  --verbose

echo EXITCODE %ERRORLEVEL%
pause
