@echo off
setlocal
set KEY=%USERPROFILE%\.ssh\codex_raspberry_ed25519

echo Parando navegador de login Meta/Facebook no Raspberry...
ssh -i "%KEY%" -o IdentitiesOnly=yes codex@192.168.0.105 "sudo systemctl stop instagram-follow-login-vnc.service"
echo Pronto. Voce tambem pode fechar a janela do tunel SSH.
pause
