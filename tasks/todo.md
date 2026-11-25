# Remove Face Recognition & Pgvector (QR-Only Attendance) — Plan

## 1. Remove Standalone Face Check-in App
- [x] Delete `face-checkin/` directory
- [x] Clean `.gitignore`, `.vercelignore`, `.env.example`, `.env`

## 2. Frontend Cleanup
- [x] Delete `frontend/src/pages/volunteer/FaceCheckIn.jsx`
- [x] Remove `FaceCheckIn` import and `/volunteer/face-checkin` route from `frontend/src/App.jsx`
- [x] Remove Face Check-In card/link from `frontend/src/pages/volunteer/VolunteerDashboard.jsx`
- [x] Remove `FACE` method badge/copy references in `frontend/src/utils/helpers.js`, `FeatureCarousel.jsx`, `EventSuccess.jsx`, `Home.jsx`, `ParticipantDetail.jsx`, `FormBuilder.jsx`

## 3. Backend Models, Services, Routers & Dependencies
- [x] Delete `backend/app/services/embedding_service.py` and `backend/app/api/embeddings.py`
- [x] Remove `embeddings_router` from `backend/app/main.py`
- [x] Remove `FaceEmbedding`, `embedding_status`, `Vector`, and `AttendanceMethod.FACE` from `backend/app/models/models.py` and `models/__init__.py`
- [x] Remove `FaceMatchResponse`, `EmbeddingOut` from `backend/app/schemas/schemas.py`
- [x] Remove `/face-match` endpoint and numpy/embedding imports from `backend/app/api/attendance.py`
- [x] Remove embedding generation/storage/deletion from `backend/app/api/participants.py`, `super_admin.py`, `offline_sync.py`
- [x] Remove `pgvector` and `numpy` from `backend/requirements.txt` & `backend/requirements-dev.txt`
- [x] Remove OpenCV apt deps from `backend/Dockerfile`
- [x] Update `backend/tests/`

## 4. Database Migrations & Docker
- [x] Remove `pgvector` import/extension/table from `001_initial.py` and `003_event_users_coupons.py`
- [x] Create `009_remove_face_recognition.py` to drop `face_embeddings`, `embedding_status`, `FACE` enum value, and `vector` extension
- [x] Update `docker-compose.yml` from `pgvector/pgvector:pg16` to `postgres:16`

## 5. Documentation, Rebuild & E2E Verification
- [x] Update `README.md` and `tasks/progress.md`
- [x] Deploy updated backend/frontend into Docker containers and run migration `009_remove_face_recognition` (Docker Hub image rebuild skipped due to transient `registry-1.docker.io` EOF)
- [x] Verify migration `009_remove_face_recognition`, registration, QR generation, QR attendance, and dashboards
