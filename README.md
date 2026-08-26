# Instagram STL Auto DM

Official-API Instagram automation for sending a private reply when someone comments a configured keyword, such as `STL`, on a selected post.

## Portfolio Highlights

- Integration with Meta Webhooks and Instagram Private Replies.
- `X-Hub-Signature-256` signature validation.
- SQLite idempotency to avoid duplicate replies.
- Polling fallback when webhooks do not arrive in real time.
- Raspberry Pi deployment with `systemd`.
- Separate service monitoring dashboard.
- Tests with fake payloads, without calling the real API.

See also: [`docs/portfolio-case-study.md`](docs/portfolio-case-study.md).

The project uses Python, FastAPI, Meta Webhooks, SQLite and Instagram Private Replies. The goal is to avoid browser automation, scraping and Selenium for a workflow that needs to be reliable on a Raspberry Pi.

When Meta webhooks are not delivered in real time because of app review or access limitations, the backend can also poll comments as a fallback.

## Current State

MVP with:

- `GET /webhook` endpoint for Meta verification.
- `POST /webhook` endpoint for comment events.
- `X-Hub-Signature-256` signature validation.
- Filtering by `media_id` and keyword.
- Private Reply sending through a configurable messaging endpoint.
- SQLite idempotency so the same comment is not answered twice.
- Optional comment polling fallback.
- Tests using fake payloads, without calling the real Meta API.

## Structure

```text
app/
  main.py
  config.py
  database.py
  security.py
  routes/
    webhook.py
  services/
    automations.py
    instagram.py
data/
tests/
.env.example
requirements.txt
run.py
```

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On Linux/Raspberry Pi:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Create a `.env` file based on `.env.example`.

```env
VERIFY_TOKEN=a_token_you_choose
META_APP_SECRET=your_meta_app_secret
IG_ACCESS_TOKEN=your_access_token
IG_USER_ID=your_instagram_user_id
TARGET_MEDIA_ID=target_post_id
STL_KEYWORD=STL
STL_LINK=https://example.com/download/model.stl
GRAPH_VERSION=v26.0
```

For multiple automations, use `AUTOMATIONS_JSON`:

```env
AUTOMATIONS_JSON=[{"media_id":"180...","keyword":"STL","link":"https://example.com/model.stl"}]
```

If Meta webhooks are not arriving, enable comment polling:

```env
COMMENT_POLLING_ENABLED=true
COMMENT_POLLING_INTERVAL_SECONDS=30
COMMENT_POLLING_LIMIT=25
```

## Run Locally

```bash
python run.py
```

Or:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Local URL:

```text
http://localhost:8000
```

For Meta to call the webhook during development, expose the port through an HTTPS URL, for example with ngrok or Cloudflare Tunnel:

```text
https://your-domain-or-tunnel/webhook
```

## Run On Raspberry Pi

The Raspberry Pi is intended to keep the backend running 24/7. Use a `systemd` service so it starts with the system and restarts if it crashes.

1. Clone or copy this project to the Raspberry Pi:

```bash
sudo mkdir -p /opt/instagram-stl-auto-dm
sudo chown -R pi:pi /opt/instagram-stl-auto-dm
git clone <your-repository-url> /opt/instagram-stl-auto-dm
```

Keep `.env` outside Git.

2. Run the setup script:

```bash
cd /opt/instagram-stl-auto-dm
chmod +x deploy/raspberry-setup.sh
sudo ./deploy/raspberry-setup.sh
```

3. Edit `.env` on the Raspberry Pi with real values:

```bash
nano /opt/instagram-stl-auto-dm/.env
```

4. Start or restart the service:

```bash
sudo systemctl restart instagram-stl-auto-dm
sudo systemctl status instagram-stl-auto-dm --no-pager
```

5. Test locally on the Raspberry Pi:

```bash
curl http://127.0.0.1:8000/health
```

6. Create a public HTTPS URL pointing to `127.0.0.1:8000` and use it in the Meta dashboard:

```text
https://your-public-url/webhook
```

