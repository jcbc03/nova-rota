@echo off
chcp 65001 >nul
setlocal EnableExtensions
title IA Off - atualizacao para a v3.0
rem Uso: atualizar_v3.bat [pasta_do_app]
rem Padrao: <Area de Trabalho>\IA_Off_v1\ia_off (detectada pelo Windows, inclusive no OneDrive).
rem Log completo: C:\IA\atualizar_v3.log
set "PKG=%~dp0"
if "%PKG:~-1%"=="\" set "PKG=%PKG:~0,-1%"
set "LOG=C:\IA\atualizar_v3.log"
if not exist C:\IA mkdir C:\IA
set "APP=%~1"
if "%APP%"=="" for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; [Environment]::GetFolderPath('Desktop')"`) do set "APP=%%D\IA_Off_v1\ia_off"
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"`) do set "TS=%%T"
set "PY=%APP%\.venv\Scripts\python.exe"
set "BK=C:\IA\backup\v3_%TS%"

call :log "=== IA Off v3.0: inicio %DATE% %TIME% ==="
call :log "Pacote: %PKG%"
call :log "App:    %APP%"
if not exist "%PY%" ( call :log "ERRO: nao achei %PY%. Rode: atualizar_v3.bat [pasta do app que tem .venv]" & goto fim_erro )
tasklist /FI "IMAGENAME eq pythonw.exe" 2>nul | find /I "pythonw.exe" >nul && (
  call :log "AVISO: o IA Off parece estar aberto. Feche o programa e pressione uma tecla."
  pause
)

call :log "[1/6] Backup da configuracao e do codigo atual em %BK%"
mkdir "%BK%" 2>nul
if exist "%APPDATA%\IA_Off_v1\config.json" copy /Y "%APPDATA%\IA_Off_v1\config.json" "%BK%\config.json" >>"%LOG%" 2>&1
robocopy "%APP%\ia_off" "%BK%\ia_off" /E /XD __pycache__ /NFL /NDL /NJH /NP /LOG+:"%LOG%" >nul
if errorlevel 8 ( call :log "ERRO no backup do codigo." & goto fim_erro )
for %%F in (requirements.txt requirements-gpu.txt) do if exist "%APP%\%%F" copy /Y "%APP%\%%F" "%BK%\" >nul
"%PY%" -m pip freeze > "%BK%\pip_freeze_antes.txt" 2>>"%LOG%"
call :log "   OK (config.json fica em %APPDATA%\IA_Off_v1 e nao e alterado)"

call :log "[2/6] Copiando o codigo novo"
robocopy "%PKG%\ia_off" "%APP%\ia_off" /E /XD __pycache__ /NFL /NDL /NJH /NP /LOG+:"%LOG%" >nul
if errorlevel 8 ( call :log "ERRO ao copiar ia_off." & goto fim_erro )
for %%D in (tools docs) do if exist "%PKG%\%%D" robocopy "%PKG%\%%D" "%APP%\%%D" /E /XD __pycache__ /NFL /NDL /NJH /NP /LOG+:"%LOG%" >nul
for %%F in ("%PKG%\*.bat" "%PKG%\*.txt" "%PKG%\*.md") do copy /Y "%%~F" "%APP%\" >nul
call :log "   OK"

call :log "[3/6] Instalando dependencias (faiss-cpu, onnxruntime, faster-whisper, piper-tts...) - pode levar alguns minutos"
rem Trava as versoes JA instaladas de torch/openvino/optimum/transformers etc. (nada e rebaixado nem trocado)
set "CONS=%BK%\constraints.txt"
findstr /I /R "^torch== ^torchvision== ^openvino ^optimum ^nncf== ^transformers== ^huggingface.hub== ^tokenizers== ^diffusers== ^accelerate== ^numpy== ^PySide6" "%BK%\pip_freeze_antes.txt" > "%CONS%"
type "%CONS%" >>"%LOG%"
"%PY%" -m pip install --disable-pip-version-check -r "%APP%\requirements.txt" -c "%CONS%" --extra-index-url https://download.pytorch.org/whl/cpu --log "%LOG%"
if errorlevel 1 ( call :log "ERRO no pip (conflito com as versoes travadas? veja o log). Codigo antigo em %BK%." & goto fim_erro )
"%PY%" -m pip check >>"%LOG%" 2>&1 || call :log "   AVISO: 'pip check' apontou conflitos (detalhes no log)."
call :log "   OK"

call :log "[4/6] Modelos de voz (Whisper small + Piper pt_BR-faber-medium) em C:\IA\modelos\voz"
set IA_NOPAUSE=1
call "%APP%\baixar_voz.bat"
if errorlevel 1 ( call :log "ERRO no download da voz (rode de novo; arquivos completos sao pulados)." & goto fim_erro )
call :log "   OK"

call :log "[5/6] Modelo do ampliador (Real-ESRGAN x4v3, ~5 MB, SHA-256 conferido) em C:\IA\modelos\imagem"
pushd "%APP%"
"%PY%" tools\baixar_ampliador.py >>"%LOG%" 2>&1
set ERR=%ERRORLEVEL%
popd
if not "%ERR%"=="0" ( call :log "ERRO no download do ampliador (o app usa Lanczos ate resolver)." & goto fim_erro )
call :log "   OK"

call :log "[6/6] Verificando importacoes"
pushd "%APP%"
"%PY%" tools\checar_imports.py "%LOG%"
set ERR=%ERRORLEVEL%
popd
if not "%ERR%"=="0" ( call :log "ERRO: alguma importacao falhou (lista acima). Codigo antigo em %BK%." & goto fim_erro )

call :log "=== Atualizacao concluida %DATE% %TIME%. Backup: %BK% ==="
echo.
echo Tudo certo. Abra o IA Off pelo iniciar.bat.
pause
exit /b 0

:fim_erro
call :log "=== Atualizacao INTERROMPIDA. Log: %LOG% ==="
echo.
echo Para voltar o codigo antigo: copie %BK%\ia_off para "%APP%\ia_off".
pause
exit /b 1

:log
echo %~1
>>"%LOG%" echo [%TIME%] %~1
exit /b 0
