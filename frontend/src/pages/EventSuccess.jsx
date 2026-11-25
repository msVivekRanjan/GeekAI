import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { ArrowLeft, Calendar, Check, Download, MapPin, ScanLine } from 'lucide-react'
import { eventDate } from '../utils/eventDisplay'
import { resolveMediaUrl } from '../utils/helpers'

const escapeCalendar = value => String(value || '').replaceAll('\\', '\\\\').replace(/\r?\n/g, '\\n').replaceAll(';', '\\;').replaceAll(',', '\\,')

function downloadCalendar(event) {
  const date = new Date(event.event_date)
  const localDay = new Intl.DateTimeFormat('en', {
    timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(date)
  const day = ['year', 'month', 'day'].map(part => localDay.find(item => item.type === part).value).join('')
  const stamp = new Date().toISOString().replace(/[-:]|\.\d{3}/g, '')
  const start = /^\d{4}-\d{2}-\d{2}$/.test(event.event_date)
    ? `DTSTART;VALUE=DATE:${day}`
    : `DTSTART:${date.toISOString().replace(/[-:]|\.\d{3}/g, '')}`
  const lines = [
    'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//GeekAI//Event Pass//EN', 'BEGIN:VEVENT',
    `UID:${escapeCalendar(event.slug)}-${day}@geekai.in`, `DTSTAMP:${stamp}`,
    start, `SUMMARY:${escapeCalendar(event.name)}`,
    `LOCATION:${escapeCalendar(event.venue)}`, 'END:VEVENT', 'END:VCALENDAR', '',
  ]
  const url = URL.createObjectURL(new Blob([lines.join('\r\n')], { type: 'text/calendar;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `${event.slug}.ics`
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export default function EventSuccess() {
  const { state } = useLocation()
  const { eventSlug } = useParams()
  const heading = useRef(null)
  const [qrUnavailable, setQrUnavailable] = useState(false)
  const [photoUnavailable, setPhotoUnavailable] = useState(false)

  useEffect(() => {
    window.scrollTo(0, 0)
    heading.current?.focus({ preventScroll: true })
  }, [])

  if (!state?.attendee || state.event?.slug !== eventSlug) return (
    <div className="public-width route-state">
      <h1>Find your event pass</h1>
      <p>Open the registration email for your QR code, or contact the event team for help.</p>
      <Link className="public-button" to="/#active-events"><ArrowLeft size={16} /> Back to Events</Link>
    </div>
  )

  const { attendee, event } = state
  const canAddToCalendar = event.event_date && !Number.isNaN(new Date(event.event_date).getTime())

  return (
    <div className="public-width confirmation">
      <Link className="back-link" to="/#active-events"><ArrowLeft size={16} /> Back to Events</Link>
      <h1 ref={heading} tabIndex={-1}>Registration complete</h1>
      <p className="confirmation-intro">Keep this pass handy for check-in and session entry.</p>

      <article className="pass" aria-label="Digital event pass">
        <header className="pass-header">
          <div className="pass-label"><span>Digital event pass</span><span className="confirmed"><Check size={14} /> Confirmed</span></div>
          <h2>{event.name}</h2>
          <div className="summary-meta">
            <span><Calendar size={16} /> {eventDate(event.event_date)}</span>
            {event.venue && <span><MapPin size={16} /> {event.venue}</span>}
          </div>
        </header>
        <div className="pass-perforation" aria-hidden="true" />
        <div className="pass-body">
          <div className="pass-media">
            <div>
              {attendee.qr && !qrUnavailable ?
                <img className="pass-qr" src={resolveMediaUrl(attendee.qr)} alt="QR code for session entry" onError={() => setQrUnavailable(true)} />
                : <p className="pass-qr-fallback">Use the QR code in your registration email.</p>}
              <span>Session entry</span>
            </div>
            {attendee.photo && !photoUnavailable && (
              <div>
                <img className="pass-photo" src={resolveMediaUrl(attendee.photo)} alt="Attendee check-in photo" onError={() => setPhotoUnavailable(true)} />
                <span><ScanLine size={15} /> AI Face Check-In Ready</span>
              </div>
            )}
          </div>
          <dl className="pass-details">
            <div><dt>Attendee</dt><dd>{attendee.name}</dd></div>
            <div><dt>Category</dt><dd>{attendee.category?.toLowerCase()}</dd></div>
            <div><dt>Institution</dt><dd>{attendee.institution || '—'}</dd></div>
            <div><dt>{attendee.orderId ? 'Order ID' : 'Registration ID'}</dt><dd className="mono">{attendee.orderId || attendee.id}</dd></div>
          </dl>
        </div>
      </article>

      <div className="action-row pass-actions">
        <button className="public-button primary" onClick={() => window.print()}><Download size={16} /> Download Event Pass</button>
        {canAddToCalendar && <button className="public-button" onClick={() => downloadCalendar(event)}><Calendar size={16} /> Add to Calendar (.ics)</button>}
      </div>
      <p className="pass-email">Check <strong>{attendee.email}</strong> for a copy of your QR pass.</p>
    </div>
  )
}
