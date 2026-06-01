# Oracle Always Free Migration Runbook

Last updated: 2026-05-31

## Goal
Migrate AvClimate from Render free web service to Oracle Cloud Always Free VM to gain more memory headroom while preserving current functionality and minimizing downtime.

## Scope
- Keep the current app architecture (single backend serving frontend + API).
- Keep Render running as rollback until Oracle production is stable.
- Reuse existing bootstrap and precompute optimization scripts.

## Prerequisites
- Oracle Cloud account with access to Always Free resources.
- Domain/DNS access for creating staging and production records.
- GitHub access to this repo.
- SSH key pair ready for VM login.

## Variables to prepare
Set these before deployment (from current Render setup):

- CHARTS_MEMORY_GUARD_MB (currently 430)
- AVCLIMATE_RELEASE_BASE_URL
- AVCLIMATE_BY_ICAO_SHA256
- AVCLIMATE_LIGHTNING_SHA256
- Optional: AVCLIMATE_BY_ICAO_URL
- Optional: AVCLIMATE_LIGHTNING_URL
- Optional: GITHUB_TOKEN (for private rate-limit-safe archive downloads)

## Phase 1: Provision Oracle VM
1. Create an Ubuntu instance in Oracle Always Free tier.
2. Reserve and attach a static public IP.
3. In Oracle network security rules, allow inbound ports 22, 80, 443.
4. Record VM public IP and SSH username (usually ubuntu).

## Phase 2: Prepare DNS safely
1. Create a staging DNS record (example: staging.yourdomain.com) -> Oracle static IP.
2. Keep production DNS pointed at Render for now.
3. Lower production DNS TTL to 300 before cutover day.

## Phase 3: Base server setup
SSH into VM and run:

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install git python3 python3-venv python3-pip nginx ufw

sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
```

## Phase 4: Clone and install app
```bash
sudo mkdir -p /opt/avclimate
sudo chown "$USER":"$USER" /opt/avclimate
cd /opt/avclimate

git clone https://github.com/StrictBug/AvClimate.git app
cd app

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r webapp/requirements.txt
```

## Phase 5: Configure environment
Create /opt/avclimate/app/.env.production:

```bash
cat > /opt/avclimate/app/.env.production <<'EOF'
CHARTS_MEMORY_GUARD_MB=430
AVCLIMATE_RELEASE_BASE_URL=<set-me>
AVCLIMATE_BY_ICAO_SHA256=<set-me>
AVCLIMATE_LIGHTNING_SHA256=<set-me>
# Optional overrides:
# AVCLIMATE_BY_ICAO_URL=<set-me>
# AVCLIMATE_LIGHTNING_URL=<set-me>
# GITHUB_TOKEN=<set-me>
EOF
```

## Phase 6: Bootstrap data and fog shard optimizations
Run once after install and on each deploy:

```bash
cd /opt/avclimate/app
source .venv/bin/activate
set -a
source .env.production
set +a

bash scripts/helpers/bootstrap_data_from_release.sh
python scripts/helpers/split_fog_wind_by_mode.py
```

Notes:
- split_fog_wind_by_mode.py now generates mode and all-state fast-path shards for hourly/dewpoint/wind.
- This is important for reducing memory pressure in fog charts.

## Phase 7: systemd service for Uvicorn
Create /etc/systemd/system/avclimate.service:

```ini
[Unit]
Description=AvClimate Uvicorn Service
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/avclimate/app
EnvironmentFile=/opt/avclimate/app/.env.production
ExecStart=/opt/avclimate/app/.venv/bin/python -m uvicorn webapp.backend.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable avclimate
sudo systemctl restart avclimate
sudo systemctl status avclimate --no-pager
```

## Phase 8: Nginx reverse proxy
Create /etc/nginx/sites-available/avclimate:

```nginx
server {
    listen 80;
    server_name staging.yourdomain.com yourdomain.com;

    client_max_body_size 16m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
    }
}
```

Enable:

```bash
sudo ln -sf /etc/nginx/sites-available/avclimate /etc/nginx/sites-enabled/avclimate
sudo nginx -t
sudo systemctl restart nginx
```

## Phase 9: HTTPS (LetsEncrypt)
```bash
sudo apt -y install certbot python3-certbot-nginx
sudo certbot --nginx -d staging.yourdomain.com -d yourdomain.com
```

Confirm auto-renew:

```bash
sudo systemctl status certbot.timer --no-pager
```

## Phase 10: Staging validation checklist
Use staging domain first.

1. Open home page and confirm assets load.
2. Hit /api/options and ensure 200.
3. Test fog tab (YMML and YMMB):
   - chart 1 and 2 load
   - chart 3 either renders or skips safely
   - no process restart
4. Check logs:

```bash
sudo journalctl -u avclimate -n 200 --no-pager
```

Look for:
- charts.fog_low_cloud_precomputed
- optional charts.fog_cloud_distribution_skipped
- absence of crash loops

## Phase 11: Cutover to production
1. Confirm staging is stable.
2. Update production DNS A record to Oracle static IP.
3. Monitor for 60 minutes.
4. Keep Render live for rollback window (48 hours recommended).

## Phase 12: Deploy update workflow (Oracle)
On each new code release:

```bash
cd /opt/avclimate/app

git pull origin main
source .venv/bin/activate
pip install -r webapp/requirements.txt

set -a
source .env.production
set +a

bash scripts/helpers/bootstrap_data_from_release.sh
python scripts/helpers/split_fog_wind_by_mode.py

sudo systemctl restart avclimate
sudo systemctl status avclimate --no-pager
```

## Rollback plan
If production issue occurs:

1. Point production DNS back to Render endpoint.
2. Verify Render responds normally.
3. Investigate Oracle logs before retrying cutover.

## Troubleshooting quick commands
```bash
# Service health
sudo systemctl status avclimate --no-pager

# App logs
sudo journalctl -u avclimate -f

# Nginx logs
sudo tail -n 200 /var/log/nginx/error.log
sudo tail -n 200 /var/log/nginx/access.log

# Port check
sudo ss -ltnp | grep -E ':80|:443|:8000'
```

## Optional hardening after stable cutover
- Add daily VM snapshot policy.
- Add simple uptime monitoring and alerting.
- Add fail2ban for SSH protection.
- Add log rotation review for app and nginx.
