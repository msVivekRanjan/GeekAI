# GeekAI — Multi-Event Registration & Attendance Platform

> Event registration, dynamic form builder, QR ticketing, and real-time attendance management — built for Cloudflare Pages, AWS EC2 Docker (or Vercel), Neon PostgreSQL, and Cloudflare R2.

[![Cloudflare Pages](https://img.shields.io/badge/Frontend-Cloudflare%20Pages-F38020)](https://pages.cloudflare.com/)
[![AWS EC2 + Docker](https://img.shields.io/badge/Backend-EC2%20Docker%20%2B%20FastAPI-009688)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19%20%2B%20Vite-61DAFB)](https://react.dev/)
[![Neon](https://img.shields.io/badge/DB-Neon%20PostgreSQL%2016-00E599)](https://neon.tech/)
[![Cloudflare R2](https://img.shields.io/badge/Storage-Cloudflare%20R2-F38020)](https://developers.cloudflare.com/r2/)

---

## Overview

GeekAI is a multi-event platform that lets organisations host and manage events with:

- **Super Admin Dashboard & Dynamic Form Builder** — Create/edit events, assign per-event admin credentials, configure registration guidelines, and build custom registration forms (including dynamic categories, photo, file, radio, dropdown, and inline image fields)
- **Event-Scoped Dynamic Categories** — Participant categories are stored as flexible strings and validated against each event's configured form schema (with legacy fallback for events without a custom schema)
- **Optional Cashfree Payment Gateway** — Enable or disable Cashfree per event (free events confirm immediately without payment)
- **Cloudflare R2 Object Storage** — Direct browser uploads via S3v4 presigned URLs for participant photos, documents, form images, and generated QR codes (with local filesystem fallback in development)
- **QR & Manual Attendance** — Unique QR ticket generation + email delivery, QR scanning, and manual participant lookup per event and session
- **Event Admin & Volunteer Dashboards** — Fixed/sticky sidebar, photo-free Participants table (conditional Payment column when Cashfree is enabled), dynamic participant detail views, session management, safe volunteer deletion preserving attendance history, analytics, and CSV/XLSX export
- **Offline Sync API** — Idempotent batch attendance sync (`/api/offline/sync/attendance`)

---

## Production Deployment

### Option A: Cloudflare Pages + AWS EC2 Docker + Cloudflare Tunnel (Recommended)
See **[DEPLOYMENT_AWS_CLOUDFLARE.md](DEPLOYMENT_AWS_CLOUDFLARE.md)** for the full step-by-step guide:
- **Frontend:** Cloudflare Pages (`frontend/`, build command `npm run build`, output `dist`, SPA routing via `frontend/public/_redirects`) with `VITE_API_BASE_URL` and `VITE_DEPLOYMENT_MODE=cloud`
- **Backend:** AWS EC2 (Ubuntu + Docker) running `docker-compose.prod.yml` bound to `127.0.0.1:8000` behind **Cloudflare Tunnel** (`cloudflared`)
- **Database:** Neon PostgreSQL (`DATABASE_URL` pooled with `DB_POOL_SIZE=5` / `DB_MAX_OVERFLOW=5`, and `MIGRATION_DATABASE_URL` direct for Alembic)
- **Storage:** Cloudflare R2 (`STORAGE_BACKEND=r2` or per-event R2 settings)

### Option B: Vercel Multi-Service Deployment
`vercel.json` is also configured for Vercel Services (`frontend` with `VITE_DEPLOYMENT_MODE=cloud` + `backend` FastAPI serverless with `NullPool` on `VERCEL=1`), Neon PostgreSQL, and Cloudflare R2.

### Cloudflare R2 Bucket CORS
Allow browser `PUT` uploads to presigned URLs on your R2 bucket (**R2 → Bucket → Settings → CORS Policy**):
```json
[
  {
    "AllowedOrigins": ["https://your-app.pages.dev", "http://localhost:5173"],
    "AllowedMethods": ["GET", "PUT", "POST", "HEAD"],
    "AllowedHeaders": ["Content-Type"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

### Bootstrap Super Admin (Fresh Database)
On an empty `users` table, create the initial Super Admin once via `POST /api/auth/bootstrap` using your `BOOTSTRAP_TOKEN`.

---

## Quick Start (Local Docker)

### Prerequisites
- Docker + Docker Compose
- Git

### 1. Clone & configure environment
```bash
git clone https://github.com/msVivekRanjan/GeekAI.git
cd GeekAI
cp .env.example .env
```
Edit `.env` to set `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL` (using host `postgres` for Docker Compose), `SECRET_KEY`, `BOOTSTRAP_TOKEN`, and `QR_SIGNING_KEY`.

### 2. Start all services
```bash
docker compose up -d --build
```
This will:
1. Start PostgreSQL 16 (`geekai-postgres`)
2. Wait for DB connectivity and run `alembic upgrade head` in `backend/docker-entrypoint.sh`
3. Start the FastAPI backend on port `8000`
4. Build and serve the React SPA via nginx on port `5173`

### 3. Open the app
| URL | Description |
|-----|-------------|
| http://localhost:5173 | GeekAI homepage & active events |
| http://localhost:5173/events/oaic/register | Event registration form |
| http://localhost:5173/login | Staff / Admin login |
| http://localhost:8000/docs | FastAPI Swagger docs |

---

## Project Structure

```
GeekAI/
├── backend/                  # FastAPI + async SQLAlchemy + Alembic
│   ├── app/
│   │   ├── api/              # Route handlers
│   │   │   ├── auth.py       # Login / JWT / bootstrap
│   │   │   ├── super_admin.py# Super Admin events, admins & form builder
│   │   │   ├── admin.py      # Event Admin dashboard, volunteers, coupons, export
│   │   │   ├── events.py     # Public event details & form schemas
│   │   │   ├── participants.py # Registration & dynamic category validation
│   │   │   ├── sessions.py
│   │   │   ├── attendance.py # QR & manual attendance
│   │   │   ├── storage.py    # R2 presigned URLs, confirm, proxy & delete
│   │   │   ├── offline_sync.py
│   │   │   └── payments.py   # Cashfree create-order + verify + webhook
│   │   ├── models/models.py  # SQLAlchemy ORM models
│   │   ├── schemas/schemas.py
│   │   ├── core/
│   │   │   ├── config.py     # Pydantic settings & Neon asyncpg URL normalization
│   │   │   ├── db_init.py    # Migration & optional admin seed helpers
│   │   │   ├── deps.py       # Pool / NullPool DB session & auth dependencies
│   │   │   └── security.py   # JWT + bcrypt
│   │   └── services/
│   │       ├── email_service.py
│   │       ├── qr_service.py
│   │       └── storage_service.py
│   ├── migrations/versions/  # Alembic migrations (001 through 011)
│   ├── tests/
│   ├── Dockerfile
│   ├── docker-entrypoint.sh
│   └── requirements.txt
│
├── frontend/                 # React 19 + Vite + Tailwind CSS v4
│   ├── public/
│   │   └── _redirects        # Cloudflare Pages SPA routing fallback
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Home.jsx
│   │   │   ├── EventRegister.jsx
│   │   │   ├── EventSuccess.jsx
│   │   │   ├── Login.jsx
│   │   │   ├── super-admin/  # Super Admin events & FormBuilder
│   │   │   ├── admin/        # Event Admin dashboard pages
│   │   │   └── volunteer/    # QR scanner & manual lookup
│   │   ├── utils/upload.js   # Presigned R2 / local dev upload helper
│   │   ├── context/AuthContext.jsx
│   │   └── api/client.js
│   └── Dockerfile
│
├── docker-compose.yml        # Local full-stack Docker Compose
├── docker-compose.prod.yml   # Production backend-only Compose for EC2
├── DEPLOYMENT_AWS_CLOUDFLARE.md
├── vercel.json               # Optional Vercel multi-service config
├── .env.example
└── tasks/
    ├── todo.md
    └── progress.md
```

---

## Environment Variables

Copy `.env.example` to `.env`. Secrets must be provided via environment variables in production.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ | — | Neon pooled URL (prod) or local `postgresql+asyncpg://...` |
| `MIGRATION_DATABASE_URL` | Prod | — | Neon direct (non-pooled) URL for Alembic migrations |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | — | `5` / `5` | Conservative SQLAlchemy pool limits for EC2 |
| `SECRET_KEY` | ✅ | — | JWT signing secret (min 32 random chars) |
| `BOOTSTRAP_TOKEN` | First boot | — | One-time secret for `/api/auth/bootstrap` |
| `CORS_ORIGINS` | ✅ (prod) | `localhost` | Comma-separated allowed frontend origins |
| `STORAGE_BACKEND` | — | `local` | `r2` for production, `local` for dev |
| `R2_ACCOUNT_ID` | If `r2` | — | Cloudflare R2 account ID (global fallback) |
| `R2_ACCESS_KEY_ID` | If `r2` | — | Cloudflare R2 access key ID |
| `R2_SECRET_ACCESS_KEY` | If `r2` | — | Cloudflare R2 secret access key |
| `R2_BUCKET_NAME` | If `r2` | — | Cloudflare R2 bucket name |
| `R2_PUBLIC_URL` | Optional | — | Custom R2 public domain (falls back to `/api/storage/object`) |
| `CASHFREE_APP_ID` | Optional | — | Global Cashfree App ID (per-event config supported) |
| `CASHFREE_SECRET_KEY` | Optional | — | Global Cashfree Secret Key |
| `CASHFREE_ENV` | — | `sandbox` | `sandbox` or `production` |
| `BACKEND_URL` | — | `http://localhost:8000` | Public backend URL for Cashfree webhooks |
| `SMTP_HOST` / `USER` / `PASSWORD` | Optional | — | SMTP settings for QR ticket emails |
| `VITE_API_BASE_URL` | Frontend prod | `/api` | Backend origin for Cloudflare Pages (e.g. `https://api.yourdomain.com`) |
| `VITE_DEPLOYMENT_MODE` | — | — | Set to `cloud` to exclude `/volunteer/*` routes from public builds |

---

## Development (without Docker)

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev    # starts at http://localhost:5173
```

---

## API Reference

Interactive Swagger docs: `http://localhost:8000/docs`.

Key endpoints:
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/auth/bootstrap` | One-time initial Super Admin creation |
| `POST` | `/api/auth/login` | Staff / Admin JWT login |
| `GET` | `/api/events/` | List active events |
| `GET` | `/api/events/{slug}/registration-form` | Public dynamic form schema |
| `POST` | `/api/storage/presign-upload` | Generate R2 presigned PUT URL |
| `POST` | `/api/storage/confirm-upload` | Persist uploaded file metadata |
| `GET` | `/api/storage/object` | Proxy-serve R2 object when no public domain is set |
| `POST` | `/api/participants/` | Register participant + generate QR |
| `POST` | `/api/payments/create-order` | Create Cashfree order (when enabled) |
| `POST` | `/api/payments/verify` | Verify Cashfree payment status |
| `POST` | `/api/attendance/` | Record QR or manual attendance |
| `POST` | `/api/offline/sync/attendance` | Batch-sync offline attendance records |
| `GET` | `/api/super-admin/events` | Manage events, credentials & form schemas |

---

## License

MIT © GeekAI
