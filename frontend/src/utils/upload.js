import client from '../api/client'

/**
 * Upload a File via presigned URL (Cloudflare R2 when enabled, or local dev fallback).
 * Returns { url, object_key, mode }.
 */
export async function uploadViaPresignedUrl({
  file,
  eventId = null,
  eventSlug = null,
  category = 'documents',
  participantId = null,
}) {
  if (!file) throw new Error('No file provided')

  const contentType = file.type || 'application/octet-stream'
  const presignRes = await client.post('/storage/presign-upload', {
    event_id: eventId ? Number(eventId) : null,
    event_slug: eventSlug || null,
    participant_id: participantId ? Number(participantId) : null,
    category,
    filename: file.name || 'upload.bin',
    content_type: contentType,
    size_bytes: file.size || null,
  })

  const { mode, upload_url, object_key, public_url, headers } = presignRes.data

  if (mode === 'r2') {
    const putResp = await fetch(upload_url, {
      method: 'PUT',
      headers: headers || { 'Content-Type': contentType },
      body: file,
    })
    if (!putResp.ok) {
      throw new Error(`Direct R2 upload failed (${putResp.status})`)
    }
  } else {
    const fd = new FormData()
    fd.append('object_key', object_key)
    fd.append('file', file)
    await client.post(upload_url, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  }

  // Record metadata in PostgreSQL
  await client.post('/storage/confirm-upload', {
    event_id: eventId ? Number(eventId) : null,
    participant_id: participantId ? Number(participantId) : null,
    category,
    object_key,
    public_url,
    original_filename: file.name,
    content_type: contentType,
    size_bytes: file.size || null,
    storage_provider: mode,
  })

  return { url: public_url, object_key, mode }
}

/**
 * Delete a replaced or unwanted object from R2/local storage.
 */
export async function deleteStoredObject({ eventId = null, objectKey }) {
  if (!objectKey) return
  try {
    await client.delete('/storage/object', {
      data: {
        event_id: eventId ? Number(eventId) : null,
        object_key: objectKey,
      },
    })
  } catch {
    // Non-blocking cleanup
  }
}
