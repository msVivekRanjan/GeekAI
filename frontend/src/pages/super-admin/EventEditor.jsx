import { useState, useEffect } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { ArrowLeft, Save, CreditCard, Shield, Eye, EyeOff, Trash2, Plus, List, UserCheck } from 'lucide-react'
import client from '../../api/client'
import toast from 'react-hot-toast'

const DEFAULT_GUIDELINES = [
  'Each participant must register with a unique, valid email address.',
  'Upload a clear, front-facing photograph for AI face recognition check-in.',
  'Registration fee is non-refundable once paid unless waived by authorized coupon.',
  'Your QR entry ticket will be generated and emailed upon registration.',
  'Please carry a valid photo ID matching your registration details to the venue.',
]

const EMPTY_FORM = {
  name: '', slug: '', description: '', tagline: '',
  logo_url: '', banner_url: '',
  registration_fee: 0,
  cashfree_enabled: false,
  cashfree_app_id: '',
  cashfree_secret_key: '',
  cashfree_env: 'sandbox',
  guidelines: [],
  venue: '', website: '',
  event_date: '', registration_deadline: '',
}

function toLocalDatetime(iso) {
  if (!iso) return ''
  return iso.slice(0, 16) // "2026-03-20T09:00"
}

function toISO(local) {
  if (!local) return null
  return new Date(local).toISOString()
}

