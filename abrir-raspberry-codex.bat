@echo off
setlocal

set "KEY=%USERPROFILE%\.ssh\codex_raspberry_ed25519"

if not exist "%KEY%" (
  echo Chave SSH nao encontrada:
  echo %KEY%
  echo.
  echo Rode novamente a configuracao do usuario codex no Raspberry.
  pause
  exit /b 1
)

start "Raspberry SSH - Codex" powershell.exe -NoExit -Command "ssh -t -i '%KEY%' -o IdentitiesOnly=yes codex@192.168.0.105 'cd /opt/instagram-stl-auto-dm; bash -l'"
