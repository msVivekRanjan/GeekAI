import axios from 'axios'
import toast from 'react-hot-toast'

const rawApiBase = import.meta.env.VITE_API_BASE_URL
  ?.trim()
  .replace(/\/+$/, '')
  .replace(/\/api$/, '')

const client = axios.create({
  baseURL: rawApiBase ? `${rawApiBase}/api` : '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor: attach JWT token
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor: handle errors
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const { status, data } = error.response

      if (status === 401) {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        if (!window.location.pathname.includes('/login')) {
          window.location.href = '/login'
        }
      } else if (status === 422) {
        const detail = data.detail
        if (Array.isArray(detail)) {
          detail.forEach((err) => toast.error(err.msg || 'Validation error'))
        } else if (typeof detail === 'string') {
          toast.error(detail)
        }
      } else if (status >= 500) {
        toast.error('Server error. Please try again later.')
      }
    } else if (error.request) {
      toast.error('Network error. Please check your connection.')
    }

    return Promise.reject(error)
  }
)

export default client
