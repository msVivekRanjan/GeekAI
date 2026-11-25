import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useInView, useReducedMotion } from 'motion/react'
import { ChartNoAxesColumn, Check, QrCode, ScanLine, Ticket, UserRound } from 'lucide-react'

const features = [
  [Ticket, 'Smart Registration', 'Instant ticketing, UPI checkout, and automated pass delivery.'],
  [ScanLine, 'Instant QR Check-In', 'Fast QR badge verification for queue-free venue entry.'],
  [QrCode, 'Live Session Tracking', 'Track workshop and keynote room occupancy across multi-track events.'],
  [ChartNoAxesColumn, 'Real-Time Event Analytics', 'Monitor check-in velocity, demographics, and export CSV reports.'],
]

const slide = {
  enter: direction => ({ x: direction * 100 + '%' }),
  active: { x: '0%' },
  exit: direction => ({ x: -direction * 100 + '%' }),
}

export default function FeatureCarousel() {
  const carousel = useRef(null)
  const inView = useInView(carousel, { amount: 0.5 })
  const reduceMotion = useReducedMotion()
  const [{ index, direction }, setSlide] = useState({ index: 0, direction: 1 })
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [pageVisible, setPageVisible] = useState(() => !document.hidden)
  const autoplay = !reduceMotion && !hovered && !focused && !dragging && pageVisible && inView

  useEffect(() => {
    const update = () => setPageVisible(!document.hidden)
    document.addEventListener('visibilitychange', update)
    return () => document.removeEventListener('visibilitychange', update)
  }, [])

  useEffect(() => {
    if (!autoplay) return
    const timer = window.setTimeout(() => {
      setSlide({ index: (index + 1) % features.length, direction: 1 })
    }, 3000)
    return () => window.clearTimeout(timer)
  }, [autoplay, index])

  const step = amount => setSlide(current => ({
    index: (current.index + amount + features.length) % features.length,
    direction: amount,
  }))
  const [Icon, title, description] = features[index]
  const card = (
    <article className="feature-slide" aria-roledescription="slide" aria-label={`${index + 1} of ${features.length}`}>
      <div className="feature-slide-top">
        <span className="feature-index mono" aria-hidden="true">0{index + 1} / 0{features.length}</span>
        <Icon size={30} strokeWidth={1.5} aria-hidden="true" />
      </div>
      <div className="feature-slide-copy">
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      <FeaturePreview index={index} />
    </article>
  )
  return (
    <section className="feature-carousel" ref={carousel} aria-label="Event platform features" aria-roledescription="carousel"
      onPointerEnter={event => { if (event.pointerType === 'mouse') setHovered(true) }}
      onPointerLeave={() => setHovered(false)}
      onFocus={() => setFocused(true)}
      onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setFocused(false) }}
      onKeyDown={event => {
        if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
        event.preventDefault()
        step(event.key === 'ArrowRight' ? 1 : -1)
      }}
    >
      <div className="feature-viewport" aria-live={autoplay ? 'off' : 'polite'}>
        <AnimatePresence initial={false} custom={direction}>
          <motion.div key={index} className="feature-rail" custom={direction}
            variants={reduceMotion ? undefined : slide} initial="enter" animate="active" exit="exit"
            transition={{ duration: 0.26, ease: [0.32, 0.72, 0, 1] }}>
            <motion.div className="feature-drag" drag="x" dragConstraints={{ left: 0, right: 0 }} dragElastic={reduceMotion ? 0 : 0.24} dragMomentum={false}
              onDragStart={() => setDragging(true)}
              onDragEnd={(_, { offset, velocity }) => {
                setDragging(false)
                if (Math.abs(offset.x) > 40 || (Math.abs(offset.x) > 12 && Math.abs(velocity.x) > 300)) step(offset.x < 0 ? 1 : -1)
              }}>
              {card}
            </motion.div>
          </motion.div>
        </AnimatePresence>
      </div>
      <div className="feature-controls">
        <div className="feature-pagination" aria-label="Choose feature">
          {features.map(([, name], position) => (
            <button key={name} className="feature-dot" type="button" aria-label={name} aria-current={position === index ? 'true' : undefined}
              onClick={() => { if (position !== index) setSlide({ index: position, direction: position > index ? 1 : -1 }) }} />
          ))}
        </div>
      </div>
    </section>
  )
}

function FeaturePreview({ index }) {
  if (index === 0) return (
    <div className="feature-preview preview-pass" aria-label="Sample attendee pass">
      <span className="preview-qr" aria-hidden="true"><QrCode size={28} strokeWidth={1.7} /></span>
      <div className="preview-detail">
        <strong>Ananya Sharma <span className="preview-secondary">· Student Pass</span></strong>
        <span className="mono">#OAIC-2026-084</span>
      </div>
      <span className="preview-status">Paid ₹300 <Check size={13} aria-hidden="true" /></span>
    </div>
  )

  if (index === 1) return (
    <div className="feature-preview preview-row" aria-label="Sample face verification">
      <span className="preview-face" aria-hidden="true"><UserRound size={25} strokeWidth={1.5} /></span>
      <div className="preview-detail">
        <strong>Identity Match <span className="preview-value mono">99.4%</span></strong>
        <span>Gate 01 · Verified in 0.38s</span>
      </div>
    </div>
  )

  if (index === 2) return (
    <ul className="feature-preview preview-rooms" aria-label="Sample room occupancy">
      <li>
        <strong>Main Auditorium <span className="preview-secondary">· Keynote</span></strong>
        <span className="preview-status mono">412 / 450</span>
      </li>
      <li>
        <strong>Lab 02 <span className="preview-secondary">· Quantum Workshop</span></strong>
        <span className="preview-status preview-status-amber mono">88 / 100</span>
      </li>
    </ul>
  )

  return (
    <div className="feature-preview preview-telemetry" aria-label="Sample event analytics">
      <dl>
        <div><dt>Registered</dt><dd className="preview-value mono">1,240</dd></div>
        <div><dt>Checked In</dt><dd className="preview-value mono">1,168</dd></div>
        <div><dt>Turnout</dt><dd className="preview-value mono">94.2%</dd></div>
      </dl>
      <div className="preview-bars" aria-hidden="true">
        {[31, 46, 40, 68, 61, 92].map(value => <span key={value} style={{ height: `${value}%` }} />)}
      </div>
    </div>
  )
}
