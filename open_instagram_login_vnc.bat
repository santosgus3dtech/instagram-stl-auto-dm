@echo off
setlocal
set KEY=%USERPROFILE%\.ssh\codex_raspberry_ed25519

echo Iniciando navegador de login no Raspberry...
ssh -i "%KEY%" -o IdentitiesOnly=yes codex@192.168.0.105 "sudo systemctl start instagram-follow-login-vnc.service"

echo Abrindo tunel SSH local em http://127.0.0.1:6080 ...
start "Raspberry Instagram Login Tunnel" powershell -NoExit -Command "ssh -N -i '%KEY%' -o IdentitiesOnly=yes -L 6080:127.0.0.1:6080 codex@192.168.0.105"

timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:6080/vnc.html?host=127.0.0.1&port=6080&autoconnect=true&resize=scale"

echo.
echo Faca login no Instagram pela janela que abriu.
echo Depois de concluir, execute stop_instagram_login_vnc.bat.
pause
