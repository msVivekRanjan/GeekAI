import { useState, useEffect, useRef } from 'react'
import { Link, useLocation, useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRight, ArrowUpRight, Calendar, ChevronDown, LockKeyhole, MapPin, Ticket } from 'lucide-react'
import { eventDate, eventFee } from '../utils/eventDisplay'
import EventPhoto from '../components/public/EventPhoto'
import { oaicOrganizerLogos } from '../content/oaicLogos'
import client from '../api/client'
import { uploadViaPresignedUrl } from '../utils/upload'
import toast from 'react-hot-toast'

const CATEGORIES = [
  { value: 'STUDENT', label: 'Student' },
  { value: 'RESEARCHER', label: 'Researcher' },
  { value: 'PROFESSIONAL', label: 'Professional' },
  { value: 'SPEAKER', label: 'Speaker' },
  { value: 'OTHER', label: 'Other' },
]

const OAIC_GUIDELINES = [
  'Registration is open to students, researchers, professionals, and speakers.',
  'Each participant must register with a unique email address.',
  'Upload a clear, front-facing photograph for AI-powered face recognition at check-in.',
  'The registration fee of ₹300 is non-refundable once paid (unless using an authorized waiver coupon).',
  'Your QR code will be emailed after successful registration — keep it handy for session entry.',
  'Sessions may have limited capacity; check-in is first-come, first-served.',
  'For queries, contact info@oaic.in.',
]

export default function EventRegister() {
  const { eventSlug } = useParams()
  return <EventRegistration key={eventSlug} eventSlug={eventSlug} />
}

