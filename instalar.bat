@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Criando ambiente virtual (Python 3.11)...
if not exist .venv\Scripts\python.exe (
  py -3.11 -m venv .venv 2>nul || "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" -m venv .venv
)
if not exist .venv\Scripts\python.exe ( echo ERRO: nao foi possivel criar o venv. & pause & exit /b 1 )
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 ( echo ERRO na instalacao. & pause & exit /b 1 )
echo Instalacao concluida! Use iniciar.bat.
pause
