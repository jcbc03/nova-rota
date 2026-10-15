@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe ( echo .venv nao encontrado. Execute instalar.bat primeiro. & pause & exit /b 1 )
echo Instalando suporte a GPU Intel (OpenVINO)...
rem torch e torchvision precisam vir do indice CPU e com versoes casadas
.venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 ( echo ERRO ao instalar torch/torchvision. & pause & exit /b 1 )
.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-gpu.txt --extra-index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 ( echo ERRO na instalacao. & pause & exit /b 1 )
echo.
echo Dispositivos OpenVINO detectados:
.venv\Scripts\python.exe -c "import openvino as ov; print(ov.Core().available_devices)"
echo (Se 'GPU' nao aparecer, atualize o driver grafico Intel.)
pause
