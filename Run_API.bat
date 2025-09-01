@echo off
setlocal ENABLEEXTENSIONS
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

echo [INFO] Activando entorno virtual...
if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
) else (
  echo [WARN] No se encontro .venv\Scripts\activate.bat
  echo [WARN] Continuo con Python global - no recomendado
)

echo [INFO] Verificando modulo uvicorn...
python -c "import uvicorn" >nul 2>&1
if errorlevel 1 (
  echo [INFO] Instalando fastapi, uvicorn y aiohttp en este entorno...
  python -m pip install --upgrade pip
  python -m pip install fastapi "uvicorn[standard]" aiohttp
)

echo [INFO] Iniciando API en http://127.0.0.1:8000
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
echo [INFO] Server detenido.
pause
