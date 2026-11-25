import { Suspense, lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import AdminLayout from './components/AdminLayout'
import SuperAdminLayout from './components/SuperAdminLayout'
import ProtectedRoute from './components/ProtectedRoute'
import Home from './pages/Home'
import Login from './pages/Login'
import Register from './pages/Register'
import EventRegister from './pages/EventRegister'
import EventSuccess from './pages/EventSuccess'
import Dashboard from './pages/admin/Dashboard'
import Participants from './pages/admin/Participants'
import ParticipantDetail from './pages/admin/ParticipantDetail'
import Sessions from './pages/admin/Sessions'
import Attendance from './pages/admin/Attendance'
import Export from './pages/admin/Export'
import Volunteers from './pages/admin/Volunteers'
import Coupons from './pages/admin/Coupons'
import SuperAdminDashboard from './pages/super-admin/Dashboard'
import SuperAdminEvents from './pages/super-admin/Events'
import EventEditor from './pages/super-admin/EventEditor'
import FormBuilder from './pages/super-admin/FormBuilder'

// Volunteer pages are excluded from the cloud deployment.
// In cloud mode (VITE_DEPLOYMENT_MODE=cloud), these routes are not registered.
const IS_CLOUD = import.meta.env.VITE_DEPLOYMENT_MODE === 'cloud'

// Lazy-import volunteer pages only in non-cloud mode to keep cloud bundle clean.
const VolunteerDashboard = !IS_CLOUD ? lazy(() => import('./pages/volunteer/VolunteerDashboard')) : null
const FaceCheckIn = !IS_CLOUD ? lazy(() => import('./pages/volunteer/FaceCheckIn')) : null
const QRScanner = !IS_CLOUD ? lazy(() => import('./pages/volunteer/QRScanner')) : null
const ManualLookup = !IS_CLOUD ? lazy(() => import('./pages/volunteer/ManualLookup')) : null

export default function App() {
  return (
    <Suspense fallback={null}>
      <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/register" element={<Register />} />
        <Route path="/events/:eventSlug/register" element={<EventRegister />} />
        <Route path="/events/:eventSlug/success" element={<EventSuccess />} />
      </Route>
      <Route element={<Layout login />}>
        <Route path="/login" element={<Login />} />
        <Route path="/admin/login" element={<Login />} />
        {!IS_CLOUD && <Route path="/volunteer/login" element={<Login />} />}
      </Route>

      {/* Super Admin routes */}
      <Route
        path="/super-admin"
        element={
          <ProtectedRoute allowedRoles={['SUPER_ADMIN']}>
            <SuperAdminLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<SuperAdminDashboard />} />
        <Route path="events" element={<SuperAdminEvents />} />
        <Route path="events/new" element={<EventEditor />} />
        <Route path="events/:id/edit" element={<EventEditor />} />
        <Route path="events/:id/form-builder" element={<FormBuilder />} />
      </Route>

      {/* Admin routes */}
      <Route
        path="/admin"
        element={
          <ProtectedRoute allowedRoles={['ADMIN']}>
            <AdminLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="participants" element={<Participants />} />
        <Route path="participants/:id" element={<ParticipantDetail />} />
        <Route path="sessions" element={<Sessions />} />
        <Route path="attendance" element={<Attendance />} />
        <Route path="volunteers" element={<Volunteers />} />
        <Route path="coupons" element={<Coupons />} />
        <Route path="export" element={<Export />} />
      </Route>

      {/* Volunteer routes — excluded from cloud deployment */}
      {!IS_CLOUD && VolunteerDashboard && (
        <Route
          path="/volunteer"
          element={
            <ProtectedRoute allowedRoles={['ADMIN', 'VOLUNTEER']}>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<VolunteerDashboard />} />
          <Route path="face-checkin" element={<FaceCheckIn />} />
          <Route path="scan" element={<QRScanner />} />
          <Route path="manual" element={<ManualLookup />} />
        </Route>
      )}

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </Suspense>
  )
}