export default function EventEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isEdit = !!id

  const [form, setForm] = useState(EMPTY_FORM)
  const [loading, setLoading] = useState(isEdit)
  const [saving, setSaving] = useState(false)
  const [slugDirty, setSlugDirty] = useState(false)
  const [showSecret, setShowSecret] = useState(false)
  const [hasSecret, setHasSecret] = useState(false)

  // Event Admin Credentials State
  const [adminForm, setAdminForm] = useState({
    id: null,
    email: '',
    name: '',
    password: '',
    is_active: true,
  })
  const [hasExistingAdmin, setHasExistingAdmin] = useState(false)
  const [showAdminPassword, setShowAdminPassword] = useState(false)
  const [savingAdmin, setSavingAdmin] = useState(false)

  useEffect(() => {
    if (!isEdit) return
    client.get(`/super-admin/events/${id}`)
      .then(r => {
        const e = r.data
        setForm({
          name: e.name || '',
          slug: e.slug || '',
          description: e.description || '',
          tagline: e.tagline || '',
          logo_url: e.logo_url || '',
          banner_url: e.banner_url || '',
          registration_fee: e.registration_fee || 0,
          cashfree_enabled: e.cashfree_enabled ?? false,
          cashfree_app_id: e.cashfree_app_id || '',
          cashfree_secret_key: '',
          cashfree_env: e.cashfree_env || 'sandbox',
          guidelines: Array.isArray(e.guidelines) ? e.guidelines : [],
          venue: e.venue || '',
          website: e.website || '',
          event_date: toLocalDatetime(e.event_date),
          registration_deadline: toLocalDatetime(e.registration_deadline),
        })
        setHasSecret(!!e.has_cashfree_secret)
        setSlugDirty(true)
      })
      .catch(() => toast.error('Failed to load event'))
      .finally(() => setLoading(false))

    // Fetch existing assigned event admin
    client.get(`/super-admin/events/${id}/admin`)
      .then(res => {
        if (res.data) {
          setAdminForm({
            id: res.data.id,
            email: res.data.email || '',
            name: res.data.name || '',
            password: '',
            is_active: res.data.is_active ?? true,
          })
          setHasExistingAdmin(true)
        }
      })
      .catch(() => {})
  }, [id, isEdit])

  const handleSaveAdmin = async (e) => {
    if (e) e.preventDefault()
    if (!adminForm.email.trim()) {
      toast.error('Admin email is required')
      return
    }
    if (!hasExistingAdmin && (!adminForm.password || adminForm.password.trim().length < 6)) {
      toast.error('Password must be at least 6 characters for a new admin')
      return
    }
    setSavingAdmin(true)
    try {
      const payload = {
        email: adminForm.email.trim(),
        name: adminForm.name.trim() || undefined,
        is_active: adminForm.is_active,
      }
      if (adminForm.password && adminForm.password.trim()) {
        payload.password = adminForm.password.trim()
      }
      const res = await client.post(`/super-admin/events/${id}/admin`, payload)
      setAdminForm(prev => ({
        ...prev,
        id: res.data.id,
        email: res.data.email,
        name: res.data.name || '',
        password: '',
        is_active: res.data.is_active,
      }))
      setHasExistingAdmin(true)
      toast.success(hasExistingAdmin ? 'Admin credentials updated!' : 'Event admin assigned successfully!')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save admin credentials')
    } finally {
      setSavingAdmin(false)
    }
  }

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target
    if (name === 'name' && !slugDirty && !isEdit) {
      setForm(f => ({
        ...f,
        name: value,
        slug: value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''),
      }))
    } else if (name === 'slug') {
      setSlugDirty(true)
      setForm(f => ({ ...f, slug: value.toLowerCase().replace(/[^a-z0-9-]/g, '') }))
    } else if (type === 'checkbox') {
      setForm(f => ({ ...f, [name]: checked }))
    } else {
      setForm(f => ({ ...f, [name]: value }))
    }
  }

  const handleAddGuideline = () => {
    setForm(f => ({ ...f, guidelines: [...(f.guidelines || []), ''] }))
  }

  const handleUpdateGuideline = (idx, text) => {
    setForm(f => {
      const g = [...(f.guidelines || [])]
      g[idx] = text
      return { ...f, guidelines: g }
    })
  }

  const handleRemoveGuideline = (idx) => {
    setForm(f => ({
      ...f,
      guidelines: (f.guidelines || []).filter((_, i) => i !== idx)
    }))
  }

  const handleLoadDefaultGuidelines = () => {
    setForm(f => ({ ...f, guidelines: [...DEFAULT_GUIDELINES] }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const isCfEnabled = !!form.cashfree_enabled
      const payload = {
        ...form,
        registration_fee: isCfEnabled ? (parseInt(form.registration_fee) || 0) : 0,
        cashfree_enabled: isCfEnabled,
        guidelines: (form.guidelines || []).map(g => g.trim()).filter(g => g.length > 0),
        event_date: toISO(form.event_date),
        registration_deadline: toISO(form.registration_deadline),
      }
      // Only send secret key if non-empty, otherwise omit to keep existing secret
      if (!payload.cashfree_secret_key) {
        delete payload.cashfree_secret_key
      }

      // Remove empty strings → null for optional text fields
      Object.keys(payload).forEach(k => {
        if (payload[k] === '') payload[k] = null
      })

      if (isEdit) {
        await client.patch(`/super-admin/events/${id}`, payload)
        toast.success('Event updated!')
        if (form.cashfree_secret_key) {
          setHasSecret(true)
          setForm(f => ({ ...f, cashfree_secret_key: '' }))
        }
      } else {
        const r = await client.post('/super-admin/events', payload)
        if (adminForm.email.trim() && adminForm.password.trim()) {
          try {
            await client.post(`/super-admin/events/${r.data.id}/admin`, {
              email: adminForm.email.trim(),
              name: adminForm.name.trim() || undefined,
              password: adminForm.password.trim(),
              is_active: adminForm.is_active,
            })
          } catch (adminErr) {
            toast.error(adminErr.response?.data?.detail || 'Event created, but failed to assign admin credentials')
          }
        }
        toast.success('Event created!')
        navigate(`/super-admin/events/${r.data.id}/edit`, { replace: true })
      }
    } catch (err) {
      const detail = err.response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : 'Failed to save event')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="sa-state" role="status">Loading event…</div>

  return (
    <form onSubmit={handleSubmit} className="sa-page sa-editor">
      <div className="sa-page-header sa-sticky">
        <div className="sa-page-heading">
          <Link to="/super-admin/events" className="sa-icon sa-back" aria-label="Back to events"><ArrowLeft size={19} /></Link>
          <h1>{isEdit ? 'Edit Event' : 'New Event'}</h1>
        </div>
        <div className="sa-header-actions">
          <Link to="/super-admin/events" className="sa-button sa-quiet">Cancel</Link>
          {isEdit && <Link to={`/super-admin/events/${id}/form-builder`} className="sa-button">Configure Form Builder</Link>}
          <button type="submit" disabled={saving} className="sa-button sa-primary">
            <Save size={16} /> {saving ? 'Saving…' : isEdit ? 'Save Changes' : 'Create Event'}
          </button>
        </div>
      </div>

      <div className="sa-editor-grid">
        <section className="sa-panel sa-form-panel">
          <h2>Event Identity</h2>
          <div className="sa-form-pair">
            <label>Event Name <span aria-hidden="true">*</span>
              <input name="name" value={form.name} onChange={handleChange} required placeholder="Odisha AI Conference 2026" />
            </label>
            <label>URL Slug <span aria-hidden="true">*</span>
              <span className="sa-affixed">
                <code aria-hidden="true">/events/</code>
                <input name="slug" value={form.slug} onChange={handleChange} required
                  pattern="[a-z0-9-]+" title="Only lowercase letters, numbers and hyphens"
                  placeholder="oaic" disabled={isEdit} aria-describedby={isEdit ? 'event-slug-hint' : undefined} />
              </span>
              {isEdit && <small id="event-slug-hint">The slug is fixed after creation.</small>}
            </label>
          </div>
          <label>Tagline
            <input name="tagline" value={form.tagline} onChange={handleChange} placeholder="Short event tagline" />
          </label>
          <label>Description
            <textarea name="description" value={form.description} onChange={handleChange} rows={3}
              placeholder="Describe the event…" />
          </label>
        </section>
        <div className="sa-form-column">
          <section className="sa-panel sa-form-panel">
            <h2>Logistics</h2>
            <div className="sa-form-pair">
              <label>Event Date<input name="event_date" type="datetime-local" value={form.event_date} onChange={handleChange} /></label>
              <label>Registration Deadline<input name="registration_deadline" type="datetime-local" value={form.registration_deadline} onChange={handleChange} /></label>
            </div>
            <label>Venue<input name="venue" value={form.venue} onChange={handleChange} placeholder="Venue name" /></label>
            <label>Event Website
              <input name="website" type="url" value={form.website} onChange={handleChange} placeholder="https://oaic.in" />
            </label>
          </section>
          <section className="sa-panel sa-form-panel">
            <h2>Branding</h2>
            <div className="sa-form-pair">
              <label>Logo URL<input name="logo_url" value={form.logo_url} onChange={handleChange} placeholder="https://…" /><small>Event logo image.</small></label>
              <label>Banner URL<input name="banner_url" value={form.banner_url} onChange={handleChange} placeholder="https://…" /><small>Event banner image.</small></label>
            </div>
          </section>
        </div>
      </div>
      <div className="sa-editor-grid sa-event-settings">
        {/* Cashfree Payment Settings Card */}
        <div className="sa-panel sa-settings-panel p-6 space-y-5">
          <div className="flex items-center justify-between border-b border-gray-100 pb-3">
            <div className="flex items-center gap-2">
              <CreditCard className="h-5 w-5 text-gray-700" />
              <h3 className="font-semibold text-gray-900">Payment Settings (Cashfree)</h3>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                name="cashfree_enabled"
                checked={form.cashfree_enabled}
                onChange={handleChange}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
              <span className="ml-3 text-sm font-medium text-gray-700">
                {form.cashfree_enabled ? 'Enabled' : 'Disabled'}
              </span>
            </label>
          </div>

          <p className="text-xs text-gray-500">
            {form.cashfree_enabled
              ? 'Cashfree payments are enabled. Configure the registration fee and Cashfree credentials below. Participants will complete payment during registration.'
              : 'Cashfree payments are disabled. Registration will proceed directly without payment or payment-related restrictions (Google Forms-like flow).'}
          </p>

          {form.cashfree_enabled && (
            <div className="space-y-4 pt-2">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Registration Fee (in Paise) *</label>
                <div className="flex items-center gap-2">
                  <input
                    name="registration_fee"
                    type="number"
                    min="0"
                    value={form.registration_fee}
                    onChange={handleChange}
                    required={form.cashfree_enabled}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-gray-900 focus:border-transparent outline-none"
                    placeholder="30000"
                  />
                  <span className="text-sm font-semibold text-gray-700 whitespace-nowrap bg-gray-50 border border-gray-200 px-3 py-2 rounded-lg">
                    = ₹{(parseInt(form.registration_fee) / 100 || 0).toFixed(0)}
                  </span>
                </div>
                <p className="text-xs text-gray-400 mt-1">Amount to charge participant in Paise (e.g. 30000 = ₹300, 50000 = ₹500).</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Environment *
                  </label>
                  <select
                    name="cashfree_env"
                    value={form.cashfree_env}
                    onChange={handleChange}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-gray-900 focus:border-transparent outline-none bg-white"
                  >
                    <option value="sandbox">Sandbox (Testing / Test Mode)</option>
                    <option value="production">Production (Live Gateway)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Cashfree App ID (Client ID)
                  </label>
                  <input
                    name="cashfree_app_id"
                    value={form.cashfree_app_id}
                    onChange={handleChange}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-gray-900 focus:border-transparent outline-none"
                    placeholder="e.g. CF_APP_12345"
                  />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-sm font-medium text-gray-700">
                    Cashfree Secret Key
                  </label>
                  {hasSecret && (
                    <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200">
                      <Shield className="h-3 w-3" /> Configured & Secured
                    </span>
                  )}
                </div>
                <div className="relative">
                  <input
                    name="cashfree_secret_key"
                    type={showSecret ? 'text' : 'password'}
                    value={form.cashfree_secret_key}
                    onChange={handleChange}
                    className="w-full border border-gray-300 rounded-lg pl-3 pr-10 py-2 text-sm font-mono focus:ring-2 focus:ring-gray-900 focus:border-transparent outline-none"
                    placeholder={hasSecret ? '•••••••••••••••• (Leave blank to keep existing key)' : 'Enter Cashfree Secret Key'}
                  />
                  <button
                    type="button"
                    onClick={() => setShowSecret(s => !s)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 cursor-pointer"
                  >
                    {showSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                <p className="text-xs text-gray-400 mt-1">
                  Secret keys are encrypted and never transmitted to participant browsers.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Event Admin Credentials Card */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-5">
          <div className="flex items-center justify-between border-b border-gray-100 pb-3">
            <div className="flex items-center gap-2">
              <UserCheck className="h-5 w-5 text-gray-700" />
              <h3 className="font-semibold text-gray-900">Event Admin Credentials</h3>
            </div>
            {hasExistingAdmin ? (
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-md border border-emerald-200">
                <Shield className="h-3 w-3" /> Admin Assigned &amp; Scoped
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-700 bg-amber-50 px-2.5 py-1 rounded-md border border-amber-200">
                No Admin Assigned
              </span>
            )}
          </div>

          <p className="text-xs text-gray-500">
            Assign, create, or modify the login email and password for this event's dedicated admin.
            The admin will have full access strictly scoped to this event ({form.name || 'this event'}).
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Admin Login Email *
              </label>
              <input
                type="email"
                value={adminForm.email}
                onChange={(e) => setAdminForm(prev => ({ ...prev, email: e.target.value }))}
                placeholder="e.g. oaic_admin@geekai.in"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-gray-900 focus:border-transparent outline-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Admin Display Name
              </label>
              <input
                type="text"
                value={adminForm.name}
                onChange={(e) => setAdminForm(prev => ({ ...prev, name: e.target.value }))}
                placeholder="e.g. Odisha AI Conference Admin"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-gray-900 focus:border-transparent outline-none"
              />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-sm font-medium text-gray-700">
                {hasExistingAdmin ? 'Update Login Password' : 'Login Password *'}
              </label>
              {hasExistingAdmin && (
                <span className="text-xs text-gray-400">
                  Leave blank to keep current password
                </span>
              )}
            </div>
            <div className="relative">
              <input
                type={showAdminPassword ? 'text' : 'password'}
                value={adminForm.password}
                onChange={(e) => setAdminForm(prev => ({ ...prev, password: e.target.value }))}
                placeholder={hasExistingAdmin ? '•••••••• (Leave blank to keep existing password)' : 'Enter password (min 6 characters)'}
                className="w-full border border-gray-300 rounded-lg pl-3 pr-10 py-2 text-sm font-mono focus:ring-2 focus:ring-gray-900 focus:border-transparent outline-none"
              />
              <button
                type="button"
                onClick={() => setShowAdminPassword(s => !s)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 cursor-pointer"
              >
                {showAdminPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <p className="text-xs text-gray-400 mt-1">
              Passwords are securely hashed using bcrypt. Existing passwords are never exposed or transmitted in plaintext.
            </p>
          </div>

          <div className="flex items-center justify-between pt-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={adminForm.is_active}
                onChange={(e) => setAdminForm(prev => ({ ...prev, is_active: e.target.checked }))}
                className="h-4 w-4 rounded border-gray-300 text-gray-900 focus:ring-gray-900"
              />
              <span className="text-sm font-medium text-gray-700 select-none">
                Admin account active
              </span>
            </label>

            {isEdit && (
              <button
                type="button"
                onClick={handleSaveAdmin}
                disabled={savingAdmin}
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-gray-900 text-white rounded-lg text-xs font-semibold hover:bg-gray-800 transition-colors cursor-pointer disabled:opacity-60"
              >
                <Save className="h-3.5 w-3.5" />
                {savingAdmin ? 'Saving Credentials…' : hasExistingAdmin ? 'Update Credentials' : 'Assign Admin'}
              </button>
            )}
          </div>
        </div>

        {/* Registration Guidelines Card */}
        <div className="sa-panel sa-settings-panel p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-gray-100 pb-3">
            <div className="flex items-center gap-2">
              <List className="h-5 w-5 text-gray-700" />
              <h3 className="font-semibold text-gray-900">Registration Guidelines</h3>
            </div>
            <button
              type="button"
              onClick={handleLoadDefaultGuidelines}
              className="sa-text-action"
            >
              Load Preset Guidelines
            </button>
          </div>

          <p className="text-xs text-gray-500">
            Configure guidelines, terms, or instructions displayed to attendees on the public event registration page.
          </p>

          <div className="space-y-2.5">
            {(form.guidelines || []).map((guide, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <span className="text-xs font-mono text-gray-400 w-5 text-right">{idx + 1}.</span>
                <input
                  value={guide}
                  onChange={e => handleUpdateGuideline(idx, e.target.value)}
                  className="flex-1 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-gray-900 focus:border-transparent outline-none"
                  placeholder={`Guideline ${idx + 1}`}
                />
                <button
                  type="button"
                  onClick={() => handleRemoveGuideline(idx)}
                  className="p-1.5 text-gray-400 hover:text-red-600 cursor-pointer transition-colors"
                  title="Remove guideline"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}

            <button
              type="button"
              onClick={handleAddGuideline}
              className="inline-flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-800 font-medium cursor-pointer transition-colors pt-1"
            >
              <Plus className="h-3.5 w-3.5" /> + Add Guideline Item
            </button>
          </div>
        </div>

      </div>
    </form>
  )
}
