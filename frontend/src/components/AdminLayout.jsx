import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  LayoutDashboard,
  Users,
  CalendarDays,
  ClipboardCheck,
  Download,
  LogOut,
  UserCheck,
  Tag,
  Shield,
  Sparkles,
} from 'lucide-react'

const navItems = [
  { to: '/admin/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/admin/participants', label: 'Participants', icon: Users },
  { to: '/admin/sessions', label: 'Sessions', icon: CalendarDays },
  { to: '/admin/attendance', label: 'Attendance', icon: ClipboardCheck },
  { to: '/admin/volunteers', label: 'Volunteers', icon: UserCheck },
  { to: '/admin/coupons', label: 'Coupons', icon: Tag },
  { to: '/admin/export', label: 'Export Data', icon: Download },
]

export default function AdminLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <div className="min-h-screen lg:h-screen lg:overflow-hidden flex bg-gray-50">
      {/* Sidebar — fixed/sticky on desktop */}
      <aside className="hidden lg:flex lg:flex-col w-64 shrink-0 h-screen sticky top-0 overflow-y-auto bg-primary text-white">
        <div className="p-5 border-b border-white/10">
          <div className="flex items-center gap-2.5 font-bold text-xl">
            <img
              src={`${import.meta.env.BASE_URL}icons/geekai.svg`}
              alt="GeekAI Logo"
              className="h-8 w-8 object-contain rounded-md shadow-xs"
            />
            GeekAI Admin
          </div>
          {user?.event_name && (
            <div className="mt-3 px-3 py-1.5 bg-white/10 rounded-lg border border-white/10 text-xs text-white/90">
              <span className="text-accent font-semibold block uppercase tracking-wider text-[10px]">Active Event</span>
              <p className="font-medium truncate" title={user.event_name}>{user.event_name}</p>
            </div>
          )}
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-white/15 text-white'
                    : 'text-white/70 hover:bg-white/10 hover:text-white'
                }`
              }
            >
              <item.icon className="h-5 w-5" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-white/10">
          <div className="text-sm text-white/80 font-medium mb-1 truncate">{user?.name}</div>
          <div className="text-xs text-white/50 mb-3">{user?.role}</div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-white/60 hover:text-white text-sm transition-colors cursor-pointer"
          >
            <LogOut className="h-4 w-4" /> Logout
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-h-screen lg:h-screen lg:overflow-hidden min-w-0">
        {/* Mobile header */}
        <header className="lg:hidden bg-primary text-white px-4 py-3 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 font-bold">
              <img
                src={`${import.meta.env.BASE_URL}icons/geekai.svg`}
                alt="GeekAI Logo"
                className="h-6 w-6 object-contain rounded-md shadow-xs"
              />
              GeekAI Admin
            </div>
            {user?.event_name && (
              <p className="text-xs text-white/80 truncate max-w-[200px]">{user.event_name}</p>
            )}
          </div>
          <button onClick={handleLogout} className="text-white/60 hover:text-white cursor-pointer">
            <LogOut className="h-5 w-5" />
          </button>
        </header>

        {/* Mobile nav */}
        <nav className="lg:hidden bg-white border-b border-gray-200 px-2 py-1 flex gap-1 overflow-x-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
                  isActive
                    ? 'bg-primary/10 text-primary font-semibold'
                    : 'text-gray-500 hover:bg-gray-100'
                }`
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Desktop Top Event Header Banner */}
        <header className="hidden lg:flex bg-white border-b border-gray-200 px-8 py-4 items-center justify-between shadow-xs">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider text-accent bg-accent/10 px-2.5 py-0.5 rounded-full">
                <Shield className="h-3 w-3" /> Event Admin Portal
              </span>
              {user?.event_slug && (
                <span className="text-xs font-medium text-gray-400 bg-gray-100 px-2 py-0.5 rounded">
                  slug: {user.event_slug}
                </span>
              )}
            </div>
            <h1 className="text-2xl font-extrabold text-gray-900 mt-1 tracking-tight">
              {user?.event_name || 'GeekAI Central Admin'}
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-sm font-bold text-gray-900">{user?.name}</p>
              <p className="text-xs text-gray-500">{user?.role} • Authenticated</p>
            </div>
            <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center text-primary font-bold">
              {user?.name?.slice(0, 2).toUpperCase() || 'AD'}
            </div>
          </div>
        </header>

        <main className="flex-1 p-4 lg:p-8 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
