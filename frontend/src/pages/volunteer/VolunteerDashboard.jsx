import { Link } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { QrCode, Search } from 'lucide-react'
import Card from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'

export default function VolunteerDashboard() {
  const { user } = useAuth()

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Volunteer Operations Dashboard</h1>
        <p className="text-gray-500 mt-1">Welcome, {user?.name}!</p>
      </div>

      <div className="space-y-6">
        {/* Session Attendance Section */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500">
              Event &amp; Session Attendance
            </h2>
            <Badge className="bg-gray-100 text-gray-700 text-[10px] font-bold">CHECK-IN</Badge>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <Link to="/volunteer/scan">
              <Card className="h-full hover:shadow-md transition-shadow cursor-pointer border-2 border-transparent hover:border-accent/30">
                <div className="flex items-start gap-3">
                  <div className="p-2.5 bg-accent/10 rounded-lg shrink-0">
                    <QrCode className="h-6 w-6 text-accent" />
                  </div>
                  <div>
                    <h3 className="text-base font-semibold text-gray-900">Scan QR Code</h3>
                    <p className="text-xs text-gray-500 mt-1">
                      Scan attendee QR badge to record event or session attendance
                    </p>
                  </div>
                </div>
              </Card>
            </Link>

            <Link to="/volunteer/manual">
              <Card className="h-full hover:shadow-md transition-shadow cursor-pointer border-2 border-transparent hover:border-primary/30">
                <div className="flex items-start gap-3">
                  <div className="p-2.5 bg-primary/10 rounded-lg shrink-0">
                    <Search className="h-6 w-6 text-primary" />
                  </div>
                  <div>
                    <h3 className="text-base font-semibold text-gray-900">Manual Lookup</h3>
                    <p className="text-xs text-gray-500 mt-1">
                      Search attendee by name/ID for event or session attendance
                    </p>
                  </div>
                </div>
              </Card>
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
