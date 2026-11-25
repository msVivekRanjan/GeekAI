import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Html5Qrcode } from 'html5-qrcode'
import client from '../../api/client'
import Button from '../../components/ui/Button'
import Card from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import { QrCode, Camera, CheckCircle, XCircle, AlertTriangle, ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getCategoryColor, resolveMediaUrl } from '../../utils/helpers'
import toast from 'react-hot-toast'

export default function QRScanner() {
  const [sessionId, setSessionId] = useState('')
  const [scanning, setScanning] = useState(false)
  const [result, setResult] = useState(null) // { status: 'success'|'error'|'duplicate', participant, message }
  const [loading, setLoading] = useState(false)
  const scannerRef = useRef(null)
  const html5QrCodeRef = useRef(null)

  const { data: sessions } = useQuery({
    queryKey: ['sessions'],
    queryFn: () => client.get('/sessions/').then((r) => r.data),
  })

  const startScanning = async () => {
    if (!sessionId) {
      toast.error('Please select a session first')
      return
    }
    setResult(null)
    setScanning(true)

    try {
      const html5QrCode = new Html5Qrcode('qr-reader')
      html5QrCodeRef.current = html5QrCode

      await html5QrCode.start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: { width: 250, height: 250 } },
        handleScan,
        () => {} // ignore errors during scanning
      )
    } catch (err) {
      toast.error('Could not access camera. Please grant permission.')
      setScanning(false)
    }
  }

  const stopScanning = async () => {
    try {
      if (html5QrCodeRef.current) {
        await html5QrCodeRef.current.stop()
        html5QrCodeRef.current = null
      }
    } catch {
      // ignore stop errors
    }
    setScanning(false)
  }

  useEffect(() => {
    return () => {
      if (html5QrCodeRef.current) {
        html5QrCodeRef.current.stop().catch(() => {})
      }
    }
  }, [])

  const handleScan = async (decodedText) => {
    // Pause scanning while we process
    await stopScanning()
    setLoading(true)

    try {
      let participantId = null
      let participantName = ''
      try {
        const qrData = JSON.parse(decodedText)
        participantId = qrData.participant_id || qrData.id
        participantName = qrData.name || ''
      } catch {
        const trimmed = (decodedText || '').trim()
        if (/^\d+$/.test(trimmed)) {
          participantId = parseInt(trimmed, 10)
        }
      }

      if (!participantId) {
        setResult({ status: 'error', message: 'Invalid QR code format. Expected GeekAI participant QR.' })
        setLoading(false)
        return
      }

      // Validate participant
      const validateRes = await client.post('/attendance/validate-qr', {
        participant_id: participantId,
        name: participantName,
      })

      if (!validateRes.data.valid) {
        setResult({ status: 'error', message: validateRes.data.message || 'Participant not found' })
        setLoading(false)
        return
      }

      const participant = validateRes.data.participant
      const targetSessionId = sessionId && !isNaN(parseInt(sessionId, 10)) ? parseInt(sessionId, 10) : null

      // Record attendance
      try {
        await client.post('/attendance/', {
          participant_id: participant.id,
          session_id: targetSessionId,
          method: 'QR',
        })
        setResult({
          status: 'success',
          participant,
          message: `Attendance marked for ${participant.name}`,
        })
        toast.success(`✅ ${participant.name} — attendance recorded`)
      } catch (err) {
        if (err.response?.status === 409) {
          setResult({
            status: 'duplicate',
            participant,
            message: `${participant.name} — already marked for this session`,
          })
          toast.error(`Already marked: ${participant.name}`)
        } else {
          throw err
        }
      }
    } catch (err) {
      const errorMsg =
        err.response?.data?.detail?.message ||
        err.response?.data?.detail ||
        err.message ||
        'Invalid QR code or network error'
      setResult({
        status: 'error',
        message: typeof errorMsg === 'string' ? errorMsg : 'Invalid QR code or network error',
      })
    } finally {
      setLoading(false)
    }
  }

  const scanAnother = () => {
    setResult(null)
    startScanning()
  }

  return (
    <div className="max-w-lg mx-auto px-4 py-6">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/volunteer">
          <Button variant="ghost" size="sm"><ArrowLeft className="h-4 w-4" /></Button>
        </Link>
        <h1 className="text-xl font-bold text-gray-900">QR Scanner</h1>
      </div>

      {/* Session selector */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-1">Select Session</label>
        <select
          value={sessionId}
          onChange={(e) => { setSessionId(e.target.value); setResult(null) }}
          className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
          disabled={scanning}
        >
          <option value="">Choose a session...</option>
          {sessions?.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
      </div>

      {/* Scanner area */}
      <Card className="mb-4">
        <div id="qr-reader" className="w-full rounded-lg overflow-hidden" />

        {!scanning && !result && (
          <div className="text-center py-8">
            <QrCode className="h-16 w-16 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 text-sm mb-4">Select a session and start scanning</p>
            <Button variant="accent" onClick={startScanning} disabled={!sessionId}>
              <Camera className="h-4 w-4" /> Start Scanner
            </Button>
          </div>
        )}

        {scanning && (
          <div className="mt-3 text-center">
            <p className="text-sm text-accent font-medium animate-pulse">Scanning for QR codes...</p>
            <Button variant="secondary" size="sm" onClick={stopScanning} className="mt-2">
              Stop Scanner
            </Button>
          </div>
        )}

        {loading && (
          <div className="text-center py-4">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto" />
            <p className="text-sm text-gray-500 mt-2">Processing...</p>
          </div>
        )}
      </Card>

      {/* Result display */}
      {result && (
        <Card className={`border-2 ${
          result.status === 'success' ? 'border-green-400 bg-green-50' :
          result.status === 'duplicate' ? 'border-yellow-400 bg-yellow-50' :
          'border-red-400 bg-red-50'
        }`}>
          <div className="flex items-start gap-3">
            {result.status === 'success' && <CheckCircle className="h-6 w-6 text-green-600 flex-shrink-0 mt-0.5" />}
            {result.status === 'duplicate' && <AlertTriangle className="h-6 w-6 text-yellow-600 flex-shrink-0 mt-0.5" />}
            {result.status === 'error' && <XCircle className="h-6 w-6 text-red-600 flex-shrink-0 mt-0.5" />}
            <div className="flex-1">
              <p className={`font-semibold ${
                result.status === 'success' ? 'text-green-800' :
                result.status === 'duplicate' ? 'text-yellow-800' :
                'text-red-800'
              }`}>
                {result.status === 'success' ? '✅ Attendance Marked' :
                 result.status === 'duplicate' ? '⚠️ Already Marked' :
                 '❌ Error'}
              </p>
              <p className="text-sm mt-1">{result.message}</p>
              {result.participant && (
                <div className="mt-3 flex items-center gap-3">
                  {result.participant.photo_url && (
                    <img
                      src={resolveMediaUrl(result.participant.photo_url)}
                      alt={result.participant.name}
                      className="w-12 h-12 rounded-full object-cover border-2 border-white shadow"
                    />
                  )}
                  <div>
                    <p className="font-medium text-gray-900">{result.participant.name}</p>
                    <p className="text-xs text-gray-500">{result.participant.institution}</p>
                    <Badge className={`mt-1 ${getCategoryColor(result.participant.category)}`}>
                      {result.participant.category}
                    </Badge>
                  </div>
                </div>
              )}
            </div>
          </div>
          <div className="mt-4">
            <Button variant="accent" onClick={scanAnother} className="w-full">
              Scan Next
            </Button>
          </div>
        </Card>
      )}
    </div>
  )
}