function EventRegistration({ eventSlug }) {
  const navigate = useNavigate()
  const { hash } = useLocation()
  const recoveryRef = useRef(null)
  const photoSection = useRef(null)

  const [event, setEvent] = useState(null)
  const [sessions, setSessions] = useState([])
  const [eventLoading, setEventLoading] = useState(true)

  const [form, setForm] = useState({
    name: '', email: '', phone: '', institution: '', category: 'STUDENT',
  })
  const [photo, setPhoto] = useState(null)
  const [photoConsent, setPhotoConsent] = useState(false)
  const [loading, setLoading] = useState(false)
  const [loadAttempt, setLoadAttempt] = useState(0)

  // Payment recovery state
  const [paidOrderId, setPaidOrderId] = useState(null)
  const [recoverableOrder, setRecoverableOrder] = useState(null)
  const [manualOrderId, setManualOrderId] = useState('')
  const [verifyingManualOrder, setVerifyingManualOrder] = useState(false)

  // Coupon state
  const [couponCode, setCouponCode] = useState('')
  const [appliedCoupon, setAppliedCoupon] = useState(null)
  const [validatingCoupon, setValidatingCoupon] = useState(false)

  // Dynamic form schema state
  const [customFormSchema, setCustomFormSchema] = useState(null) // null = not loaded, false = no schema
  const [customResponses, setCustomResponses] = useState({}) // {field_id: value}

  /* ── Check for uncompleted paid order in localStorage ── */
  useEffect(() => {
    try {
      const saved = localStorage.getItem(`geekai_paid_order_${eventSlug}`)
      if (saved) {
        const parsed = JSON.parse(saved)
        // Keep recoverable if within 24 hours
        if (parsed.order_id && parsed.timestamp && Date.now() - parsed.timestamp < 24 * 3600 * 1000) {
          setRecoverableOrder(parsed)
        } else {
          localStorage.removeItem(`geekai_paid_order_${eventSlug}`)
        }
      }
    } catch (e) {
      // ignore JSON errors
    }
  }, [eventSlug])

  /* ── Fetch event + sessions ── */
  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      try {
        const [evtRes, sessRes, formRes] = await Promise.all([
          client.get(`/events/${eventSlug}`, { signal: controller.signal }),
          client.get(`/events/${eventSlug}/sessions`, { signal: controller.signal }),
          client.get(`/events/${eventSlug}/registration-form`, { signal: controller.signal }).catch(() => null),
        ])
        setEvent(evtRes.data)
        setSessions(sessRes.data)
        if (formRes?.data?.has_custom_form && formRes.data.schema?.fields?.length) {
          setCustomFormSchema(formRes.data.schema.fields.sort((a, b) => a.order - b.order))
        }
      } catch (err) {
        if (controller.signal.aborted) return
        if (err.response?.status === 404) {
          navigate('/', { replace: true })
        } else {
          toast.error('Failed to load event details')
        }
      } finally {
        if (!controller.signal.aborted) setEventLoading(false)
      }
    }
    load()
    return () => controller.abort()
  }, [eventSlug, navigate, loadAttempt])

  useEffect(() => {
    if (eventLoading) return
    if (hash === '#recover-order' && recoveryRef.current) {
      recoveryRef.current.open = true
      recoveryRef.current.scrollIntoView({ block: 'center' })
      recoveryRef.current.querySelector('input')?.focus({ preventScroll: true })
    } else {
      window.scrollTo(0, 0)
    }
  }, [hash, eventLoading])

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const handleFileUpload = async (fieldId, file) => {
    if (!file) return
    const toastId = toast.loading('Uploading file…')
    try {
      const res = await uploadViaPresignedUrl({
        file,
        eventId: event?.id,
        eventSlug,
        category: 'documents',
      })
      setCustomResponses(prev => ({ ...prev, [fieldId]: res.url }))
      toast.success('File uploaded successfully!', { id: toastId })
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || 'Failed to upload file', { id: toastId })
    }
  }

  /* ── Apply Coupon Code ── */
  const handleApplyCoupon = async () => {
    if (!couponCode.trim()) {
      toast.error('Please enter a coupon code')
      return
    }
    setValidatingCoupon(true)
    try {
      const res = await client.post(`/events/${eventSlug}/validate-coupon`, {
        code: couponCode.trim(),
      })
      setAppliedCoupon(res.data)
      toast.success(res.data.message || 'Coupon applied! Registration fee waived.')
    } catch (err) {
      const msg = err.response?.data?.detail || 'Invalid or expired coupon code'
      toast.error(typeof msg === 'string' ? msg : 'Invalid coupon code')
      setAppliedCoupon(null)
    } finally {
      setValidatingCoupon(false)
    }
  }

  const handleRemoveCoupon = () => {
    setAppliedCoupon(null)
    setCouponCode('')
    toast.success('Coupon removed')
  }

  /* ── Resolve participant attributes from dynamic form or static form ── */
  const resolveParticipantData = () => {
    if (!customFormSchema || customFormSchema.length === 0) {
      return {
        name: form.name.trim(),
        email: form.email.trim().toLowerCase(),
        phone: form.phone.trim(),
        institution: form.institution.trim(),
        category: form.category || 'OTHER',
        photo: photo,
      }
    }

    let resolvedName = ''
    let resolvedEmail = ''
    let resolvedPhone = ''
    let resolvedInstitution = ''
    let resolvedCategory = 'OTHER'

    customFormSchema.forEach(field => {
      const val = customResponses[field.id]
      if (val === undefined || val === null || val === '') return

      const mapping = field.mapping
      const labelLower = (field.label || '').toLowerCase()

      if (mapping === 'name' || (!resolvedName && (labelLower.includes('name') || labelLower.includes('attendee')))) {
        resolvedName = typeof val === 'string' ? val.trim() : String(val)
      } else if (mapping === 'email' || field.type === 'email' || (!resolvedEmail && (labelLower.includes('email') || labelLower.includes('mail')))) {
        resolvedEmail = typeof val === 'string' ? val.trim().toLowerCase() : String(val).toLowerCase()
      } else if (mapping === 'phone' || field.type === 'phone' || (!resolvedPhone && (labelLower.includes('phone') || labelLower.includes('mobile') || labelLower.includes('contact')))) {
        resolvedPhone = typeof val === 'string' ? val.trim() : String(val)
      } else if (mapping === 'institution' || (!resolvedInstitution && (labelLower.includes('institution') || labelLower.includes('college') || labelLower.includes('organization') || labelLower.includes('company') || labelLower.includes('university')))) {
        resolvedInstitution = typeof val === 'string' ? val.trim() : String(val)
      } else if (mapping === 'category' || labelLower.includes('category')) {
        resolvedCategory = typeof val === 'string' ? val : String(val)
      }
    })

    if (!resolvedName) {
      const firstText = customFormSchema.find(f => f.type === 'text' && customResponses[f.id])
      resolvedName = firstText ? String(customResponses[firstText.id]).trim() : 'Participant'
    }

    return {
      name: resolvedName,
      email: resolvedEmail,
      phone: resolvedPhone,
      institution: resolvedInstitution,
      category: resolvedCategory,
      photo: photo,
    }
  }

  /* ── Submit registration (after payment or coupon bypass) ── */
  const submitRegistration = async (paymentOrderId = null, dataOverride = null) => {
    const data = dataOverride || resolveParticipantData()
    const fd = new FormData()
    fd.append('name', data.name)
    fd.append('email', data.email)
    if (data.phone) fd.append('phone', data.phone)
    if (data.institution) fd.append('institution', data.institution)
    fd.append('category', data.category)
    if (data.photo) {
      if (event?.r2_enabled) {
        const uploaded = await uploadViaPresignedUrl({
          file: data.photo,
          eventId: event?.id,
          eventSlug,
          category: 'participant_photos',
        })
        fd.append('photo_url', uploaded.url)
        fd.append('photo_object_key', uploaded.object_key)
      } else {
        fd.append('photo', data.photo)
      }
    }
    fd.append('source', 'ONLINE')
    if (event?.id) fd.append('event_id', String(event.id))

    // Append custom form responses as JSON string
    if (customFormSchema && Object.keys(customResponses).length > 0) {
      fd.append('custom_responses', JSON.stringify(customResponses))
    }

    if (!isPaymentEnabled) {
      fd.append('payment_status', 'SUCCESS')
    } else if (appliedCoupon) {
      fd.append('coupon_code', appliedCoupon.code)
      fd.append('payment_status', 'SUCCESS')
    } else if (paymentOrderId) {
      fd.append('payment_order_id', paymentOrderId)
      fd.append('payment_status', 'SUCCESS')
    }

    const { data: attendee } = await client.post('/participants/', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })

    // Registration succeeded: clean up any stored recovery order
    try {
      localStorage.removeItem(`geekai_paid_order_${eventSlug}`)
    } catch (e) {}
    setPaidOrderId(null)
    setRecoverableOrder(null)
    navigate(`/events/${eventSlug}/success`, {
      replace: true,
      state: {
        event: { name: event.name, event_date: event.event_date, venue: event.venue, slug: eventSlug },
        attendee: {
          id: attendee.id, name: attendee.name, email: attendee.email,
          institution: attendee.institution, category: attendee.category,
          qr: attendee.qr_code_url, photo: attendee.photo_url, orderId: paymentOrderId,
        },
      },
    })
  }

  const handleUseRecoverableOrder = (rec) => {
    setAppliedCoupon(null)
    setPaidOrderId(rec.order_id)
    if (rec.email && !form.email) setForm(prev => ({ ...prev, email: rec.email }))
    if (rec.name && !form.name) setForm(prev => ({ ...prev, name: rec.name }))
    if (customFormSchema && customFormSchema.length > 0) {
      const emailField = customFormSchema.find(f => f.mapping === 'email' || f.type === 'email')
      if (emailField && rec.email) {
        setCustomResponses(prev => ({ ...prev, [emailField.id]: rec.email }))
      }
      const nameField = customFormSchema.find(f => f.mapping === 'name' || f.label?.toLowerCase().includes('name'))
      if (nameField && rec.name) {
        setCustomResponses(prev => ({ ...prev, [nameField.id]: rec.name }))
      }
    }
  }

  const handleDismissRecoverableOrder = () => {
    try {
      localStorage.removeItem(`geekai_paid_order_${eventSlug}`)
    } catch (e) {}
    setRecoverableOrder(null)
  }

  const handleVerifyManualOrder = async () => {
    if (!manualOrderId.trim()) {
      toast.error('Please enter an order ID')
      return
    }
    setVerifyingManualOrder(true)
    try {
      const res = await client.post('/payments/verify', {
        order_id: manualOrderId.trim(),
      })
      if (res.data.paid) {
        setAppliedCoupon(null)
        setPaidOrderId(manualOrderId.trim())
      } else {
        toast.error(`Order ${manualOrderId.trim()} is not marked as paid (${res.data.order_status}).`)
      }
    } catch (err) {
      const msg = err.response?.data?.detail || 'Could not verify order'
      toast.error(typeof msg === 'string' ? msg : 'Could not verify order')
    } finally {
      setVerifyingManualOrder(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    const participantData = resolveParticipantData()

    if (customFormSchema && customFormSchema.length > 0) {
      // Validate dynamic form fields
      for (const field of customFormSchema) {
        if (field.type === 'image') continue

        if (field.type === 'photo') {
          if (field.required && !photo) {
            photoSection.current?.querySelector('button')?.focus()
            toast.error(`Please capture or upload "${field.label}"`)
            return
          }
          if (photo && !photoConsent) {
            toast.error('Please consent to photo usage for face recognition')
            return
          }
        } else if (field.required) {
          const val = customResponses[field.id]
          if (val === undefined || val === null || val === '' || (Array.isArray(val) && val.length === 0)) {
            toast.error(`Please fill in required field: "${field.label}"`)
            return
          }
        }
      }

      if (!participantData.email || !participantData.email.includes('@')) {
        toast.error('Please enter a valid email address')
        return
      }
    } else {
      // Legacy static form validation
      if (!photo) {
        photoSection.current?.querySelector('button')?.focus()
        toast.error('Please capture or upload a photo')
        return
      }
      if (!photoConsent) {
        toast.error('Please consent to photo usage for face recognition')
        return
      }
    }

    setLoading(true)
    try {
      const isPaymentEnabled = !!(event?.cashfree_enabled && event?.registration_fee > 0)

      // Case 1: Cashfree disabled, or coupon applied, or free event -> direct Google Forms-like submission
      if (!isPaymentEnabled || appliedCoupon) {
        await submitRegistration(null, participantData)
        return
      }

      // Case 2: Already verified payment order available -> complete registration directly!
      if (paidOrderId) {
        await submitRegistration(paidOrderId, participantData)
        return
      }

      // Case 3: Need to create and execute payment on Cashfree
      /* Create Cashfree order */
      const orderRes = await client.post('/payments/create-order', {
        event_slug: eventSlug,
        amount: event.registration_fee,
        customer_name: participantData.name || 'Participant',
        customer_email: participantData.email,
        customer_phone: participantData.phone || '9999999999',
      })
      const { payment_session_id, order_id } = orderRes.data

      /* Load Cashfree SDK and open checkout modal */
      const { load } = await import('@cashfreepayments/cashfree-js')
      const cfMode = event.cashfree_env === 'production' ? 'production' : 'sandbox'
      const cashfree = await load({ mode: cfMode })

      await cashfree.checkout({
        paymentSessionId: payment_session_id,
        redirectTarget: '_modal',
      })

      /* Verify payment */
      const verifyRes = await client.post('/payments/verify', { order_id })
      if (verifyRes.data.paid) {
        // Payment is confirmed by Cashfree! Store immediately in state and localStorage so user is never re-charged!
        setPaidOrderId(order_id)
        try {
          localStorage.setItem(`geekai_paid_order_${eventSlug}`, JSON.stringify({
            order_id,
            email: participantData.email,
            name: participantData.name,
            timestamp: Date.now(),
          }))
        } catch (e) {}

        await submitRegistration(order_id, participantData)
      } else {
        toast.error('Payment was not completed. Please try again.')
      }
    } catch (err) {
      const msg = err.response?.data?.detail || 'Registration failed'
      toast.error(typeof msg === 'string' ? msg : 'Registration failed')
    } finally {
      setLoading(false)
    }
  }


  if (eventLoading) return <div className="public-width route-state" role="status">Loading event…</div>
  if (!event) return (
    <div className="public-width route-state">
      <p>Event details couldn’t load.</p>
      <button className="public-button" onClick={() => { setEventLoading(true); setLoadAttempt(loadAttempt + 1) }}>Try again</button>
    </div>
  )

  const isPaymentEnabled = !!(event?.cashfree_enabled && event?.registration_fee > 0)
  const amountDue = isPaymentEnabled && !paidOrderId && !appliedCoupon ? event.registration_fee : 0
  const submitLabel = loading ? 'Processing…' : amountDue > 0 ? 'Pay & Register' : 'Complete Registration'

  return (
    <div className="public-width checkout">
      <Link className="back-link" to="/#active-events"><ArrowLeft size={16} /> Back to Events</Link>
      <div className="checkout-grid">
        <aside className="checkout-aside" aria-label="Event details">
          <section className="event-summary">
            {eventSlug === 'oaic' ? (
              <ul className="summary-organizers" aria-label="OAIC organizers and partners">
                {oaicOrganizerLogos.map(({ src, alt, width, height }) => <li key={src}><img src={src} width={width} height={height} alt={alt} /></li>)}
              </ul>
            ) : (
              isPaymentEnabled && (
                <div className="summary-top"><Ticket size={24} strokeWidth={1.5} /><span className="fee mono">{eventFee(event.registration_fee)}</span></div>
              )
            )}
            <h1>{event.name}</h1>
            {event.tagline && <p>{event.tagline}</p>}
            <div className="summary-meta">
              <span><Calendar size={16} /> {eventDate(event.event_date)}</span>
              {event.venue && <span><MapPin size={16} /> {event.venue}</span>}
            </div>
            {eventSlug === 'oaic' && (
              <p className="summary-details-link">
                For full schedule, tracks &amp; event details, visit{' '}
                <a href="https://www.oaic.in/" target="_blank" rel="noopener noreferrer">oaic.in <ArrowUpRight size={14} aria-hidden="true" /></a>
              </p>
            )}
          </section>
          {((event.guidelines && event.guidelines.length > 0) || eventSlug === 'oaic') && (
            <details className="guidelines disclosure">
              <summary>Registration Guidelines{isPaymentEnabled ? ' & Refund Policy' : ''} <ChevronDown size={18} /></summary>
              <ol>
                {((event.guidelines && event.guidelines.length > 0) ? event.guidelines : OAIC_GUIDELINES)
                  .filter(item => isPaymentEnabled || (!item.toLowerCase().includes('fee') && !item.toLowerCase().includes('₹') && !item.toLowerCase().includes('refund')))
                  .map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
              </ol>
            </details>
          )}
        </aside>

        <form id="event-registration" className="checkout-form" onSubmit={handleSubmit}>
          {/* ── Dynamic form if custom schema configured, else fallback to standard legacy form ── */}
          {customFormSchema && customFormSchema.length > 0 ? (
            <section className="form-section" aria-labelledby="dynamic-reg-title">
              <h2 id="dynamic-reg-title">Registration details</h2>
              <div className="field-grid">
                {customFormSchema.map(field => {
                  if (field.type === 'image') {
                    if (!field.image_url) return null
                    return (
                      <div key={field.id} className="full-width form-image-block" style={{ margin: '0.75rem 0' }}>
                        {field.label && field.label !== 'Image' && (
                          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--ink)' }}>
                            {field.label}
                          </h3>
                        )}
                        <div style={{ width: '100%', display: 'flex', justifyContent: 'center' }}>
                          <img
                            src={field.image_url}
                            alt={field.label || 'Event illustration'}
                            style={{
                              maxWidth: '100%',
                              height: 'auto',
                              display: 'block',
                              objectFit: 'contain',
                              borderRadius: '8px',
                            }}
                          />
                        </div>
                        {field.help_text && (
                          <p style={{ fontSize: '0.82rem', color: '#6b7280', marginTop: '0.35rem', textAlign: 'center' }}>
                            {field.help_text}
                          </p>
                        )}
                      </div>
                    )
                  }

                  if (field.type === 'photo') {
                    return (
                      <div key={field.id} className="full-width photo-field-block" ref={photoSection} style={{ marginTop: '0.5rem', marginBottom: '0.5rem' }}>
                        <label style={{ display: 'block', fontWeight: 600, marginBottom: '0.25rem' }}>
                          {field.label}
                          {field.required && <span aria-hidden="true" style={{ color: 'var(--red,#dc2626)', marginLeft: 2 }}>*</span>}
                        </label>
                        {field.help_text && <small style={{ display: 'block', color: '#6b7280', marginBottom: 6 }}>{field.help_text}</small>}
                        <EventPhoto photo={photo} onChange={setPhoto} />
                        <p className="privacy-note"><LockKeyhole size={15} /> Your photo is used for AI face recognition at event check-in.</p>
                        <label className="check-row" style={{ marginTop: 8 }}>
                          <input
                            type="checkbox"
                            checked={photoConsent}
                            onChange={event => setPhotoConsent(event.target.checked)}
                            required={field.required}
                          />
                          <span>I consent to using my photo for face recognition at this event.</span>
                        </label>
                      </div>
                    )
                  }

                  const val = customResponses[field.id] ?? ''
                  const setVal = (v) => setCustomResponses(prev => ({ ...prev, [field.id]: v }))

                  if (field.type === 'radio') {
                    return (
                      <fieldset key={field.id} className="field-group full-width" style={{ border: 'none', padding: 0, margin: 0 }}>
                        <legend className="field-label" style={{ display: 'block', fontSize: '.83rem', fontWeight: 750, color: 'var(--ink)', marginBottom: 4 }}>
                          {field.label}
                          {field.required && <span aria-hidden="true" style={{ color: 'var(--red,#dc2626)', marginLeft: 2 }}>*</span>}
                        </legend>
                        {field.help_text && <small style={{ display: 'block', color: '#6b7280', marginBottom: 6 }}>{field.help_text}</small>}
                        <div className="radio-options-row">
                          {(field.options || []).map(o => {
                            const isChecked = val === o.value
                            return (
                              <label
                                key={o.value}
                                className={`radio-option ${isChecked ? 'selected' : ''}`}
                              >
                                <input
                                  type="radio"
                                  name={field.id}
                                  value={o.value}
                                  checked={isChecked}
                                  onChange={() => setVal(o.value)}
                                  required={field.required && !val}
                                />
                                <span className="option-label">{o.label}</span>
                              </label>
                            )
                          })}
                        </div>
                      </fieldset>
                    )
                  }

                  if (field.type === 'checkbox') {
                    return (
                      <fieldset key={field.id} className="field-group full-width" style={{ border: 'none', padding: 0, margin: 0 }}>
                        <legend className="field-label" style={{ display: 'block', fontSize: '.83rem', fontWeight: 750, color: 'var(--ink)', marginBottom: 4 }}>
                          {field.label}
                          {field.required && <span aria-hidden="true" style={{ color: 'var(--red,#dc2626)', marginLeft: 2 }}>*</span>}
                        </legend>
                        {field.help_text && <small style={{ display: 'block', color: '#6b7280', marginBottom: 6 }}>{field.help_text}</small>}
                        <div className="checkbox-options-row">
                          {(field.options || []).map(o => {
                            const checked = Array.isArray(val) ? val.includes(o.value) : false
                            return (
                              <label
                                key={o.value}
                                className={`checkbox-option ${checked ? 'selected' : ''}`}
                              >
                                <input
                                  type="checkbox"
                                  value={o.value}
                                  checked={checked}
                                  onChange={e => {
                                    const arr = Array.isArray(val) ? [...val] : []
                                    setVal(e.target.checked ? [...arr, o.value] : arr.filter(v => v !== o.value))
                                  }}
                                />
                                <span className="option-label">{o.label}</span>
                              </label>
                            )
                          })}
                        </div>
                      </fieldset>
                    )
                  }

                  return (
                    <label key={field.id} className={field.type === 'textarea' ? 'full-width' : ''}>
                      {field.label}
                      {field.required && <span aria-hidden="true" style={{ color: 'var(--red,#dc2626)', marginLeft: 2 }}>*</span>}
                      {field.help_text && <small style={{ display: 'block', color: '#6b7280', marginBottom: 4 }}>{field.help_text}</small>}
                      {field.type === 'textarea' ? (
                        <textarea
                          value={val}
                          onChange={e => setVal(e.target.value)}
                          required={field.required}
                          placeholder={field.placeholder}
                          rows={4}
                          style={{ width: '100%', resize: 'vertical' }}
                        />
                      ) : field.type === 'dropdown' ? (
                        <select value={val} onChange={e => setVal(e.target.value)} required={field.required}>
                          <option value="">Select…</option>
                          {(field.options || []).map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                        </select>
                      ) : field.type === 'file' ? (
                        <div style={{ width: '100%' }}>
                          {val && typeof val === 'string' && (
                            <div style={{ marginBottom: 6, fontSize: '0.8rem', color: '#4338ca', display: 'flex', alignItems: 'center', gap: 6 }}>
                              <span>✓ Uploaded: {val.split('/').pop()}</span>
                            </div>
                          )}
                          <input
                            type="file"
                            onChange={e => handleFileUpload(field.id, e.target.files[0])}
                            required={field.required && !val}
                          />
                        </div>
                      ) : (
                        <input
                          type={field.type === 'phone' ? 'tel' : field.type}
                          value={val}
                          onChange={e => setVal(e.target.value)}
                          required={field.required}
                          placeholder={field.placeholder}
                          min={field.validation?.min}
                          max={field.validation?.max}
                          minLength={field.validation?.min_length}
                          maxLength={field.validation?.max_length}
                        />
                      )}
                    </label>
                  )
                })}
              </div>
            </section>
          ) : (
            <section className="form-section" aria-labelledby="attendee-title">
              <h2 id="attendee-title">Attendee details</h2>
              <div className="field-grid">
                <label>Full name <input name="name" autoComplete="name" value={form.name} onChange={handleChange} required /></label>
                <label>Email <input name="email" type="email" autoComplete="email" value={form.email} onChange={handleChange} required /></label>
                <label>Phone number
                  <span className="phone-field"><span aria-hidden="true">+91</span><input name="phone" type="tel" autoComplete="tel-national" value={form.phone} onChange={handleChange} required /></span>
                </label>
                <label>Institution <input name="institution" autoComplete="organization" value={form.institution} onChange={handleChange} required /></label>
                <label>Category
                  <select name="category" value={form.category} onChange={handleChange}>
                    {CATEGORIES.map(category => <option key={category.value} value={category.value}>{category.label}</option>)}
                  </select>
                </label>
              </div>
            </section>
          )}

          {/* Legacy photo section for events without dynamic form */}
          {(!customFormSchema || customFormSchema.length === 0) && (
            <section className="form-section" aria-labelledby="photo-title" ref={photoSection}>
              <h2 id="photo-title">Check-in photo</h2>
              <EventPhoto photo={photo} onChange={setPhoto} />
              <p className="privacy-note"><LockKeyhole size={15} /> Your photo is used for face recognition at event check-in.</p>
              <label className="check-row">
                <input type="checkbox" checked={photoConsent} onChange={event => setPhotoConsent(event.target.checked)} required />
                <span>I consent to using my photo for face recognition at this event.</span>
              </label>
            </section>
          )}
          <section className="form-section" aria-labelledby="checkout-title">
            <h2 id="checkout-title">{isPaymentEnabled ? 'Checkout' : 'Complete Registration'}</h2>
            {isPaymentEnabled && (
              <>
                {recoverableOrder && !paidOrderId && (
                  <div className="checkout-notice">
                    <strong>Previous payment found</strong>
                    <p className="mono">{recoverableOrder.order_id}</p>
                    <div className="action-row">
                      <button type="button" className="public-button" onClick={() => handleUseRecoverableOrder(recoverableOrder)}>Use payment</button>
                      <button type="button" className="public-button ghost" onClick={handleDismissRecoverableOrder}>Dismiss</button>
                    </div>
                  </div>
                )}
                {paidOrderId && (
                  <div className="checkout-notice">
                    <strong>Payment confirmed</strong>
                    <p className="mono">{paidOrderId}</p>
                    <button type="button" className="public-button ghost" onClick={() => setPaidOrderId(null)}>Detach payment</button>
                  </div>
                )}
                {!paidOrderId && (
                  <>
                    <details className="disclosure checkout-option">
                      <summary>{appliedCoupon ? 'Coupon applied' : 'Apply Coupon Code'} <ChevronDown size={18} /></summary>
                      {appliedCoupon ? (
                        <div className="inline-field"><span className="mono">{appliedCoupon.code} · Fee waived</span><button type="button" className="public-button" onClick={handleRemoveCoupon}>Remove</button></div>
                      ) : (
                        <div className="inline-field">
                          <input className="mono" aria-label="Coupon code" placeholder="Coupon code" value={couponCode} onChange={event => setCouponCode(event.target.value.toUpperCase())} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); if (!validatingCoupon && !verifyingManualOrder && !loading) handleApplyCoupon() } }} />
                          <button type="button" className="public-button" disabled={validatingCoupon || verifyingManualOrder || loading} onClick={handleApplyCoupon}>{validatingCoupon ? 'Applying…' : 'Apply'}</button>
                        </div>
                      )}
                    </details>

                    <details className="disclosure checkout-option" id="recover-order" ref={recoveryRef}>
                      <summary>Already paid? Link Cashfree Order ID <ChevronDown size={18} /></summary>
                      <p>Find the order ID in your Cashfree payment receipt.</p>
                      <div className="inline-field">
                        <input className="mono" aria-label="Cashfree order ID" placeholder="Order ID" value={manualOrderId} onChange={event => setManualOrderId(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); if (!verifyingManualOrder && !validatingCoupon && !loading) handleVerifyManualOrder() } }} />
                        <button type="button" className="public-button" disabled={verifyingManualOrder || validatingCoupon || loading} onClick={handleVerifyManualOrder}>{verifyingManualOrder ? 'Verifying…' : 'Verify'}</button>
                      </div>
                    </details>
                  </>
                )}
              </>
            )}
            <div className="checkout-total">
              {isPaymentEnabled && (
                <div role="status">
                  <span>Total payable</span>
                  <strong className="mono">{amountDue > 0 ? eventFee(amountDue) : 'Free'}</strong>
                </div>
              )}
              <button type="submit" className="public-button primary" disabled={loading || verifyingManualOrder || validatingCoupon}>
                {submitLabel} <ArrowRight size={17} />
              </button>
            </div>
          </section>
        </form>
      </div>
    </div>
  )
}
