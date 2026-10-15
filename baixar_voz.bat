@echo off
rem Baixa os modelos da aba Voz para C:\IA\modelos\voz (ou %IA_OFF_VOZ_DIR%), usando curl do Windows.
rem   whisper\faster-whisper-small\  (config.json, model.bin ~484 MB, tokenizer.json, vocabulary.txt)
rem   piper\pt_BR-faber-medium.onnx (~63 MB) + .onnx.json
rem Opcional: "baixar_voz.bat base" baixa também o faster-whisper-base (~145 MB, mais rápido e menos preciso).
setlocal
set VOZ=%IA_OFF_VOZ_DIR%
if "%VOZ%"=="" set VOZ=C:\IA\modelos\voz
set HF=https://huggingface.co
call :whisper small || goto erro
if /I "%1"=="base" call :whisper base || goto erro
set PD=%VOZ%\piper
if not exist "%PD%" mkdir "%PD%"
set PV=%HF%/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium
for %%F in (pt_BR-faber-medium.onnx pt_BR-faber-medium.onnx.json) do (
  if not exist "%PD%\%%F" ( echo Baixando %%F... & curl -fL --retry 3 -o "%PD%\%%F.part" "%PV%/%%F" && move /Y "%PD%\%%F.part" "%PD%\%%F" >nul || goto erro )
)
echo OK: modelos de voz em %VOZ%
pause
exit /b 0

:whisper
set WD=%VOZ%\whisper\faster-whisper-%1
if not exist "%WD%" mkdir "%WD%"
for %%F in (config.json model.bin tokenizer.json vocabulary.txt) do (
  if not exist "%WD%\%%F" ( echo Baixando whisper-%1 %%F... & curl -fL --retry 3 -o "%WD%\%%F.part" "%HF%/Systran/faster-whisper-%1/resolve/main/%%F" && move /Y "%WD%\%%F.part" "%WD%\%%F" >nul || exit /b 1 )
)
exit /b 0

:erro
echo ERRO no download (veja a mensagem acima). Rode de novo: arquivos completos são pulados.
pause
exit /b 1
