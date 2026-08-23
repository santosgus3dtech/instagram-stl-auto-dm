#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/instagram-stl-auto-dm}"
APP_USER="${APP_USER:-${SUDO_USER:-pi}}"
APP_GROUP="${APP_GROUP:-$(id -gn "$APP_USER")}"
SERVICE_NAME="instagram-stl-auto-dm.service"

if [[ $EUID -ne 0 ]]; then
  echo "Run this script with sudo."
  exit 1
fi

apt-get update
apt-get install -y git python3 python3-venv python3-pip

mkdir -p "$APP_DIR"
chown -R "$APP_USER:$APP_GROUP" "$APP_DIR"

sudo -u "$APP_USER" python3 -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

if [[ ! -f "$APP_DIR/.env" ]]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  chown "$APP_USER:$APP_GROUP" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo "Created $APP_DIR/.env. Edit it before starting the service."
fi

cp "$APP_DIR/deploy/$SERVICE_NAME" "/etc/systemd/system/$SERVICE_NAME"
sed -i \
  -e "s|^User=.*|User=$APP_USER|" \
  -e "s|^Group=.*|Group=$APP_GROUP|" \
  -e "s|^WorkingDirectory=.*|WorkingDirectory=$APP_DIR|" \
  -e "s|^EnvironmentFile=.*|EnvironmentFile=$APP_DIR/.env|" \
  -e "s|^ExecStart=.*|ExecStart=$APP_DIR/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log|" \
  "/etc/systemd/system/$SERVICE_NAME"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo "Setup complete."
echo "Edit $APP_DIR/.env, then run:"
echo "  sudo systemctl restart $SERVICE_NAME"
echo "  sudo systemctl status $SERVICE_NAME --no-pager"
