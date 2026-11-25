# GeekAI — Multi-Event Registration & Attendance Platform

> Event registration, QR ticketing, and real-time attendance management — inspired by Unstop.

[![Docker](https://img.shields.io/badge/Docker-Compose-blue)](https://docs.docker.com/compose/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React%2019-61DAFB)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/DB-PostgreSQL%2016-336791)](https://www.postgresql.org/)

---

## Overview

GeekAI is a multi-event platform that lets organisations host events with:

- **Online registration** with dynamic forms, photo/file uploads, and QR code generation
- **QR & manual session attendance** tracking per session and event
- **Cashfree payment gateway** integration for paid events
- **Cloudflare R2 storage** for participant photos, form uploads, documents, and QR codes
- **Admin panel** for participant management, attendance, analytics, and CSV export
- **Volunteer dashboard** for QR scanning and manual lookup at the venue

Currently hosting: **Odisha AI Conference (OAIC)** — registration fee ₹300.

---

## Quick Start (Docker)

### Prerequisites
- Docker + Docker Compose
- Git

### 1. Clone the repo
```bash
git clone https://github.com/msVivekRanjan/GeekAI.git
cd GeekAI
```

### 2. Configure environment
```bash
cp .env.example .env
```

Edit `.env` and set at minimum:
```
SECRET_KEY=your-random-secret-32-chars-min
SMTP_HOST=smtp.gmail.com
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your-app-password

# Cashfree (sandbox credentials from https://merchant.cashfree.com)
CASHFREE_APP_ID=your_app_id
CASHFREE_SECRET_KEY=your_secret_key
CASHFREE_ENV=sandbox   # change to "production" for live
```

> [!NOTE]
> Cashfree sandbox credentials are free — sign up at https://merchant.cashfree.com and generate test API keys.
> Without Cashfree keys the payment step will fail (503). Set `registration_fee = 0` in the events table if you want to skip payment during development.

### 3. Start all services
```bash
docker compose up -d
```

This will:
1. Start PostgreSQL 16 (`docker compose up -d postgres`)
2. Apply all Alembic schema migrations automatically
3. Seed default admin and volunteer accounts
4. Start the FastAPI backend on port 8000
5. Build and serve the React SPA via nginx on port 5173

### 4. Open the app
| URL | Description |
|-----|-------------|
| http://localhost:5173 | GeekAI homepage + event discovery |
| http://localhost:5173/events/oaic/register | OAIC registration form |
| http://localhost:5173/login | Organizer Login (admin/volunteer) |
| http://localhost:8000/docs | FastAPI Swagger docs |

### Default credentials (auto-seeded)
| Role | Email | Password |
|------|-------|----------|
| Admin | admin@geekai.in | admin123 |
| Volunteer | volunteer@geekai.in | volunteer123 |

> [!CAUTION]
> Change these immediately in production via `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` env vars.

---

## Project Structure

```
GeekAI/
├── backend/                  # FastAPI + SQLAlchemy + Alembic
│   ├── app/
│   │   ├── api/              # Route handlers
│   │   │   ├── auth.py       # Login / JWT
│   │   │   ├── participants.py
│   │   │   ├── sessions.py
│   │   │   ├── attendance.py # QR & manual attendance
│   │   │   ├── events.py     # Multi-event API
│   │   │   ├── payments.py   # Cashfree create-order + verify
│   │   │   └── admin.py      # Admin + volunteer management
│   │   ├── models/models.py  # SQLAlchemy ORM models
│   │   ├── schemas/schemas.py
│   │   ├── core/
│   │   │   ├── config.py     # Pydantic settings (env vars)
│   │   │   ├── db_init.py    # Migration runner + seeder
│   │   │   ├── deps.py       # Auth dependencies
│   │   │   └── security.py   # JWT + bcrypt
│   │   └── services/
│   │       ├── email_service.py
│   │       ├── qr_service.py
│   │       └── storage_service.py
│   ├── migrations/
│   │   └── versions/
│   │       ├── 001_initial.py
│   │       └── 002_multi_event_payment.py
│   ├── Dockerfile
│   ├── docker-entrypoint.sh  # Waits for PG, runs alembic upgrade head
│   └── requirements.txt
│
├── frontend/                 # React 19 + Vite + Tailwind CSS v4
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Home.jsx          # GeekAI homepage + event cards
│   │   │   ├── EventRegister.jsx # Reusable event registration
│   │   │   ├── Login.jsx         # Organizer Login
│   │   │   ├── Register.jsx      # Legacy (preserved)
│   │   │   ├── admin/            # Admin dashboard pages
│   │   │   └── volunteer/        # Volunteer dashboard pages
│   │   ├── components/
│   │   │   ├── Navbar.jsx
│   │   │   ├── AdminLayout.jsx
│   │   │   └── ui/               # Input, Button, PhotoCapture
│   │   ├── context/AuthContext.jsx
│   │   └── api/client.js         # Axios + JWT interceptors
│   └── Dockerfile
│
├── docker-compose.yml
├── .env.example
└── tasks/
    ├── todo.md
    └── lessons.md
```

---

## Environment Variables

Copy `.env.example` to `.env`. All variables with defaults are optional.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ | set in compose | PostgreSQL async URL |
| `SECRET_KEY` | ✅ | weak default | JWT signing key (min 32 chars) |
| `CASHFREE_APP_ID` | For paid events | — | Cashfree merchant App ID |
| `CASHFREE_SECRET_KEY` | For paid events | — | Cashfree secret key |
| `CASHFREE_ENV` | — | `sandbox` | `sandbox` or `production` |
| `BACKEND_URL` | — | `http://localhost:8000` | Used in Cashfree webhook URL |
| `SMTP_HOST` | For emails | — | SMTP server (e.g. smtp.gmail.com) |
| `SMTP_PORT` | — | `587` | SMTP port |
| `SMTP_USER` | For emails | — | SMTP username |
| `SMTP_PASSWORD` | For emails | — | SMTP password / app password |
| `SMTP_FROM_EMAIL` | — | `noreply@geekai.in` | Sender address |
| `SEED_ADMIN_EMAIL` | — | `admin@geekai.in` | Default admin email |
| `SEED_ADMIN_PASSWORD` | — | `admin123` | Default admin password |

---

## Multi-Event Architecture

GeekAI is designed to host multiple independent events. Each event has its own:
- Branding (name, slug, logo, tagline, venue, date)
- Registration fee (stored in paise; ₹300 = 30000)
- Sessions (linked via `event_id`)
- Participants (linked via `event_id`)

### Add a new event (via psql or admin API):
```sql
INSERT INTO events (name, slug, description, tagline, registration_fee, is_active, event_date, venue, website)
VALUES ('My Conference 2027', 'myconf27', 'Description...', 'Tagline', 50000, true, '2027-03-10', 'Venue Name', 'https://myconf.com');
```

The event will automatically appear on the homepage under "Active Events" and its registration page will be available at `/events/myconf27/register`.

---

## Cashfree Payment Setup

1. Sign up at https://merchant.cashfree.com
2. Under **Developers → API Keys**, create a sandbox key pair
3. Copy the `App ID` and `Secret Key` into your `.env`:
   ```
   CASHFREE_APP_ID=CF_TEST_XXXX
   CASHFREE_SECRET_KEY=cfsk_ma_XXXX
   CASHFREE_ENV=sandbox
   ```
4. For production: change `CASHFREE_ENV=production` and use live credentials
5. Restart the backend: `docker compose restart backend`

> [!TIP]
> Use Cashfree test card `4111 1111 1111 1111` / expiry `12/26` / CVV `123` for sandbox testing.

---

## Development (without Docker)

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Set DATABASE_URL to a local PostgreSQL instance in .env
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

Full interactive docs at: http://localhost:8000/docs

Key endpoints:
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/events/` | List active events |
| `GET` | `/api/events/{slug}` | Event details + branding |
| `GET` | `/api/events/{slug}/sessions` | Sessions for an event |
| `POST` | `/api/payments/create-order` | Create Cashfree order |
| `POST` | `/api/payments/verify` | Verify payment status |
| `POST` | `/api/participants/` | Register participant |
| `POST` | `/api/auth/login` | Get JWT token |
| `GET` | `/api/admin/volunteers` | List volunteers (admin) |
| `POST` | `/api/attendance/` | Record attendance |

---

## Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m "feat: add my feature"`
4. Push and open a PR

---

## License

MIT © GeekAI
