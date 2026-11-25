import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Calendar, ChevronRight, LayoutDashboard, LogOut, Menu, X } from 'lucide-react'
import { useRef } from 'react'
import { useAuth } from '../context/AuthContext'
import '../pages/super-admin/console.css'

const navItems = [
  { to: '/super-admin/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/super-admin/events', label: 'Events', icon: Calendar },
]

export default function SuperAdminLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const drawer = useRef(null)
  const events = pathname.startsWith('/super-admin/events')
  const page = pathname.endsWith('/form-builder') ? 'Form Builder'
    : pathname.endsWith('/edit') ? 'Edit Event'
    : pathname.endsWith('/new') ? 'New Event' : events ? 'Events' : 'Dashboard'
  const initials = user?.name?.slice(0, 2).toUpperCase() || 'SA'

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  const sidebar = (
    <>
      <div className="sa-brand">
        <img src={`${import.meta.env.BASE_URL}icons/geekai.svg`} alt="" />
        <div><strong>GeekAI</strong><small>Super Admin</small></div>
      </div>
      <nav aria-label="Console navigation" className="sa-nav">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} onClick={() => drawer.current?.close()}>
            <Icon size={17} aria-hidden="true" />{label}
          </NavLink>
        ))}
      </nav>
      <div className="sa-sidebar-footer">
        <div className="sa-profile">
          <span className="sa-avatar" aria-hidden="true">{initials}</span>
          <span className="truncate">{user?.name}<small>Super Admin</small></span>
        </div>
        <button type="button" onClick={handleLogout}><LogOut size={16} />Logout</button>
      </div>
    </>
  )

  return (
    <div className="sa-console">
      <aside className="sa-sidebar">{sidebar}</aside>
      <dialog ref={drawer} className="sa-drawer" aria-label="Console navigation"
        onClick={event => { if (event.target === event.currentTarget) drawer.current.close() }}>
        <div className="sa-drawer-inner">
          <button type="button" className="sa-icon sa-drawer-close" aria-label="Close navigation" onClick={() => drawer.current.close()}>
            <X size={19} />
          </button>
          {sidebar}
        </div>
      </dialog>
      <div className="sa-shell">
        <header className="sa-topbar">
          <button type="button" className="sa-icon sa-mobile-menu" aria-label="Open navigation" onClick={() => drawer.current.showModal()}>
            <Menu size={20} />
          </button>
          <nav aria-label="Breadcrumb" className="sa-breadcrumb">
            <span>Super Admin</span><ChevronRight size={13} aria-hidden="true" />
            {events && page !== 'Events' && (
              <><NavLink to="/super-admin/events">Events</NavLink><ChevronRight size={13} aria-hidden="true" /></>
            )}
            <strong aria-current="page">{page}</strong>
          </nav>
          <div className="sa-top-profile">
            <span>{user?.name}<small> · Super Admin</small></span>
            <span className="sa-avatar" aria-hidden="true">{initials}</span>
          </div>
        </header>
        <main className="sa-main"><Outlet /></main>
      </div>
    </div>
  )
}
