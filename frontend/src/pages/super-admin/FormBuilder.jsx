import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft, Plus, Trash2, ChevronDown, Save, Eye,
  Type, Mail, Phone, Hash, List, Circle, CheckSquare, Calendar,
  AlignLeft, Upload, AlertCircle, Camera, ArrowUp, ArrowDown, GripVertical, Image,
} from 'lucide-react'
import client from '../../api/client'
import toast from 'react-hot-toast'

const FIELD_TYPES = [
  { type: 'text', label: 'Text', icon: Type },
  { type: 'email', label: 'Email', icon: Mail },
  { type: 'phone', label: 'Phone', icon: Phone },
  { type: 'photo', label: 'Photo', icon: Camera },
  { type: 'number', label: 'Number', icon: Hash },
  { type: 'textarea', label: 'Long Text', icon: AlignLeft },
  { type: 'dropdown', label: 'Dropdown', icon: List },
  { type: 'radio', label: 'Radio', icon: Circle },
  { type: 'checkbox', label: 'Checkbox', icon: CheckSquare },
  { type: 'date', label: 'Date', icon: Calendar },
  { type: 'file', label: 'File Upload', icon: Upload },
  { type: 'image', label: 'Image', icon: Image },
]

const ICON_MAP = {
  text: Type,
  email: Mail,
  phone: Phone,
  photo: Camera,
  number: Hash,
  textarea: AlignLeft,
  dropdown: List,
  radio: Circle,
  checkbox: CheckSquare,
  date: Calendar,
  file: Upload,
  image: Image,
}

