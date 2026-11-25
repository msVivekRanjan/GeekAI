import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Edit2, Trash2, Eye, EyeOff, Layers, MapPin, UserCheck } from 'lucide-react'
import client from '../../api/client'
import toast from 'react-hot-toast'

export default function SuperAdminEvents() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [deletingId, setDeletingId] = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(null)

  const fetchEvents = () => {
    setLoading(true)
    client.get('/super-admin/events')
      .then(r => setEvents(r.data))
      .catch(() => toast.error('Failed to load events'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchEvents() }, [])

  const handlePublish = async (id) => {
    try {
      await client.post(`/super-admin/events/${id}/publish`)
      toast.success('Event published!')
      fetchEvents()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to publish event')
    }
  }

  const handleDeactivate = async (id) => {
    try {
      await client.post(`/super-admin/events/${id}/deactivate`)
      toast.success('Event deactivated')
      fetchEvents()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to deactivate event')
    }
  }

  const handleDelete = async (id) => {
    setDeletingId(id)
    try {
      await client.delete(`/super-admin/events/${id}`)
      toast.success('Event deleted')
      setConfirmDelete(null)
      fetchEvents()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to delete event')
    } finally {
      setDeletingId(null)
    }
  }


  if (loading) return <div className="sa-state" role="status">Loading events…</div>

  return (
    <div className="sa-page">
      <div className="sa-page-header">
        <div><h1>Events</h1><p>{events.length} event{events.length !== 1 ? 's' : ''}</p></div>
        <Link to="/super-admin/events/new" className="sa-button sa-primary"><Plus size={17} />New Event</Link>
      </div>
      <div className="sa-panel sa-directory">
        {events.map(event => (
          <article key={event.id}>
            <div className="sa-event-identity">
              <h2>{event.name}</h2>
              <div className="sa-event-meta">
                <code>{event.slug}</code>
                <span>{event.participant_count} participants</span>
                {event.registration_fee > 0 && <code>₹{(event.registration_fee / 100).toFixed(0)}</code>}
                {event.venue && <span><MapPin size={13} />{event.venue}</span>}
                <span>
                  <UserCheck size={13} aria-hidden="true" />
                  Admin <strong>{event.admin_email || 'Unassigned'}</strong>
                </span>
              </div>
              {event.tagline && <p>{event.tagline}</p>}
            </div>
            <div className="sa-statuses">
              <span className={event.is_active ? 'sa-status sa-active' : 'sa-status'}>{event.is_active ? 'Active' : 'Inactive'}</span>
              <span className={event.is_published ? 'sa-status' : 'sa-status sa-draft'}>{event.is_published ? 'Published' : 'Draft'}</span>
            </div>
            <div className="sa-row-actions">
              <Link to={`/super-admin/events/${event.id}/form-builder`} className="sa-button"><Layers size={15} />Form Builder</Link>
              <Link to={`/super-admin/events/${event.id}/edit`} className="sa-button"><Edit2 size={15} />Edit</Link>
              {event.is_published ? (
                <button onClick={() => handleDeactivate(event.id)} className="sa-button"><EyeOff size={15} />Deactivate</button>
              ) : (
                <button onClick={() => handlePublish(event.id)} className="sa-button"><Eye size={15} />Publish</button>
              )}
              {confirmDelete === event.id ? (
                <div className="sa-delete-actions">
                  <button autoFocus onClick={() => setConfirmDelete(null)} className="sa-button">Cancel</button>
                  <button onClick={() => handleDelete(event.id)} disabled={deletingId === event.id} className="sa-button sa-danger">
                    {deletingId === event.id ? 'Deleting…' : 'Confirm Delete'}
                  </button>
                </div>
              ) : (
                <button onClick={() => setConfirmDelete(event.id)} className="sa-icon sa-danger" title="Delete event" aria-label={`Delete ${event.name}`}>
                  <Trash2 size={16} />
                </button>
              )}
            </div>
          </article>
        ))}
        {events.length === 0 && <p className="sa-state">No events yet. Create an event to get started.</p>}
      </div>
    </div>
  )
}
