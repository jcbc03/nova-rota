@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe ( echo .venv nao encontrado. Execute instalar.bat. & pause & exit /b 1 )
echo Instalando dependencias novas (imagem/video, torch CPU)...
.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 ( echo ERRO ao instalar torch. & pause & exit /b 1 )
.venv\Scripts\python.exe -m pip install "diffusers>=0.30" "transformers>=4.44" "accelerate>=0.33" "safetensors>=0.4" "peft>=0.12" "pillow>=10" "imageio>=2.34" "imageio-ffmpeg>=0.5"
if errorlevel 1 ( echo ERRO na instalacao. & pause & exit /b 1 )
echo Atualizacao concluida!
pause
