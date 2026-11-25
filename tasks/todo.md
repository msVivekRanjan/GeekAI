# Cloud Deployment + Offline Volunteer App + Sync — Implementation Plan

## Phase 1: Cloud Deployment — Gate Volunteer Routes
- [x] Gate volunteer routes in `frontend/src/App.jsx` with `VITE_DEPLOYMENT_MODE=cloud` env var (using React `lazy` + `Suspense`)
- [x] Conditionally exclude: `/volunteer/*` (dashboard, face-checkin, scan, manual), `/volunteer/login`
- [x] Update `vercel.json` with `VITE_DEPLOYMENT_MODE=cloud` buildCommand for frontend service
- [x] Verify frontend builds cleanly in both cloud and local modes

## Phase 2: Offline Volunteer App Extensions
- [x] Add `pyzbar>=0.1.9` to `face-checkin/requirements.txt`
- [x] Add `EVENT_ID` and `SQLITE_DB` config vars to `face-checkin/config.py`
- [x] Create `face-checkin/local_db.py` — SQLite schema (participants, sessions, attendance_queue, volunteer_cache)
- [x] Create `face-checkin/qr_scanner.py` — QR decode, local SQLite lookup, local attendance record
- [x] Offline attendance recording (`record_attendance_local` implemented in `face-checkin/local_db.py`)
- [x] Extend `face-checkin/sync.py` — download participants + sessions from `/api/offline/*`, cache to SQLite with offline fallback
- [x] Extend `face-checkin/ui.py` — add session indicator, online/offline indicator, pending sync count, QR mode UI
- [x] Create `face-checkin/offline_sync.py` — background thread reading PENDING records, syncing to backend

## Phase 3: Backend Batch-Sync APIs
- [x] Create `backend/migrations/versions/008_offline_sync.py` — add `local_uuid`, `sync_source`, `synced_at` to `attendance`
- [x] Update `backend/app/models/models.py` — add new Attendance columns
- [x] Add `OfflineAttendanceRecord`, `OfflineSyncBatch`, `OfflineSyncResult`, `OfflineSyncResponse` schemas
- [x] Create `backend/app/api/offline_sync.py` — batch sync endpoint + offline data APIs (with savepoint isolation & event-scope validation)
- [x] Register `offline_sync` router in `backend/app/main.py`

## Phase 4: Volunteer App Sync Implementation
- [x] Update `face-checkin/api_client.py` — add `sync_attendance_batch`, `download_participants`, `download_sessions`, `health_check`
- [x] Update `face-checkin/main.py` — integrate session selection, offline auth cache, QR mode, local SQLite recording, and `OfflineSyncThread`

## Phase 5: Verification
- [x] Apply migration 008 in Docker (`008_offline_sync`)
- [x] Build frontend (`npm run build` and `VITE_DEPLOYMENT_MODE=cloud npm run build`)
- [x] Test batch sync API (idempotency, dedup, error handling, `/api/offline/participants`, `/api/offline/sessions`, `/api/offline/health`)
- [x] Test offline volunteer app modules (syntax, SQLite `local_db`, `qr_scanner` payload parsing)
- [x] Update `tasks/progress.md`
