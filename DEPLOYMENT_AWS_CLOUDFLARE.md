# GeekAI Production Deployment Guide (AWS EC2 + Cloudflare + Neon)

Architecture:
- **Frontend:** Cloudflare Pages (`frontend/`, React + Vite)
- **Backend:** AWS EC2 Ubuntu + Docker (`docker-compose.prod.yml`, FastAPI bound to `127.0.0.1:8000`)
- **Public API Access:** Cloudflare Tunnel (`cloudflared` → `http://127.0.0.1:8000`)
- **Database:** Neon PostgreSQL (`DATABASE_URL` pooled + `MIGRATION_DATABASE_URL` direct)
- **File Storage:** Cloudflare R2 (presigned URLs + `/api/storage/object` fallback)
- **Payments:** Cashfree (global env fallback + per-event Super Admin config)

---

## 1. Prerequisites & Neon Setup

1. In your Neon project, copy **two** connection strings for the `production` branch:
   - **Pooled (`-pooler`) URL** → `DATABASE_URL` (used by the FastAPI app)
   - **Direct (non-pooled) URL** → `MIGRATION_DATABASE_URL` (used by `alembic upgrade head`)
2. Ensure both use `postgresql+asyncpg://...` (or `postgresql://...`, which `Settings` normalizes automatically) and `?sslmode=require`.

---

## 2. Cloudflare R2 CORS Configuration

In **Cloudflare Dashboard → R2 → `<your-bucket>` → Settings → CORS Policy**, allow your Cloudflare Pages domain:
```json
[
  {
    "AllowedOrigins": [
      "https://your-app.pages.dev",
      "https://your-custom-domain.com"
    ],
    "AllowedMethods": ["GET", "PUT", "POST", "HEAD"],
    "AllowedHeaders": ["Content-Type"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

---

## 3. AWS EC2 (Ubuntu 24.04 / 22.04, 2 GB RAM) Setup

### Install Docker & Docker Compose
```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

*(Recommended for 2 GB RAM instances)* Add a 2 GB swap file so Docker builds never OOM:
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Clone Repository & Configure `.env`
```bash
git clone <your-repo-url> ~/GeekAI
cd ~/GeekAI
cp .env.example .env
chmod 600 .env
```

Edit `.env` with production values (never commit `.env`):
```env
DATABASE_URL=postgresql+asyncpg://<user>:<pass>@<neon-host>-pooler.aws.neon.tech/neondb?sslmode=require
MIGRATION_DATABASE_URL=postgresql+asyncpg://<user>:<pass>@<neon-direct-host>.aws.neon.tech/neondb?sslmode=require
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=5

SECRET_KEY=<32+-char-random-secret>
BOOTSTRAP_TOKEN=<random-bootstrap-token>
QR_SIGNING_KEY=<random-qr-signing-key>
QR_KEY_ID=geekai-qr-01
QR_ISSUER=geekai-hub-01

CORS_ORIGINS=https://your-app.pages.dev,https://your-custom-domain.com
BACKEND_URL=https://api.yourdomain.com

STORAGE_BACKEND=r2
R2_ACCOUNT_ID=<r2-account-id>
R2_ACCESS_KEY_ID=<r2-access-key-id>
R2_SECRET_ACCESS_KEY=<r2-secret-access-key>
R2_BUCKET_NAME=<r2-bucket-name>
R2_PUBLIC_URL=<optional-r2-public-url>

CASHFREE_APP_ID=<optional-global-app-id>
CASHFREE_SECRET_KEY=<optional-global-secret>
CASHFREE_ENV=production

SMTP_HOST=<smtp-host>
SMTP_PORT=587
SMTP_USER=<smtp-user>
SMTP_PASSWORD=<smtp-password>
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_USE_TLS=true
```

### Start the Backend Container
```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
curl -s http://127.0.0.1:8000/health
```
The backend binds **only** to `127.0.0.1:8000`. Keep EC2 Security Group inbound rules closed for port `8000` (only SSH `22` restricted to your IP is needed).

---

## 4. Cloudflare Tunnel Setup (Public API Access)

Install `cloudflared` on EC2:
```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb
rm cloudflared.deb
```

Authenticate and create a named tunnel:
```bash
cloudflared tunnel login
cloudflared tunnel create geekai-api
cloudflared tunnel route dns geekai-api api.yourdomain.com
```

Create `/etc/cloudflared/config.yml`:
```yaml
tunnel: <TUNNEL_UUID>
credentials-file: /root/.cloudflared/<TUNNEL_UUID>.json

ingress:
  - hostname: api.yourdomain.com
    service: http://127.0.0.1:8000
  - service: http_status:404
```

Install and start as a systemd service:
```bash
sudo cloudflared service install
sudo systemctl enable --now cloudflared
curl -s https://api.yourdomain.com/health
```

---

## 5. Cloudflare Pages Setup (Frontend)

1. In **Cloudflare Dashboard → Workers & Pages → Create → Pages → Connect to Git**, select the `GeekAI` repository.
2. Configure build settings:
   - **Root directory:** `frontend`
   - **Build command:** `npm run build`
   - **Build output directory:** `dist`
3. Add **Environment Variables** (Production & Preview — **never** add backend secrets here):
   - `VITE_API_BASE_URL` = `https://api.yourdomain.com`
   - `VITE_DEPLOYMENT_MODE` = `cloud`
4. Deploy. `frontend/public/_redirects` (`/* /index.html 200`) handles SPA routing automatically.

---

## 6. Deployment Updates, Logs, Backups & Rollback

### Deploy Updates
```bash
cd ~/GeekAI
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build
```
Cloudflare Pages rebuilds automatically on push to the connected branch.

### Logs & Health
```bash
docker compose -f docker-compose.prod.yml logs -f --tail=100 backend
sudo journalctl -u cloudflared -f
```

### Backups (Neon)
- Create an instant point-in-time branch/snapshot before risky changes:
  ```bash
  neon branches create --project-id <project-id> --name backup-$(date +%Y%m%d-%H%M)
  ```
- Optional logical backup using Neon direct URL:
  ```bash
  pg_dump "$MIGRATION_DATABASE_URL" --format=custom -f geekai_$(date +%Y%m%d).dump
  ```

### Rollback
- **Backend code:** `git checkout <previous-commit>` and `docker compose -f docker-compose.prod.yml up -d --build`.
- **Database:** Restore from Neon branch/snapshot in the Neon Console or `alembic downgrade -1` (only if the migration has a non-destructive downgrade).
- **Frontend:** In **Cloudflare Pages → Deployments**, click **Rollback to this deployment** on any previous build.
