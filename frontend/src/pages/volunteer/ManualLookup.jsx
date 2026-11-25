import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import client from '../../api/client'
import Button from '../../components/ui/Button'
import Input from '../../components/ui/Input'
import Card from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import { Search, ArrowLeft, CheckCircle, AlertTriangle } from 'lucide-react'
import { getCategoryColor, resolveMediaUrl } from '../../utils/helpers'
import toast from 'react-hot-toast'

export default function ManualLookup() {
  const [search, setSearch] = useState('')
  const [sessionId, setSessionId] = useState('')
  const [markingId, setMarkingId] = useState(null)
  const [lastResult, setLastResult] = useState(null)

  const { data: sessions } = useQuery({
    queryKey: ['sessions'],
    queryFn: () => client.get('/sessions/').then((r) => r.data),
  })

  const { data: participants, isLoading, refetch } = useQuery({
    queryKey: ['participant-search', search],
    queryFn: () => client.get('/participants/', { params: { search, limit: 10 } }).then((r) => r.data),
    enabled: search.length >= 2,
  })

  const markAttendance = async (participant) => {
    if (!sessionId) {
      toast.error('Please select a session first')
      return
    }
    setMarkingId(participant.id)
    try {
      await client.post('/attendance/', {
        participant_id: participant.id,
        session_id: parseInt(sessionId),
        method: 'MANUAL',
      })
      setLastResult({
        status: 'success',
        message: `Attendance marked for ${participant.name}`,
      })
      toast.success(`✅ ${participant.name} — attendance recorded`)
    } catch (err) {
      if (err.response?.status === 409) {
        setLastResult({
          status: 'duplicate',
          message: `${participant.name} — already marked for this session`,
        })
        toast.error(`Already marked: ${participant.name}`)
      } else {
        toast.error('Failed to mark attendance')
      }
    } finally {
      setMarkingId(null)
    }
  }

  return (
    <div className="max-w-lg mx-auto px-4 py-6">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/volunteer">
          <Button variant="ghost" size="sm"><ArrowLeft className="h-4 w-4" /></Button>
        </Link>
        <h1 className="text-xl font-bold text-gray-900">Manual Lookup</h1>
      </div>

      {/* Session selector */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-1">Select Session</label>
        <select
          value={sessionId}
          onChange={(e) => setSessionId(e.target.value)}
          className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
        >
          <option value="">Choose a session...</option>
          {sessions?.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
      </div>

      {/* Search */}
      <div className="mb-4">
        <Input
          icon={Search}
          placeholder="Search by name or email (min 2 chars)..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setLastResult(null) }}
        />
      </div>

      {/* Last result message */}
      {lastResult && (
        <div className={`mb-4 p-3 rounded-lg flex items-center gap-2 text-sm ${
          lastResult.status === 'success' ? 'bg-green-50 text-green-800' : 'bg-yellow-50 text-yellow-800'
        }`}>
          {lastResult.status === 'success' ? <CheckCircle className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
          {lastResult.message}
        </div>
      )}

      {/* Results */}
      {search.length >= 2 && (
        <div className="space-y-2">
          {isLoading ? (
            <p className="text-sm text-gray-400 text-center py-4">Searching...</p>
          ) : participants?.items?.length > 0 ? (
            participants.items.map((p) => (
              <Card key={p.id} className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  {p.photo_url ? (
                    <img
                      src={resolveMediaUrl(p.photo_url)}
                      alt={p.name}
                      className="w-10 h-10 rounded-full object-cover border flex-shrink-0"
                    />
                  ) : (
                    <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center text-sm font-bold text-gray-400 flex-shrink-0">
                      {p.name?.charAt(0)}
                    </div>
                  )}
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{p.name}</p>
                    <p className="text-xs text-gray-500 truncate">{p.institution || p.email}</p>
                    <Badge className={`mt-0.5 ${getCategoryColor(p.category)}`}>
                      {p.category}
                    </Badge>
                  </div>
                </div>
                <Button
                  variant="accent"
                  size="sm"
                  loading={markingId === p.id}
                  disabled={!sessionId}
                  onClick={() => markAttendance(p)}
                >
                  Mark
                </Button>
              </Card>
            ))
          ) : (
            <p className="text-sm text-gray-400 text-center py-4">No participants found</p>
          )}
        </div>
      )}
    </div>
  )
}