For real use, prefer a stable URL. Cloudflare Tunnel with a custom domain, reserved ngrok domains, Nginx with HTTPS or a VPS avoid changing the callback URL every time the tunnel restarts.

For quick tests without a custom domain, install `cloudflared` and run a quick tunnel pointing to the local service:

```bash
sudo systemctl status instagram-stl-auto-dm-tunnel --no-pager
journalctl -u instagram-stl-auto-dm-tunnel --no-pager -n 120 | grep -Eo 'https://[-a-zA-Z0-9.]+\.trycloudflare\.com' | tail -n 1
```

Use the returned URL with `/webhook` in the Meta dashboard. This tunnel type is good for testing, but the URL can change when the service restarts.

## Status Dashboard

The project also includes a separate dashboard for monitoring the Raspberry Pi and the automation services. It runs on port `8080` and shows:

- Raspberry Pi online state.
- Uptime, memory, disk and temperature.
- Whether `instagram-stl-auto-dm` is active.
- Whether the public tunnel is active.
- Current public webhook URL, when found in logs.
- `systemd` logs.
- Buttons to restart the backend and tunnel services.

On the Raspberry Pi:

```bash
sudo cp /opt/instagram-stl-auto-dm/deploy/raspberry-status.service /etc/systemd/system/raspberry-status.service
sudo systemctl daemon-reload
sudo systemctl enable raspberry-status
sudo systemctl restart raspberry-status
```

Open on the local network:

```text
http://192.168.0.105:8080
```

Direct JSON:

```text
http://192.168.0.105:8080/api/status
```

Logs:

```text
http://192.168.0.105:8080/api/logs/instagram-stl-auto-dm
http://192.168.0.105:8080/api/logs/instagram-stl-auto-dm-tunnel
```

The dashboard restart buttons call:

```text
POST /api/services/instagram-stl-auto-dm/restart
POST /api/services/instagram-stl-auto-dm-tunnel/restart
```

Restarting `instagram-stl-auto-dm` keeps the tunnel active. Restarting `instagram-stl-auto-dm-tunnel` can generate a new `trycloudflare.com` URL, which must also be updated in the Meta dashboard.

## Automatic Restart

To reduce the risk of long-running service issues, the project includes an optional timer that restarts only the `instagram-stl-auto-dm` backend every day before morning traffic. It does not restart the whole Raspberry Pi and it does not restart the tunnel, so the public URL stays the same.

Install and enable it on the Raspberry Pi:

```bash
sudo cp /opt/instagram-stl-auto-dm/deploy/instagram-stl-auto-dm-restart.service /etc/systemd/system/
sudo cp /opt/instagram-stl-auto-dm/deploy/instagram-stl-auto-dm-restart.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now instagram-stl-auto-dm-restart.timer
systemctl list-timers instagram-stl-auto-dm-restart.timer
```

By default it runs every day at `04:10`, with up to 10 minutes of randomized delay.

## Test

```bash
pytest
```

## Official Sources To Track

Confirmed against Meta's official documentation on 2026-08-16:

- [Instagram Private Replies](https://developers.facebook.com/documentation/instagram-platform/private-replies)
- [Private Replies in Instagram Messaging](https://developers.facebook.com/documentation/business-messaging/instagram-messaging/features/private-replies)
- [Graph API Webhooks](https://developers.facebook.com/docs/graph-api/webhooks/getting-started/)
- [Instagram Webhooks](https://developers.facebook.com/docs/graph-api/webhooks/getting-started/webhooks-for-instagram/)
- [Permissions Reference](https://developers.facebook.com/docs/permissions/)

Before production use, review the Meta dashboard to confirm which permissions and features require App Review or Advanced Access for the account and login type you choose.

## Next Steps

1. Create and configure the app in Meta for Developers.
2. Connect an Instagram Professional account.
3. Get `IG_USER_ID`, `IG_ACCESS_TOKEN`, `APP_SECRET` and `TARGET_MEDIA_ID`.
4. Deploy the backend behind a public HTTPS URL.
5. Register the webhook in the Meta dashboard and subscribe to comment events.
6. Test the real flow by commenting `STL` on the configured post.
