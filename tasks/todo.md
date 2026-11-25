# Cloudflare R2 Storage Integration — Implementation Plan

## 1. Dependencies & Configuration
- [x] Add `boto3>=1.34.0` to `backend/requirements.txt` and install in `geekai-backend`.
- [x] Add `STORAGE_BACKEND` (`local` | `r2`) and optional global R2 env vars (`R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_URL`) to `backend/app/core/config.py` and `.env.example`.

## 2. Database Schema & Migration (`007_cloudflare_r2_storage.py`)
- [x] Add per-event R2 columns to `events` table:
  - `r2_enabled` (Boolean, default False)
  - `r2_account_id` (String(255), nullable)
  - `r2_access_key_id` (String(255), nullable)
  - `r2_secret_access_key` (String(512), nullable)
  - `r2_bucket_name` (String(255), nullable)
  - `r2_public_url` (String(512), nullable)
- [x] Add `photo_object_key` and `qr_object_key` (String(512), nullable) to `participants` table.
- [x] Create `stored_files` table (`id`, `event_id`, `participant_id`, `category`, `object_key`, `public_url`, `original_filename`, `content_type`, `size_bytes`, `storage_provider`, `created_at`).
- [x] Update `backend/app/models/models.py` and `backend/app/schemas/schemas.py` (`EventOut`, `EventCreate`, `EventUpdate`, `SuperAdminEventOut`, `ParticipantOut`, `PresignUploadRequest`, `PresignUploadResponse`).

## 3. Storage Service & Presigned URL API
- [x] Create `backend/app/services/storage_service.py`:
  - Dynamic resolution of event R2 config -> global R2 config -> local filesystem fallback.
  - S3-compatible `boto3` client for Cloudflare R2 (`https://{account_id}.r2.cloudflarestorage.com`).
  - Dynamic object key generator using event ID, participant ID, category (`participant_photos`, `form_uploads`, `documents`, `qr_codes`), and unique UUID + sanitized filename.
  - Presigned PUT URL generation (with content-type & expiry).
  - Direct server-side upload (`put_bytes`), download (`get_bytes`), and deletion (`delete_object`).
  - Validation of file extensions, MIME types, and size limits per category.
- [x] Create `backend/app/api/storage.py` and register in `backend/app/main.py`:
  - `POST /api/storage/presign-upload` (validates category, auth for `form_uploads`, file type/size; returns presigned PUT URL for R2 or local upload URL for dev).
  - `POST /api/storage/local-upload` (handles local fallback uploads to `uploads/{object_key}`).
  - `POST /api/storage/confirm-upload` (records `StoredFile` metadata in PostgreSQL).
  - `DELETE /api/storage/object` (authenticated deletion of replaced/unwanted files from R2/local and `stored_files`).

## 4. Integrate R2 into Services & Existing Endpoints
- [x] `backend/app/services/qr_service.py`: Generate QR PNG in memory, upload via `storage_service` under `events/{event_id}/qr_codes/`, return `(public_url, object_key, qr_bytes)`.
- [x] `backend/app/services/embedding_service.py`: Add `generate_embedding_from_bytes(image_bytes)` so face embeddings work from R2 without requiring local disk files.
- [x] `backend/app/services/email_service.py`: Support `qr_bytes` directly in `send_qr_email`.
- [x] `backend/app/api/participants.py`:
  - Support both presigned R2 photo/document uploads (`photo_url`, `photo_object_key`) and direct multipart `UploadFile` uploads (uploaded to R2 by backend).
  - Compute face embedding from bytes.
  - Update `get_participant_photo` and `get_participant_qrcode` to serve from R2 or legacy local paths.
  - Update `delete_participant` to delete R2 objects (`photo_object_key`, `qr_object_key`, and any `custom_responses` file keys) and `stored_files` rows.
- [x] `backend/app/api/super_admin.py`:
  - Mask `r2_secret_access_key` in `_to_super_admin_out` (`has_r2_secret`), preserve existing secret on blank update.
  - Update `upload_form_field_image` to upload to R2 under `events/{event_id}/form_uploads/` when R2 is enabled.
  - Update `delete_event` to clean up all `stored_files` / R2 objects for the event.

## 5. Frontend Integration
- [x] Add `resolveMediaUrl(url)` helper in `frontend/src/utils/helpers.js` to handle both `https://...` R2 URLs and legacy `/uploads/...` paths.
- [x] `frontend/src/pages/super-admin/EventEditor.jsx`: Add "Cloudflare R2 Storage Settings" card (toggle, Account ID, Access Key ID, Secret Access Key with mask/eye toggle, Bucket Name, Public Base URL).
- [x] `frontend/src/pages/super-admin/FormBuilder.jsx`: Use presigned URL upload flow for Form Builder `Image` field uploads (with deletion of replaced images).
- [x] `frontend/src/pages/EventRegister.jsx`: Use presigned URL upload flow for participant `photo` and `file` uploads when R2 is enabled (falling back cleanly to local upload in dev).
- [x] Update `EventSuccess.jsx`, `ParticipantDetail.jsx`, `Participants.jsx`, `QRScanner.jsx`, `ManualLookup.jsx` to use `resolveMediaUrl`.

## 6. Build, Deploy & E2E Verification
- [x] Install `boto3` in `geekai-backend`, apply migration `007_cloudflare_r2_storage`.
- [x] Build frontend (`npm run build`) and deploy containers.
- [x] Test presigned URL generation, R2 key prefixes, local dev fallback, Super Admin R2 config (secret masking), participant registration with photo/QR/documents, deletion cleanup, and OAIC backward compatibility.
- [x] Update `tasks/progress.md`.
