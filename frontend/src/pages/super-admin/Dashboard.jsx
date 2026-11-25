import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Calendar, Users, Shield, Eye, Plus, Globe, ArrowRight } from 'lucide-react'
import client from '../../api/client'
import toast from 'react-hot-toast'

export default function SuperAdminDashboard() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    client.get('/super-admin/dashboard')
      .then(r => setStats(r.data))
      .catch(() => toast.error('Failed to load dashboard stats'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="sa-state" role="status">Loading dashboard…</div>
  if (!stats) return <div className="sa-state" role="alert">Dashboard unavailable. Reload the page to try again.</div>

  const metrics = [
    { label: 'Total Events', value: stats.total_events, icon: Calendar },
    { label: 'Active Events', value: stats.active_events, icon: Eye },
    { label: 'Published', value: stats.published_events, icon: Globe },
    { label: 'Total Participants', value: stats.total_participants, icon: Users },
    { label: 'Event Admins', value: stats.total_admins, icon: Shield },
  ]

  return (
    <div className="sa-page">
      <div className="sa-page-header">
        <h1>Platform Overview</h1>
        <Link to="/super-admin/events/new" className="sa-button sa-primary"><Plus size={17} />New Event</Link>
      </div>
      <dl className="sa-metrics">
        {metrics.map(({ label, value, icon: Icon }) => (
          <div key={label} className="sa-panel sa-metric">
            <dt>{label}<Icon size={17} aria-hidden="true" /></dt>
            <dd>{value ?? 0}</dd>
          </div>
        ))}
      </dl>
      <section className="sa-panel" aria-labelledby="sa-all-events">
        <div className="sa-section-header">
          <h2 id="sa-all-events">All Events</h2>
          <Link to="/super-admin/events" className="sa-text-action">Manage Events <ArrowRight size={15} /></Link>
        </div>
        {stats.events?.length ? (
          <div className="sa-table-scroll" tabIndex={0} role="region" aria-label="All events table">
            <table className="sa-table">
              <thead><tr>
                <th scope="col">Event</th><th scope="col">Slug</th><th scope="col">Status</th>
                <th scope="col" className="sa-number">Participants</th><th scope="col" className="sa-number">Actions</th>
              </tr></thead>
              <tbody>
                {stats.events.map(event => (
                  <tr key={event.id}>
                    <th scope="row">{event.name}</th>
                    <td><code>{event.slug}</code></td>
                    <td><div className="sa-statuses">
                      <span className={event.is_active ? 'sa-status sa-active' : 'sa-status'}>{event.is_active ? 'Active' : 'Inactive'}</span>
                      <span className={event.is_published ? 'sa-status' : 'sa-status sa-draft'}>{event.is_published ? 'Published' : 'Draft'}</span>
                    </div></td>
                    <td className="sa-number"><code>{event.participant_count}</code></td>
                    <td><div className="sa-row-actions">
                      <Link className="sa-text-action" to={`/super-admin/events/${event.id}/edit`}>Edit</Link>
                      <Link className="sa-text-action" to={`/super-admin/events/${event.id}/form-builder`}>Form Builder</Link>
                    </div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="sa-state">No events yet.</p>}
      </section>
    </div>
  )
}
