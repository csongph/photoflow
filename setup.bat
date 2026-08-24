@echo off
setlocal
cd /d "%~dp0"
echo PhotoFlow V1 Setup
echo ==================

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Please install Python 3.11 or newer from https://www.python.org/downloads/windows/
  pause
  exit /b 1
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 (
  echo PhotoFlow requires Python 3.11 or newer.
  python --version
  pause
  exit /b 1
)

if not exist ".env" copy ".env.example" ".env" >nul
if not exist ".venv" python -m venv ".venv"
if errorlevel 1 (
  echo Could not create virtual environment.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r "local\requirements.txt"
if errorlevel 1 (
  echo Dependency installation failed.
  pause
  exit /b 1
)

python -m local.app.setup_local
if errorlevel 1 (
  echo Local database initialization failed.
  pause
  exit /b 1
)

echo.
echo Setup complete.
echo Edit .env to add CLOUD_API_URL, Google OAuth credentials, and gallery URL when ready.
pause
