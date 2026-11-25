import { useEffect, useLayoutEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ArrowRight, MapPin } from 'lucide-react'
import client from '../api/client'
import { eventDate } from '../utils/eventDisplay'

import FeatureCarousel from '../components/public/FeatureCarousel'
import { oaicLogos } from '../content/oaicLogos'

export default function Home() {
  const [events, setEvents] = useState(null)
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [inView, setInView] = useState(false)
  const { hash, key, state } = useLocation()
  const smoothEvents = hash === '#active-events' && state?.smoothEvents === true

  useLayoutEffect(() => {
    if (!hash) {
      window.scrollTo(0, 0)
      return
    }
    const target = document.getElementById(hash === '#events' ? 'active-events' : hash.slice(1))
    const behavior = smoothEvents && !window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'smooth' : 'auto'
    target?.scrollIntoView({ behavior, block: 'start' })
    if (smoothEvents) target?.focus({ preventScroll: true })
  }, [hash, key, smoothEvents])

  useEffect(() => {
    const node = document.getElementById('institution-strip')
    const observer = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting))
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    client.get('/events/', { signal: controller.signal })
      .then(({ data }) => setEvents(data))
      .catch(() => { if (!controller.signal.aborted) setFailed(true) })
    return () => controller.abort()
  }, [attempt])

  return (
    <div className="public-width home">
      <div className="home-first-view">
        <section className="home-hero" aria-labelledby="hero-title">
          <div className="hero-copy">
            <h1 id="hero-title">Powering<br />Next-Gen Events<span>.</span></h1>
            <p>From the first registration to the last session. Run events with online ticketing, face check-in, and live attendance.</p>
            <Link className="public-button primary" to="/#active-events" state={{ smoothEvents: true }}>
              Explore Events <ArrowRight size={16} />
            </Link>
            <ul className="hero-entry-details" aria-label="Check-in options">
              <li>Fast QR Check-In</li>
              <li>Instant QR Verification</li>
              <li>Zero-Paper Entry</li>
            </ul>
          </div>
          <FeatureCarousel />
        </section>

        <section id="institution-strip" className="institutions" aria-labelledby="institutions-title">
          <h2 id="institutions-title">Trusted by Leading Institutions</h2>
          <div className="marquee-window">
            <div className="marquee-track" data-paused={!inView}>
              {[false, true].map(duplicate => (
                <ul key={String(duplicate)} aria-hidden={duplicate || undefined}>
                  {oaicLogos.map(({ src, alt, width, height }) => <li key={src}><img src={src} width={width} height={height} alt={duplicate ? '' : alt} /></li>)}
                </ul>
              ))}
            </div>
          </div>
        </section>
      </div>

      <section id="active-events" className="event-directory" aria-labelledby="events-title" tabIndex={-1}>
        <div className="directory-heading">
          <h2 id="events-title">Active Events</h2>
          <p>Find your next conference, summit, or workshop.</p>
        </div>
        {failed ? (
          <div className="directory-state" role="status">Events couldn’t load. <button className="public-button" onClick={() => { setFailed(false); setAttempt(attempt + 1) }}>Try again</button></div>
        ) : events === null ? <p className="directory-state" role="status">Loading events…</p>
          : events.length === 0 ? <p className="directory-state">No active events right now.</p>
            : <div className="event-list">{events.map(event => <EventRow key={event.id} event={event} />)}</div>}
      </section>

      <section className="host-strip" id="host">
        <div><h2>Host Your Event with GeekAI</h2><p>Registration, check-in, and attendance for your next event.</p></div>
        <a className="public-button" href="mailto:info@oaic.in">Get in Touch <ArrowRight size={16} /></a>
      </section>
    </div>
  )
}

function EventRow({ event }) {
  return (
    <article className="event-row">
      <div className="event-stamp mono">{eventDate(event.event_date, true)}</div>
      <div className="event-info">
        <h3>{event.name}</h3>
        {event.tagline && <p>{event.tagline}</p>}
        {event.venue && <p className="event-meta"><MapPin size={15} aria-hidden="true" /> {event.venue}</p>}
      </div>
      <div className="event-action">
        <Link className="public-button primary" to={`/events/${event.slug}/register`} aria-label={`Register for ${event.name}`}>Register <ArrowRight size={16} /></Link>
      </div>
    </article>
  )
}
