#!/usr/bin/env bash
set -euo pipefail

cd /opt/instagram-stl-auto-dm

DISPLAY_ID="${SELENIUM_LOGIN_DISPLAY:-:97}"
SCREEN_SIZE="${SELENIUM_LOGIN_SCREEN_SIZE:-1365x950x24}"
PROJECT_DIR="/opt/instagram-stl-auto-dm"
PROFILE_DIR="${SELENIUM_PROFILE_DIR:-data/selenium/meta_accounts_center_profile}"
BROWSER_BINARY="${SELENIUM_BROWSER_BINARY:-/usr/bin/chromium}"
SESSION_CHECK_URL="${META_SESSION_CHECK_URL:-${INSTAGRAM_SESSION_CHECK_URL:-https://developers.facebook.com/apps/}}"
NOVNC_WEB_DIR="${NOVNC_WEB_DIR:-/usr/share/novnc}"

if [[ "${PROFILE_DIR}" != /* ]]; then
  PROFILE_DIR="${PROJECT_DIR}/${PROFILE_DIR}"
fi

mkdir -p "${PROFILE_DIR}" "${PROJECT_DIR}/data/follow_audit/screenshots"
chmod 700 "${PROJECT_DIR}/data/selenium" "${PROFILE_DIR}"

BROWSER_PID=""
OPENBOX_PID=""
X11VNC_PID=""
WEBSOCKIFY_PID=""
XVFB_PID=""

cleanup() {
  if [[ -n "${BROWSER_PID}" ]] && kill -0 "${BROWSER_PID}" 2>/dev/null; then
    kill -TERM "${BROWSER_PID}" 2>/dev/null || true
    for _ in {1..10}; do
      kill -0 "${BROWSER_PID}" 2>/dev/null || break
      sleep 1
    done
  fi

  for pid in "${WEBSOCKIFY_PID}" "${X11VNC_PID}" "${OPENBOX_PID}" "${XVFB_PID}"; do
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      kill -TERM "${pid}" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT

Xvfb "${DISPLAY_ID}" -screen 0 "${SCREEN_SIZE}" -nolisten tcp &
XVFB_PID="$!"
export DISPLAY="${DISPLAY_ID}"
sleep 1

openbox >/tmp/instagram-follow-login-openbox.log 2>&1 &
OPENBOX_PID="$!"

"${BROWSER_BINARY}" \
  --user-data-dir="${PROFILE_DIR}" \
  --profile-directory=Default \
  --window-size=1365,950 \
  --lang=pt-BR \
  --disable-dev-shm-usage \
  "${SESSION_CHECK_URL}" \
  >/tmp/instagram-follow-login-chromium.log 2>&1 &
BROWSER_PID="$!"

x11vnc \
  -display "${DISPLAY_ID}" \
  -localhost \
  -nopw \
  -forever \
  -shared \
  -quiet \
  >/tmp/instagram-follow-login-x11vnc.log 2>&1 &
X11VNC_PID="$!"

websockify --web="${NOVNC_WEB_DIR}" 127.0.0.1:6080 127.0.0.1:5900 &
WEBSOCKIFY_PID="$!"
wait "${WEBSOCKIFY_PID}"
