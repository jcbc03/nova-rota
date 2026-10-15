@echo off
rem Baixa o stable-diffusion.cpp (CPU, Windows x64) para %APPDATA%\IA_Off_v1\sdcpp (o app também faz isso sozinho)
set DEST=%APPDATA%\IA_Off_v1\sdcpp
set URL=https://github.com/leejet/stable-diffusion.cpp/releases/download/master-964-1d0a58a/sd-master-1d0a58a-bin-win-cpu-x64.zip
if not exist "%DEST%" mkdir "%DEST%"
powershell -NoProfile -Command "Invoke-WebRequest -Uri '%URL%' -OutFile '%DEST%\sd.zip'; Expand-Archive -Force '%DEST%\sd.zip' '%DEST%'; Remove-Item '%DEST%\sd.zip'"
if exist "%DEST%\sd-cli.exe" ( echo OK: %DEST%\sd-cli.exe ) else ( echo ERRO no download. )
pause