function newField(type, order, defaultLabel = null, defaultMapping = null) {
  let mapping = defaultMapping
  if (!mapping) {
    if (type === 'photo') mapping = 'photo'
    else if (type === 'email') mapping = 'email'
    else if (type === 'phone') mapping = 'phone'
    else mapping = 'custom'
  }

  let label = defaultLabel
  if (!label) {
    if (type === 'photo') label = 'Check-in Photo'
    else if (type === 'email') label = 'Email Address'
    else if (type === 'phone') label = 'Phone Number'
    else if (type === 'image') label = 'Event Illustration'
    else label = `${FIELD_TYPES.find(f => f.type === type)?.label || 'Field'} ${order + 1}`
  }

  return {
    id: `field_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    type,
    label,
    placeholder: '',
    image_url: '',
    required: ['photo', 'email'].includes(type) ? true : false,
    mapping,
    options: ['dropdown', 'radio', 'checkbox'].includes(type)
      ? [{ label: 'Option 1', value: 'option_1' }]
      : null,
    validation: null,
    order,
    help_text: type === 'photo' ? 'Upload or capture a front-facing photo for AI face recognition check-in' : '',
  }
}

function FieldEditor({ field, onChange, onDelete, onMoveUp, onMoveDown, isFirst, isLast, index, expanded, onToggle, dragging, shift, eventId, onImageUpload }) {
  const Icon = ICON_MAP[field.type] || Type
  const [uploadingImage, setUploadingImage] = useState(false)

  const updateField = (key, value) => onChange({ ...field, [key]: value })
  const updateOptions = (options) => onChange({ ...field, options })

  const handleFieldImageUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const formData = new FormData()
    formData.append('image', file)
    setUploadingImage(true)
    try {
      const url = eventId ? `/super-admin/events/${eventId}/upload-image` : '/super-admin/upload-image'
      const res = await client.post(url, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      onImageUpload(field.id, res.data.url)
      toast.success('Image uploaded successfully!')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to upload image')
    } finally {
      setUploadingImage(false)
    }
  }

  const addOption = () => {
    const opts = field.options || []
    const idx = opts.length
    updateOptions([...opts, { label: `Option ${idx + 1}`, value: `option_${idx + 1}` }])
  }

  const updateOption = (i, key, val) => {
    const opts = [...(field.options || [])]
    opts[i] = { ...opts[i], [key]: val }
    updateOptions(opts)
  }

  const removeOption = (i) => {
    updateOptions(field.options.filter((_, idx) => idx !== i))
  }

  return (
    <article className="sa-panel sa-field" data-expanded={expanded} data-field-index={index}
      data-dragging={dragging || undefined} style={shift ? { '--sa-row-shift': `${shift}px` } : undefined}>
      <div className="sa-field-summary" onClick={onToggle}>
        <span className="sa-drag-handle" data-field-handle title="Drag to rearrange" onClick={event => event.stopPropagation()}>
          <GripVertical size={15} aria-hidden="true" />
          <span className="sa-order">{String(index + 1).padStart(2, '0')}</span>
        </span>
        <span className="sa-field-type"><Icon size={15} aria-hidden="true" /><code>{field.type}</code></span>
        <input className="sa-inline-label" aria-label={`Field ${index + 1} label`}
          value={field.label} placeholder="Field label" onClick={event => event.stopPropagation()}
          onChange={event => updateField('label', event.target.value)} />
        {field.type !== 'image' && field.mapping && field.mapping !== 'custom' && (
          <span className="sa-field-mapping"><span>Maps to </span><code>{field.mapping}</code></span>
        )}
        {field.type !== 'image' && (
          <label className="sa-required" onClick={event => event.stopPropagation()}>
            <input type="checkbox" checked={field.required} onChange={event => updateField('required', event.target.checked)} />
            <span>Required</span>
          </label>
        )}
        <div className="sa-field-actions" onClick={event => event.stopPropagation()}>
          <button type="button" onClick={onMoveUp} disabled={isFirst} className="sa-icon" aria-label="Move field up" title="Move field up"><ArrowUp size={15} /></button>
          <button type="button" onClick={onMoveDown} disabled={isLast} className="sa-icon" aria-label="Move field down" title="Move field down"><ArrowDown size={15} /></button>
          <button type="button" onClick={onToggle} className="sa-icon sa-expand" aria-label={expanded ? 'Collapse field settings' : 'Expand field settings'} aria-expanded={expanded} aria-controls={`settings-${field.id}`} title="Field settings"><ChevronDown size={17} /></button>
          <button type="button" onClick={onDelete} className="sa-icon sa-danger" aria-label="Delete field" title="Delete field"><Trash2 size={15} /></button>
        </div>
      </div>
      <div className="sa-field-disclosure" id={`settings-${field.id}`} inert={!expanded} aria-hidden={!expanded}>
        <div className="sa-disclosure-inner">
          <div className="sa-field-config">
            {field.type === 'image' ? (
              <div className="sa-config-wide space-y-4">
                <div className="sa-info items-start">
                  <Image className="h-4 w-4 text-stone-600 shrink-0 mt-0.5" />
                  <div>
                    <strong className="font-semibold text-stone-900">Form Image / Illustration Field</strong>
                    <p className="mt-0.5 text-stone-700">
                      Display an image banner or illustration at this exact position in the registration form. Rendered at original aspect ratio and natural dimensions.
                    </p>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">Image Heading / Alt Text</label>
                  <input
                    value={field.label}
                    onChange={e => updateField('label', e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-gray-900 focus:border-transparent outline-none"
                    placeholder="e.g. Event Venue Map or Sponsor Illustration"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">Image Source (URL or File Upload) *</label>
                  <div className="flex items-center gap-2">
                    <input
                      value={field.image_url || ''}
                      onChange={e => updateField('image_url', e.target.value)}
                      className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-gray-900 focus:border-transparent outline-none"
                      placeholder="https://… or click upload"
                    />
                    <label className="sa-button sa-image-upload">
                      <Upload className="h-3.5 w-3.5" />
                      {uploadingImage ? 'Uploading…' : 'Upload Image'}
                      <input
                        type="file"
                        accept="image/*"
                        onChange={handleFieldImageUpload}
                        disabled={uploadingImage}
                        className="sr-only"
                      />
                    </label>
                  </div>
                </div>

                {field.image_url && (
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 mb-1">Image Preview</label>
                    <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg flex flex-col items-center justify-center">
                      <img
                        src={field.image_url}
                        alt={field.label || 'Image preview'}
                        style={{ maxWidth: '100%', height: 'auto', maxHeight: '260px', objectFit: 'contain', borderRadius: '6px' }}
                      />
                      <button
                        type="button"
                        onClick={() => updateField('image_url', '')}
                        className="mt-2 text-xs text-red-600 hover:text-red-700 font-medium inline-flex items-center gap-1 cursor-pointer"
                      >
                        <Trash2 className="h-3 w-3" /> Remove image
                      </button>
                    </div>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">Caption / Help Text</label>
                  <input
                    value={field.help_text || ''}
                    onChange={e => updateField('help_text', e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-gray-900 focus:border-transparent outline-none"
                    placeholder="Optional caption displayed below image"
                  />
                </div>
              </div>
            ) : (
              <>
                <div>
                  <label htmlFor={`mapping-${field.id}`}>System Attribute Mapping</label>
                  <select
                    id={`mapping-${field.id}`}
                    value={field.mapping || 'custom'}
                    onChange={e => updateField('mapping', e.target.value)}
                  >
                    <option value="custom">Custom Field (Stored in responses)</option>
                    <option value="name">Participant Full Name (Core DB & QR)</option>
                    <option value="email">Participant Email (Core DB & QR Email)</option>
                    <option value="phone">Participant Phone (Cashfree & SMS)</option>
                    <option value="institution">Institution / Organization</option>
                    <option value="category">Participant Category</option>
                    <option value="photo">Check-in Photo (Face Recognition)</option>
                  </select>
                </div>

                {field.type !== 'photo' && (
                  <div>
                    <label htmlFor={`placeholder-${field.id}`}>Placeholder</label>
                    <input
                      id={`placeholder-${field.id}`}
                      value={field.placeholder || ''}
                      onChange={e => updateField('placeholder', e.target.value)}
                      placeholder="Placeholder text"
                    />
                  </div>
                )}

                <div>
                  <label htmlFor={`help-${field.id}`}>Help Text</label>
                  <input
                    id={`help-${field.id}`}
                    value={field.help_text || ''}
                    onChange={e => updateField('help_text', e.target.value)}
                    placeholder="Optional helper text shown below the field"
                  />
                </div>

                {field.type === 'photo' && (
                  <p className="sa-info sa-config-wide">
                    <Camera size={15} aria-hidden="true" />Attendees can use a camera or upload a photo for face check-in.
                  </p>
                )}

                {/* Options for dropdown/radio/checkbox */}
                {['dropdown', 'radio', 'checkbox'].includes(field.type) && (
                  <div className="sa-config-wide">
                    <p className="sa-config-subtitle">Options</p>
                    <div className="space-y-2">
                      {(field.options || []).map((opt, i) => (
                        <div key={i} className="sa-option">
                          <input
                            value={opt.label}
                            onChange={e => updateOption(i, 'label', e.target.value)}
                            aria-label={`Option ${i + 1} label`} placeholder={`Option ${i + 1} label`}
                          />
                          <input
                            value={opt.value}
                            onChange={e => updateOption(i, 'value', e.target.value)}
                            aria-label={`Option ${i + 1} value`} placeholder="value"
                          />
                          <button
                            onClick={() => removeOption(i)}
                            className="sa-icon sa-danger" aria-label={`Remove option ${i + 1}`}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ))}
                      <button
                        type="button"
                        onClick={addOption}
                        className="sa-text-action"
                      >
                        <Plus className="h-3.5 w-3.5" /> Add Option
                      </button>
                    </div>
                  </div>
                )}

                {/* Validation for text/number */}
                {['text', 'textarea', 'number'].includes(field.type) && (
                  <div className="sa-config-wide sa-validation">
                    <p className="sa-config-subtitle">Validation (optional)</p>
                    <div className="grid grid-cols-2 gap-3">
                      {field.type === 'number' ? (
                        <>
                          <div>
                            <label htmlFor={`min-${field.id}`}>Min value</label>
                            <input
                              id={`min-${field.id}`}
                              type="number"
                              value={field.validation?.min ?? ''}
                              onChange={e => updateField('validation', { ...field.validation, min: e.target.value ? Number(e.target.value) : null })}
                            />
                          </div>
                          <div>
                            <label htmlFor={`max-${field.id}`}>Max value</label>
                            <input
                              id={`max-${field.id}`}
                              type="number"
                              value={field.validation?.max ?? ''}
                              onChange={e => updateField('validation', { ...field.validation, max: e.target.value ? Number(e.target.value) : null })}
                            />
                          </div>
                        </>
                      ) : (
                        <>
                          <div>
                            <label htmlFor={`min-length-${field.id}`}>Min length</label>
                            <input
                              id={`min-length-${field.id}`}
                              type="number" min="0"
                              value={field.validation?.min_length ?? ''}
                              onChange={e => updateField('validation', { ...field.validation, min_length: e.target.value ? Number(e.target.value) : null })}
                            />
                          </div>
                          <div>
                            <label htmlFor={`max-length-${field.id}`}>Max length</label>
                            <input
                              id={`max-length-${field.id}`}
                              type="number" min="0"
                              value={field.validation?.max_length ?? ''}
                              onChange={e => updateField('validation', { ...field.validation, max_length: e.target.value ? Number(e.target.value) : null })}
                            />
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </article>
  )
}

function FormPreview({ fields }) {
  if (!fields.length) return (
    <div className="sa-state">

      <p className="text-sm">No fields configured yet. Add fields from the left panel.</p>
    </div>
  )

  return (
    <div className="space-y-5">
      {fields.map(field => {
        if (field.type === 'image') {
          return (
            <div key={field.id} className="py-2">
              {field.label && field.label !== 'Image' && (
                <h4 className="text-sm font-semibold text-gray-800 mb-1.5">{field.label}</h4>
              )}
              {field.image_url ? (
                <div className="rounded-lg overflow-hidden border border-gray-200 bg-gray-50 flex justify-center">
                  <img
                    src={field.image_url}
                    alt={field.label || 'Form image'}
                    style={{ maxWidth: '100%', height: 'auto', display: 'block', objectFit: 'contain' }}
                  />
                </div>
              ) : (
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center bg-gray-50 text-gray-400">
                  <Image className="h-8 w-8 mx-auto mb-1 text-gray-400" />
                  <p className="text-xs">Image field (upload an image in the editor)</p>
                </div>
              )}
              {field.help_text && (
                <p className="text-xs text-gray-500 mt-1">{field.help_text}</p>
              )}
            </div>
          )
        }

        return (
          <div key={field.id}>
            <label className="block text-sm font-semibold text-stone-700 mb-1">
              {field.label}
              {field.required && <span className="text-red-500 ml-0.5">*</span>}
            </label>
            {field.help_text && <p className="text-xs text-stone-500 mb-1">{field.help_text}</p>}
            {field.type === 'photo' ? (
              <div className="border-2 border-dashed border-stone-300 bg-stone-50 rounded-xl p-5 text-center">
                <div className="w-12 h-12 rounded-full bg-stone-100 flex items-center justify-center mx-auto mb-2 text-stone-600">
                  <Camera className="h-6 w-6" />
                </div>
                <p className="text-sm font-semibold text-stone-800">Check-in Photo Capture & Upload</p>
                <p className="text-xs text-stone-500 mt-1 max-w-xs mx-auto">
                  Live webcam capture and file upload for AI face recognition check-in.
                </p>
              </div>
            ) : field.type === 'textarea' ? (
              <textarea rows={3} disabled placeholder={field.placeholder}
                className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm bg-stone-50 resize-none opacity-70" />
            ) : field.type === 'dropdown' ? (
              <select disabled className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm bg-stone-50 opacity-70">
                <option value="">Select…</option>
                {(field.options || []).map(o => <option key={o.value}>{o.label}</option>)}
              </select>
            ) : ['radio', 'checkbox'].includes(field.type) ? (
              <div className="flex flex-wrap gap-2 pt-1">
                {(field.options || []).map(o => (
                  <div key={o.value} className="inline-flex items-center gap-2 px-3 py-2 bg-stone-50 border border-stone-200 rounded-lg text-xs font-medium text-stone-700 opacity-80">
                    <input type={field.type === 'radio' ? 'radio' : 'checkbox'} disabled className="h-3.5 w-3.5" />
                    <span>{o.label}</span>
                  </div>
                ))}
              </div>
            ) : field.type === 'file' ? (
              <div className="border-2 border-dashed border-stone-300 rounded-lg px-4 py-6 text-center opacity-70">
                <Upload className="h-5 w-5 text-stone-400 mx-auto mb-1" />
                <p className="text-xs text-stone-500">Click to upload file</p>
              </div>
            ) : (
              <input type={field.type === 'phone' ? 'tel' : field.type}
                disabled placeholder={field.placeholder}
                className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm bg-stone-50 opacity-70" />
            )}
          </div>
        )
      })}
    </div>
  )
}

export default function FormBuilder() {
  const { id } = useParams()
  const [event, setEvent] = useState(null)
  const [fields, setFields] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [expandedField, setExpandedField] = useState(null)
  const [activeTab, setActiveTab] = useState('builder') // 'builder' | 'preview'
  const [dragPreview, setDragPreview] = useState(null)
  const dragRef = useRef(null)

  useEffect(() => () => cancelAnimationFrame(dragRef.current?.frame), [])

  useEffect(() => {
    Promise.all([
      client.get(`/super-admin/events/${id}`),
      client.get(`/super-admin/events/${id}/form-schema`),
    ]).then(([evtRes, schemaRes]) => {
      setEvent(evtRes.data)
      const schema = schemaRes.data?.schema
      if (schema?.fields?.length) {
        setFields(schema.fields.sort((a, b) => a.order - b.order))
      }
    }).catch(() => toast.error('Failed to load event or form schema'))
      .finally(() => setLoading(false))
  }, [id])

  const addField = (type) => {
    setFields(prev => [...prev, newField(type, prev.length)])
  }

  const addCustomField = (type, defaultLabel, defaultMapping, required = false) => {
    const f = newField(type, fields.length, defaultLabel, defaultMapping)
    f.required = required
    setFields(prev => [...prev, f])
  }

  const updateField = (idx, updated) => {
    setFields(prev => {
      const next = [...prev]
      next[idx] = updated
      return next
    })
  }

  const updateFieldImage = (fieldId, imageUrl) => {
    setFields(prev => prev.map(field => field.id === fieldId ? { ...field, image_url: imageUrl } : field))
  }

  const deleteField = (idx) => {
    setFields(prev => prev.filter((_, i) => i !== idx).map((f, i) => ({ ...f, order: i })))
  }

  const moveField = (idx, direction) => {
    setFields(prev => {
      const next = [...prev]
      const targetIdx = idx + direction
      if (idx === targetIdx || targetIdx < 0 || targetIdx >= next.length) return prev
      const [field] = next.splice(idx, 1)
      next.splice(targetIdx, 0, field)
      return next.map((f, i) => ({ ...f, order: i }))
    })
  }

  const updateDropTarget = (drag) => {
    const bounds = drag.list.getBoundingClientRect()
    const listTop = bounds.top + drag.list.clientTop - drag.list.scrollTop
    const pointerY = drag.y - listTop
    // Layout offsets stay stable while neighboring rows translate.
    drag.row.style.setProperty('--sa-grab-offset', `${pointerY - drag.grabOffset - drag.row.offsetTop}px`)
    const inside = drag.x >= bounds.left && drag.x <= bounds.right
      && drag.y >= bounds.top && drag.y <= bounds.bottom
    const destination = inside ? drag.rows.reduce((index, row) => (
      row !== drag.row && pointerY >= row.offsetTop + row.offsetHeight / 2 ? index + 1 : index
    ), 0) : drag.source
    drag.destination = destination
    setDragPreview(current => current?.destination === destination ? current : {
      source: drag.source, destination, distance: drag.distance,
    })
  }

  const startDrag = (event) => {
    const handle = event.target.closest('[data-field-handle]')
    if (!handle || !event.isPrimary || event.button !== 0 || fields.length < 2) return
    const list = event.currentTarget
    const scrollable = getComputedStyle(list).overflowY === 'auto'
    const row = handle.closest('[data-field-index]')
    const rows = Array.from(list.querySelectorAll('[data-field-index]'))
    const source = Number(row.dataset.fieldIndex)
    const neighbor = rows[source + 1]
    const previous = rows[source - 1]
    const gap = neighbor ? neighbor.offsetTop - row.offsetTop - row.offsetHeight
      : row.offsetTop - previous.offsetTop - previous.offsetHeight
    event.preventDefault()
    list.focus({ preventScroll: true })
    list.setPointerCapture(event.pointerId)
    dragRef.current = {
      pointer: event.pointerId, list, scrollable, row, rows, source,
      grabOffset: event.clientY - row.getBoundingClientRect().top,
      distance: row.offsetHeight + gap,
      startY: event.clientY, x: event.clientX, y: event.clientY, destination: source,
    }
  }

  const trackDrag = (event) => {
    const drag = dragRef.current
    if (!drag || drag.pointer !== event.pointerId) return
    drag.x = event.clientX
    drag.y = event.clientY
    if (!drag.frame && Math.abs(drag.y - drag.startY) < 5) return
    updateDropTarget(drag)
    if (drag.frame) return

    const scrollAtEdge = () => {
      const bounds = drag.list.getBoundingClientRect()
      const top = drag.scrollable ? bounds.top : 0
      const bottom = drag.scrollable ? bounds.bottom : window.innerHeight
      const distance = drag.y < top + 44 ? drag.y - top - 44
        : drag.y > bottom - 44 ? drag.y - bottom + 44 : 0
      if (distance && drag.x >= bounds.left && drag.x <= bounds.right) {
        const scroller = drag.scrollable ? drag.list : document.scrollingElement
        const previous = scroller.scrollTop
        scroller.scrollTop += Math.max(-14, Math.min(14, distance / 3))
        if (scroller.scrollTop !== previous) updateDropTarget(drag)
      }
      drag.frame = requestAnimationFrame(scrollAtEdge)
    }
    drag.frame = requestAnimationFrame(scrollAtEdge)
  }

  const finishDrag = (event) => {
    const drag = dragRef.current
    if (!drag || (event.pointerId != null && drag.pointer !== event.pointerId)) return
    dragRef.current = null
    cancelAnimationFrame(drag.frame)
    drag.row.style.removeProperty('--sa-grab-offset')
    setDragPreview(null)
    if (drag.list.hasPointerCapture(drag.pointer)) drag.list.releasePointerCapture(drag.pointer)
    if (event.type === 'pointerup') moveField(drag.source, drag.destination - drag.source)
  }

  const getRowShift = (index) => {
    if (!dragPreview) return 0
    const { source, destination, distance } = dragPreview
    if (index > source && index <= destination) return -distance
    if (index < source && index >= destination) return distance
    return 0
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const schema = {
        fields: fields.map((f, i) => ({ ...f, order: i })),
        version: 1,
      }
      await client.put(`/super-admin/events/${id}/form-schema`, schema)
      toast.success('Form schema saved!')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save form schema')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="sa-state" role="status">Loading form builder…</div>

  return (
    <div className="sa-page sa-builder">
      <div className="sa-page-header sa-sticky">
        <div className="sa-page-heading">
          <Link to={`/super-admin/events/${id}/edit`} className="sa-icon sa-back" aria-label="Back to event editor"><ArrowLeft size={19} /></Link>
          <div><h1>Form Builder</h1>{event?.name && <p>{event.name}</p>}</div>
        </div>
        <div className="sa-header-actions">
          <button type="button" onClick={() => setActiveTab(t => t === 'builder' ? 'preview' : 'builder')} className="sa-button">
            <Eye size={16} />{activeTab === 'builder' ? 'Preview Form' : 'Back to Builder'}
          </button>
          <button type="button" onClick={handleSave} disabled={saving} className="sa-button sa-primary">
            <Save size={16} />{saving ? 'Saving…' : 'Save Schema'}
          </button>
        </div>
      </div>
      <p className="sa-info"><AlertCircle size={15} aria-hidden="true" />
        <span>All fields are added manually. Use the Photo field for face check-in.</span>
      </p>
      <div className="sa-quick" aria-label="Quick Add">
        <strong>Quick Add</strong>
        {[
          ['text', 'Full Name', 'name', true, 'Full Name'],
          ['email', 'Email Address', 'email', true, 'Email Address'],
          ['phone', 'Phone Number', 'phone', false, 'Phone Number'],
          ['text', 'Institution / Organization', 'institution', false, 'Institution'],
          ['photo', 'Check-in Photo', 'photo', true, 'Photo (Face Check-in)'],
        ].map(([type, label, mapping, required, caption]) => (
          <button key={mapping} type="button" className="sa-button"
            onClick={() => addCustomField(type, label, mapping, required)}>
            <Plus size={14} aria-hidden="true" />{caption}
          </button>
        ))}
      </div>

      {activeTab === 'preview' ? (
        <section className="sa-panel sa-preview">
          <h2>Form Preview</h2>
          <FormPreview fields={fields} />
        </section>
      ) : (
        <div className="sa-builder-grid">
          <section className="sa-panel sa-palette" aria-labelledby="sa-field-types">
            <h2 id="sa-field-types">Field Types</h2>
            {FIELD_TYPES.map(({ type, label, icon: Icon }) => (
              <button key={type} type="button" onClick={() => addField(type)}>
                <Icon size={16} aria-hidden="true" />{label}<Plus size={14} aria-hidden="true" />
              </button>
            ))}
          </section>
          <section className="sa-canvas" aria-labelledby="sa-form-fields">
            <div className="sa-canvas-header">
              <h2 id="sa-form-fields">Form Fields</h2>
              <span role="status">{fields.length} {fields.length === 1 ? 'field' : 'fields'}</span>
            </div>
            <div className="sa-field-list" tabIndex={0} role="region" aria-label="Configured fields"
              data-reordering={!!dragPreview || undefined}
              onPointerDown={startDrag} onPointerMove={trackDrag} onPointerUp={finishDrag}
              onPointerCancel={finishDrag} onLostPointerCapture={finishDrag}
              onKeyDown={event => { if (event.key === 'Escape') finishDrag(event) }}>
              {fields.length === 0 ? (
                <div className="sa-empty">
                  <List size={25} aria-hidden="true" />
                  <h3>No fields yet</h3>
                  <p>Choose a field type or use Quick Add to start the registration form.</p>
                </div>
              ) : fields.map((field, idx) => (
                <FieldEditor
                  key={field.id}
                  field={field}
                  eventId={id}
                  onImageUpload={updateFieldImage}
                  index={idx}
                  dragging={dragPreview?.source === idx}
                  shift={getRowShift(idx)}
                  onChange={(updated) => updateField(idx, updated)}
                  onDelete={() => deleteField(idx)}
                  onMoveUp={() => moveField(idx, -1)}
                  onMoveDown={() => moveField(idx, 1)}
                  isFirst={idx === 0}
                  isLast={idx === fields.length - 1}
                  expanded={expandedField === field.id}
                  onToggle={() => setExpandedField(current => current === field.id ? null : field.id)}
                />
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
