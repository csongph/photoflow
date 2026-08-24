@echo off
setlocal
cd /d "%~dp0"
echo Starting PhotoFlow...

if not exist ".venv\Scripts\activate.bat" (
  echo Virtual environment not found. Run setup.bat first.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"

python -c "import socket; s=socket.socket(); code=s.connect_ex(('127.0.0.1',8000)); s.close(); raise SystemExit(1 if code==0 else 0)"
if errorlevel 1 (
  echo Port 8000 is already in use. Close the other app or change LOCAL_PORT in .env.
  pause
  exit /b 1
)

start "" http://127.0.0.1:8000
uvicorn local.app.main:app --host 127.0.0.1 --port 8000
pause

