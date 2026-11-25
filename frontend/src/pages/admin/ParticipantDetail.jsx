import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import client from '../../api/client'
import Card from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import Spinner from '../../components/ui/Spinner'
import {
  ArrowLeft, Mail, Phone, Building, Tag, Pencil, Trash2, X, Save,
  Download, QrCode, ShieldCheck, FileText, CheckCircle2, Circle,
  Eye, ExternalLink, Calendar, Image as ImageIcon, Camera, Hash,
  CheckSquare, AlignLeft, List, Globe, User, Layers
} from 'lucide-react'
import { getCategoryColor, getMethodBadge, formatDate, resolveMediaUrl } from '../../utils/helpers'

const CATEGORIES = ['STUDENT', 'RESEARCHER', 'PROFESSIONAL', 'SPEAKER', 'OTHER']
const PAYMENT_STATUSES = ['SUCCESS', 'PENDING', 'FAILED']

export default function ParticipantDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [editOpen, setEditOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [previewImage, setPreviewImage] = useState(null) // { url, title }

  const [form, setForm] = useState({
    name: '',
    email: '',
    phone: '',
    institution: '',
    category: 'OTHER',
    payment_status: 'PENDING',
  })
  const [editError, setEditError] = useState('')

  const { data: participant, isLoading, error } = useQuery({
    queryKey: ['participant', id],
    queryFn: () => client.get(`/participants/${id}`).then((r) => r.data),
  })

  // Fetch dynamic form schema for this event
  const { data: eventSchemaData, isLoading: schemaLoading } = useQuery({
    queryKey: ['event-registration-form', participant?.event_id],
    queryFn: () => client.get(`/events/${participant.event_id}/registration-form`).then((r) => r.data),
    enabled: !!participant?.event_id,
  })

  const updateMutation = useMutation({
    mutationFn: (payload) => client.patch(`/participants/${id}`, payload).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['participant', id] })
      queryClient.invalidateQueries({ queryKey: ['participants'] })
      setEditOpen(false)
      setEditError('')
    },
    onError: (err) => {
      setEditError(err.response?.data?.detail || 'Failed to update participant. Please try again.')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => client.delete(`/participants/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['participants'] })
      navigate('/admin/participants')
    },
  })

  const openEdit = () => {
    if (participant) {
      setForm({
        name: participant.name || '',
        email: participant.email || '',
        phone: participant.phone || '',
        institution: participant.institution || '',
        category: participant.category || 'OTHER',
        payment_status: participant.payment_status || 'PENDING',
      })
      setEditError('')
    }
    setEditOpen(true)
  }

  const handleSave = (e) => {
    e.preventDefault()
    if (!form.name.trim()) {
      setEditError('Name is required')
      return
    }
    if (!form.email.trim()) {
      setEditError('Email is required')
      return
    }
    updateMutation.mutate(form)
  }

  if (isLoading) {
    return <div className="flex justify-center py-20"><Spinner size="lg" /></div>
  }

  if (error || !participant) {
    return (
      <div className="text-center py-20 space-y-3">
        <p className="text-gray-500">Participant not found or inaccessible.</p>
        <Button variant="secondary" size="sm" onClick={() => navigate('/admin/participants')}>
          <ArrowLeft className="h-4 w-4 mr-1" /> Back to Participants
        </Button>
      </div>
    )
  }

  // Format static / R2 media URLs safely
  const photoUrl = resolveMediaUrl(participant.photo_url)

  const qrUrl = resolveMediaUrl(participant.qr_code_url)

  const attendanceCount = participant.attendances?.length || 0

  // Resolve dynamic schema fields and custom responses
  const schemaFields = eventSchemaData?.schema?.fields || []
  const customResponses = participant.custom_responses || {}

  // Collect unmatched custom response keys if any
  const matchedFieldIds = new Set(schemaFields.map(f => f.id))
  const unmappedKeys = Object.keys(customResponses).filter(k => !matchedFieldIds.has(k))

  return (
    <div className="space-y-6">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate('/admin/participants')}>
            <ArrowLeft className="h-4 w-4 mr-1" /> Back
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{participant.name}</h1>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-xs text-gray-500">Participant ID: #{participant.id}</span>
              <span className="text-xs text-gray-300">•</span>
              <span className="text-xs text-gray-500">Source: {participant.source || 'ONLINE'}</span>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={openEdit}>
            <Pencil className="h-4 w-4 mr-1" /> Edit Participant
          </Button>
          <Button variant="danger" size="sm" onClick={() => setDeleteOpen(true)}>
            <Trash2 className="h-4 w-4 mr-1" /> Delete
          </Button>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Profile Card */}
        <Card className="lg:col-span-1">
          <div className="text-center pt-2">
            {photoUrl ? (
              <div className="relative inline-block group cursor-pointer" onClick={() => setPreviewImage({ url: photoUrl, title: `${participant.name} - Check-in Photo` })}>
                <img
                  src={photoUrl}
                  alt={participant.name}
                  className="w-32 h-32 rounded-full mx-auto object-cover border-4 border-indigo-100 shadow-sm transition-transform group-hover:scale-105"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none'
                    const fb = document.getElementById(`avatar-fb-${participant.id}`)
                    if (fb) fb.style.display = 'flex'
                  }}
                />
                <div className="absolute inset-0 rounded-full bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white text-xs font-semibold">
                  <Eye className="h-4 w-4 mr-1" /> View Photo
                </div>
                <div
                  id={`avatar-fb-${participant.id}`}
                  style={{ display: 'none' }}
                  className="w-32 h-32 rounded-full mx-auto bg-gradient-to-tr from-indigo-500 to-purple-600 items-center justify-center text-3xl font-bold text-white shadow-sm"
                >
                  {participant.name?.charAt(0).toUpperCase()}
                </div>
              </div>
            ) : (
              <div className="w-32 h-32 rounded-full mx-auto bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center text-3xl font-bold text-white shadow-sm">
                {participant.name?.charAt(0).toUpperCase()}
              </div>
            )}

            <h2 className="mt-4 text-xl font-bold text-gray-900">{participant.name}</h2>
            <div className="mt-2 flex items-center justify-center gap-2 flex-wrap">
              <Badge className={getCategoryColor(participant.category)}>
                {participant.category}
              </Badge>
              <Badge
                className={
                  participant.payment_status === 'SUCCESS'
                    ? 'bg-emerald-100 text-emerald-800'
                    : participant.payment_status === 'FAILED'
                    ? 'bg-rose-100 text-rose-800'
                    : 'bg-amber-100 text-amber-800'
                }
              >
                Payment: {participant.payment_status || 'PENDING'}
              </Badge>
            </div>
          </div>

          <div className="mt-6 space-y-3 border-t border-gray-100 pt-5">
            <InfoRow icon={Mail} label="Email" value={participant.email} />
            <InfoRow icon={Phone} label="Phone" value={participant.phone} />
            <InfoRow icon={Building} label="Institution" value={participant.institution} />
            <InfoRow icon={Tag} label="Registered" value={formatDate(participant.registered_at)} />
            {participant.coupon_code && (
              <InfoRow icon={ShieldCheck} label="Coupon" value={participant.coupon_code} />
            )}
          </div>

          {/* QR Code Section */}
          <div className="mt-6 border-t border-gray-100 pt-5 text-center">
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3 flex items-center justify-center gap-1">
              <QrCode className="h-4 w-4" /> Check-in QR Code
            </p>
            {qrUrl ? (
              <div className="space-y-3">
                <div className="inline-block p-2 bg-white border border-gray-200 rounded-xl shadow-sm">
                  <img
                    src={qrUrl}
                    alt="Participant QR Code"
                    className="w-44 h-44 object-contain mx-auto"
                    onError={(e) => {
                      e.currentTarget.src = `/api/participants/${participant.id}/qrcode`
                    }}
                  />
                </div>
                <div>
                  <a
                    href={qrUrl}
                    download={`participant_${participant.id}_qr.png`}
                    className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:text-primary-dark transition-colors"
                  >
                    <Download className="h-3.5 w-3.5" /> Download QR Code PNG
                  </a>
                </div>
              </div>
            ) : (
              <div className="p-6 bg-gray-50 rounded-lg text-sm text-gray-400">
                No QR code generated yet.
              </div>
            )}
          </div>
        </Card>

        {/* Dynamic Registration Form Responses Card & Attendance History */}
        <div className="lg:col-span-2 space-y-6">
          {/* Complete Dynamic Registration Form Card */}
          <Card
            title={
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <Layers className="h-5 w-5 text-indigo-600" />
                  Registration Form Details
                </span>
                {schemaFields.length > 0 && (
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                    {schemaFields.length} configured fields
                  </span>
                )}
              </div>
            }
          >
            {schemaLoading ? (
              <div className="py-12 flex justify-center"><Spinner size="md" /></div>
            ) : schemaFields.length > 0 ? (
              <div className="space-y-4 pt-2">
                {schemaFields.map((field) => {
                  if (field.type === 'image') return null // static image in builder

                  // Resolve value: custom responses first, or mapped participant attributes
                  let val = customResponses[field.id]
                  if (val === undefined || val === null || val === '') {
                    if (field.mapping === 'name') val = participant.name
                    else if (field.mapping === 'email' || field.type === 'email') val = participant.email
                    else if (field.mapping === 'phone' || field.type === 'phone') val = participant.phone
                    else if (field.mapping === 'institution') val = participant.institution
                    else if (field.mapping === 'category') val = participant.category
                    else if (field.mapping === 'photo' || field.type === 'photo') val = photoUrl
                  }

                  return (
                    <div
                      key={field.id}
                      className="p-3.5 rounded-xl border border-gray-100 bg-gray-50/60 hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex items-center justify-between gap-2 mb-1.5">
                        <span className="text-xs font-bold text-gray-600 uppercase tracking-wider flex items-center gap-1.5">
                          {field.label}
                          {field.required && <span className="text-red-500 font-bold">*</span>}
                        </span>
                        <span className="text-[10px] font-mono text-gray-400 bg-white px-2 py-0.5 rounded border border-gray-200 uppercase">
                          {field.type}
                        </span>
                      </div>

                      {/* Render formatted value */}
                      <DynamicFieldValue
                        field={field}
                        value={val}
                        participant={participant}
                        onPreviewImage={(url, title) => setPreviewImage({ url, title })}
                      />
                    </div>
                  )
                })}

                {/* Additional Unmapped Responses (if any) */}
                {unmappedKeys.length > 0 && (
                  <div className="mt-6 pt-4 border-t border-gray-200">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-3">
                      Additional Submitted Data
                    </h4>
                    <div className="space-y-2.5">
                      {unmappedKeys.map((k) => (
                        <div key={k} className="p-3 bg-gray-50 rounded-lg border border-gray-200 text-sm">
                          <span className="text-xs font-semibold text-gray-500 block mb-1">{k}:</span>
                          <span className="font-medium text-gray-900 break-all">
                            {typeof customResponses[k] === 'object'
                              ? JSON.stringify(customResponses[k])
                              : String(customResponses[k])}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              /* Fallback when event does not have a custom dynamic schema */
              <div className="space-y-3 pt-2">
                <p className="text-xs text-gray-500 mb-4">
                  Standard registration details submitted by this attendee:
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                    <span className="text-xs font-semibold text-gray-500 block">Full Name</span>
                    <span className="text-sm font-semibold text-gray-900 mt-0.5 block">{participant.name}</span>
                  </div>
                  <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                    <span className="text-xs font-semibold text-gray-500 block">Email Address</span>
                    <span className="text-sm font-semibold text-gray-900 mt-0.5 block break-all">{participant.email}</span>
                  </div>
                  <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                    <span className="text-xs font-semibold text-gray-500 block">Phone</span>
                    <span className="text-sm font-semibold text-gray-900 mt-0.5 block">{participant.phone || '—'}</span>
                  </div>
                  <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                    <span className="text-xs font-semibold text-gray-500 block">Institution / Org</span>
                    <span className="text-sm font-semibold text-gray-900 mt-0.5 block">{participant.institution || '—'}</span>
                  </div>
                </div>

                {Object.keys(customResponses).length > 0 && (
                  <div className="mt-4 pt-3 border-t border-gray-200">
                    <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">Submitted Responses</h4>
                    <div className="space-y-2">
                      {Object.entries(customResponses).map(([k, v]) => (
                        <div key={k} className="p-2.5 bg-gray-50 rounded border border-gray-200 text-sm">
                          <span className="text-xs font-semibold text-gray-500 block">{k}</span>
                          <span className="text-gray-900 break-all">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </Card>

          {/* Attendance History Card */}
          <Card title={`Attendance History (${attendanceCount})`}>
            {attendanceCount > 0 ? (
              <div className="mt-2 divide-y divide-gray-100">
                {participant.attendances.map((a) => (
                  <div key={a.id} className="flex items-center justify-between py-3.5">
                    <div>
                      <p className="text-sm font-semibold text-gray-900">
                        {a.session_name || 'Event General Check-in'}
                      </p>
                      <p className="text-xs text-gray-500 mt-0.5">{formatDate(a.marked_at)}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge className={getMethodBadge(a.method)}>{a.method}</Badge>
                      <span className="text-xs text-gray-400">ID #{a.id}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-10 text-gray-400 text-sm">
                <p>No check-in attendance recorded for this participant yet.</p>
                <p className="text-xs text-gray-400 mt-1">Check-ins via QR scanner or Manual lookup will appear here.</p>
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* Image Preview Lightbox Modal */}
      {previewImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 animate-in fade-in duration-150"
          onClick={() => setPreviewImage(null)}
        >
          <div
            className="bg-white rounded-2xl overflow-hidden max-w-2xl w-full shadow-2xl relative"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-100 bg-gray-50">
              <h3 className="font-semibold text-sm text-gray-900">{previewImage.title || 'Image Preview'}</h3>
              <button
                onClick={() => setPreviewImage(null)}
                className="text-gray-400 hover:text-gray-700 p-1 rounded-lg hover:bg-gray-200 transition-colors cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="p-4 flex items-center justify-center bg-gray-900/5 max-h-[75vh] overflow-auto">
              <img
                src={previewImage.url}
                alt={previewImage.title || 'Preview'}
                className="max-w-full max-h-[65vh] object-contain rounded-lg shadow-sm"
              />
            </div>
            <div className="px-5 py-3 bg-gray-50 border-t border-gray-100 flex justify-end">
              <a
                href={previewImage.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-900 text-white rounded-lg text-xs font-semibold hover:bg-gray-800 transition-colors"
              >
                <ExternalLink className="h-3.5 w-3.5" /> Open Full Image
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Edit Participant Modal */}
      {editOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gray-50/50">
              <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                <Pencil className="h-5 w-5 text-primary" /> Edit Participant
              </h2>
              <button
                onClick={() => setEditOpen(false)}
                className="text-gray-400 hover:text-gray-600 p-1 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleSave} className="p-6 space-y-4">
              {editError && (
                <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">
                  {editError}
                </div>
              )}

              <div className="grid sm:grid-cols-2 gap-4">
                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Full Name *</label>
                  <input
                    type="text"
                    required
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="w-full rounded-lg border border-gray-300 px-3.5 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Email Address *</label>
                  <input
                    type="email"
                    required
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    className="w-full rounded-lg border border-gray-300 px-3.5 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Phone Number</label>
                  <input
                    type="text"
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                    className="w-full rounded-lg border border-gray-300 px-3.5 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>

                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Institution / Organization</label>
                  <input
                    type="text"
                    value={form.institution}
                    onChange={(e) => setForm({ ...form, institution: e.target.value })}
                    className="w-full rounded-lg border border-gray-300 px-3.5 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Category</label>
                  <select
                    value={form.category}
                    onChange={(e) => setForm({ ...form, category: e.target.value })}
                    className="w-full rounded-lg border border-gray-300 px-3.5 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 bg-white"
                  >
                    {CATEGORIES.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Payment Status</label>
                  <select
                    value={form.payment_status}
                    onChange={(e) => setForm({ ...form, payment_status: e.target.value })}
                    className="w-full rounded-lg border border-gray-300 px-3.5 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 bg-white"
                  >
                    {PAYMENT_STATUSES.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex gap-3 justify-end pt-4 border-t border-gray-100">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setEditOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={updateMutation.isPending}
                >
                  {updateMutation.isPending ? <Spinner size="sm" /> : <Save className="h-4 w-4 mr-1" />}
                  Save Changes
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center gap-3">
              <div className="rounded-full bg-red-100 p-3 flex-shrink-0">
                <Trash2 className="h-6 w-6 text-red-600" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-gray-900">Delete Participant</h2>
                <p className="text-xs text-gray-500">This action is permanent and cannot be undone.</p>
              </div>
            </div>

            <p className="text-sm text-gray-700">
              Are you sure you want to delete <strong>{participant.name}</strong> ({participant.email})?
            </p>

            {attendanceCount > 0 && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
                <strong>Warning:</strong> This participant has {attendanceCount} recorded check-in attendance record(s). Deleting will permanently remove all associated check-in records.
              </div>
            )}

            {deleteMutation.isError && (
              <p className="text-xs text-red-600">
                {deleteMutation.error?.response?.data?.detail || 'Failed to delete participant. Only administrators can delete records.'}
              </p>
            )}

            <div className="flex gap-3 justify-end pt-3">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setDeleteOpen(false)}
                disabled={deleteMutation.isPending}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={() => deleteMutation.mutate()}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? <Spinner size="sm" /> : <Trash2 className="h-4 w-4 mr-1" />}
                Confirm Delete
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function DynamicFieldValue({ field, value, participant, onPreviewImage }) {
  if (value === undefined || value === null || value === '' || (Array.isArray(value) && value.length === 0)) {
    return <span className="text-gray-400 italic text-sm">Not provided</span>
  }

  // 1. Photo field (Participant profile photo)
  if (field.type === 'photo') {
    const pUrl = typeof value === 'string'
      ? resolveMediaUrl(value)
      : resolveMediaUrl(participant.photo_url)

    if (!pUrl) return <span className="text-gray-400 italic text-sm">No photo uploaded</span>

    return (
      <div className="flex items-center gap-3 mt-1">
        <img
          src={pUrl}
          alt={field.label}
          className="w-16 h-16 rounded-xl object-cover border border-gray-200 shadow-xs cursor-pointer hover:opacity-90"
          onClick={() => onPreviewImage(pUrl, field.label)}
        />
        <div>
          <span className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 rounded font-semibold inline-flex items-center gap-1">
            <CheckCircle2 className="h-3 w-3" /> Participant Photo
          </span>
          <button
            type="button"
            onClick={() => onPreviewImage(pUrl, field.label)}
            className="block mt-1 text-xs text-indigo-600 hover:text-indigo-800 font-medium cursor-pointer"
          >
            Click to view full photo
          </button>
        </div>
      </div>
    )
  }

  // 2. File / Document upload field
  if (field.type === 'file') {
    const isImage = typeof value === 'string' && /\.(jpg|jpeg|png|webp|gif)$/i.test(value)
    if (isImage) {
      const imgUrl = resolveMediaUrl(value)
      return (
        <div className="flex items-center gap-3 mt-1">
          <img
            src={imgUrl}
            alt={field.label}
            className="w-20 h-20 rounded-xl object-cover border border-gray-200 shadow-xs cursor-pointer hover:opacity-90"
            onClick={() => onPreviewImage(imgUrl, field.label)}
          />
          <div>
            <span className="text-xs font-mono text-gray-500 block truncate max-w-xs">{value.split('/').pop()}</span>
            <button
              type="button"
              onClick={() => onPreviewImage(imgUrl, field.label)}
              className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold cursor-pointer mt-1 inline-flex items-center gap-1"
            >
              <Eye className="h-3 w-3" /> Preview Image
            </button>
          </div>
        </div>
      )
    }

    if (typeof value === 'string' && (value.startsWith('/') || value.startsWith('http'))) {
      return (
        <div className="mt-1">
          <a
            href={value}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-200 hover:border-gray-300 rounded-lg text-xs font-semibold text-gray-800 shadow-xs hover:bg-gray-50 transition-colors"
          >
            <FileText className="h-3.5 w-3.5 text-indigo-600" />
            <span>{value.split('/').pop() || 'Download File'}</span>
            <ExternalLink className="h-3 w-3 text-gray-400" />
          </a>
        </div>
      )
    }

    return <span className="font-medium text-sm text-gray-900 break-all">{String(value)}</span>
  }

  // 3. Radio / Dropdown fields (Single Option)
  if (field.type === 'radio' || field.type === 'dropdown') {
    const option = (field.options || []).find((o) => o.value === value || o.label === value)
    const label = option ? option.label : String(value)
    return (
      <div className="mt-0.5">
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-indigo-50 text-indigo-800 border border-indigo-200/80">
          <Circle className="h-2 w-2 fill-indigo-600 text-indigo-600" />
          {label}
        </span>
      </div>
    )
  }

  // 4. Checkbox fields (Multiple Options)
  if (field.type === 'checkbox') {
    const rawArr = Array.isArray(value) ? value : (typeof value === 'string' ? [value] : [])
    const labels = rawArr.map((v) => {
      const opt = (field.options || []).find((o) => o.value === v || o.label === v)
      return opt ? opt.label : String(v)
    })

    return (
      <div className="flex flex-wrap gap-1.5 mt-1">
        {labels.map((lbl, idx) => (
          <span
            key={idx}
            className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-medium bg-purple-50 text-purple-700 border border-purple-200"
          >
            <CheckSquare className="h-3 w-3 text-purple-600" />
            {lbl}
          </span>
        ))}
      </div>
    )
  }

  // 5. Long Text / Textarea
  if (field.type === 'textarea') {
    return (
      <div className="p-3 bg-white rounded-lg border border-gray-200 text-sm text-gray-900 whitespace-pre-wrap mt-1 shadow-2xs">
        {String(value)}
      </div>
    )
  }

  // 6. Standard Text / Email / Phone / Number / Date
  return (
    <div className="mt-0.5">
      <span className="text-sm font-semibold text-gray-900 break-words">
        {String(value)}
      </span>
    </div>
  )
}

function InfoRow({ icon: Icon, label, value }) {
  return (
    <div className="flex items-center gap-3 text-sm">
      <Icon className="h-4 w-4 text-gray-400 flex-shrink-0" />
      <span className="text-gray-500 min-w-24 text-xs font-medium">{label}</span>
      <span className="text-gray-900 font-medium text-sm break-all">{value || '—'}</span>
    </div>
  )
}
