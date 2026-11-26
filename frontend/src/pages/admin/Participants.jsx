import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import client from '../../api/client'
import Table from '../../components/ui/Table'
import Input from '../../components/ui/Input'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import Spinner from '../../components/ui/Spinner'
import { Search, ChevronLeft, ChevronRight, Pencil, Trash2, X, Save, Eye } from 'lucide-react'
import { formatShortDate } from '../../utils/helpers'

const CATEGORIES = ['STUDENT', 'RESEARCHER', 'PROFESSIONAL', 'SPEAKER', 'OTHER']
const PAYMENT_STATUSES = ['SUCCESS', 'PENDING', 'FAILED']

export default function Participants() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [page, setPage] = useState(0)
  const limit = 20

  // Modals state
  const [deleteTarget, setDeleteTarget] = useState(null) // { id, name, email }
  const [editTarget, setEditTarget] = useState(null)
  const [editForm, setEditForm] = useState({
    name: '',
    email: '',
    phone: '',
    institution: '',
    category: 'OTHER',
    payment_status: 'PENDING',
  })
  const [editError, setEditError] = useState('')

  const { data: eventSettings } = useQuery({
    queryKey: ['admin-event-settings'],
    queryFn: () => client.get('/admin/event/form-schema').then((r) => r.data),
  })
  const cashfreeEnabled = Boolean(eventSettings?.cashfree_enabled)

  const { data, isLoading } = useQuery({
    queryKey: ['participants', search, category, page],
    queryFn: () =>
      client
        .get('/participants/', {
          params: {
            search: search || undefined,
            category: category || undefined,
            skip: page * limit,
            limit,
            include_media: false,
          },
        })
        .then((r) => r.data),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }) => client.patch(`/participants/${id}`, payload).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['participants'] })
      setEditTarget(null)
      setEditError('')
    },
    onError: (err) => {
      setEditError(err.response?.data?.detail || 'Failed to update participant.')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => client.delete(`/participants/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['participants'] })
      setDeleteTarget(null)
    },
  })

  const openEditModal = (row) => {
    setEditTarget(row)
    setEditForm({
      name: row.name || '',
      email: row.email || '',
      phone: row.phone || '',
      institution: row.institution || '',
      category: row.category || 'OTHER',
      payment_status: row.payment_status || 'PENDING',
    })
    setEditError('')
  }

  const handleEditSubmit = (e) => {
    e.preventDefault()
    if (!editForm.name.trim()) {
      setEditError('Name is required')
      return
    }
    if (!editForm.email.trim()) {
      setEditError('Email is required')
      return
    }
    updateMutation.mutate({ id: editTarget.id, payload: editForm })
  }

  const columns = [
    { key: 'id', label: 'ID' },
    {
      key: 'name',
      label: 'Participant',
      render: (_, row) => (
        <div>
          <p className="font-medium text-gray-900">{row.name}</p>
          <p className="text-xs text-gray-500">{row.email}</p>
        </div>
      ),
    },
    { key: 'institution', label: 'Institution', render: (v) => v || '—' },
    ...(cashfreeEnabled
      ? [
          {
            key: 'payment_status',
            label: 'Payment',
            render: (v) => (
              <Badge
                className={
                  v === 'SUCCESS'
                    ? 'bg-emerald-100 text-emerald-800'
                    : v === 'FAILED'
                    ? 'bg-rose-100 text-rose-800'
                    : 'bg-amber-100 text-amber-800'
                }
              >
                {v || 'PENDING'}
              </Badge>
            ),
          },
        ]
      : []),
    {
      key: 'registered_at',
      label: 'Registered',
      render: (v) => formatShortDate(v),
    },
    {
      key: '_actions',
      label: 'Actions',
      render: (_, row) => (
        <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
          <button
            title="View Details"
            onClick={() => navigate(`/admin/participants/${row.id}`)}
            className="p-1.5 rounded-lg text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 transition-colors"
          >
            <Eye className="h-4 w-4" />
          </button>
          <button
            title="Edit Participant"
            onClick={() => openEditModal(row)}
            className="p-1.5 rounded-lg text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 transition-colors"
          >
            <Pencil className="h-4 w-4" />
          </button>
          <button
            title="Delete Participant"
            onClick={() => setDeleteTarget(row)}
            className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      ),
    },
  ]

  const totalPages = Math.ceil((data?.total || 0) / limit)

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Participants</h1>
          <p className="text-xs text-gray-500">
            Total Registrations: {data?.total ?? 0}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="flex-1">
          <Input
            icon={Search}
            placeholder="Search by name or email..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0) }}
          />
        </div>
        <select
          value={category}
          onChange={(e) => { setCategory(e.target.value); setPage(0) }}
          className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
        >
          <option value="">All Categories</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <Table
        columns={columns}
        data={data?.items || []}
        loading={isLoading}
        onRowClick={(row) => navigate(`/admin/participants/${row.id}`)}
        emptyMessage="No participants found"
      />

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">
            Showing {page * limit + 1}–{Math.min((page + 1) * limit, data?.total)} of {data?.total}
          </p>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={page === 0}
              onClick={() => setPage(page - 1)}
            >
              <ChevronLeft className="h-4 w-4 mr-1" /> Prev
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={page >= totalPages - 1}
              onClick={() => setPage(page + 1)}
            >
              Next <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {editTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gray-50/50">
              <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                <Pencil className="h-5 w-5 text-primary" /> Edit Participant #{editTarget.id}
              </h2>
              <button
                onClick={() => setEditTarget(null)}
                className="text-gray-400 hover:text-gray-600 p-1 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleEditSubmit} className="p-6 space-y-4">
              {editError && (
                <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">
                  {editError}
                </div>
              )}

              <div className="grid sm:grid-cols-2 gap-4">
                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Full Name *</label>
                  <input
                    type="text"
                    required
                    value={editForm.name}
                    onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                    className="w-full rounded-lg border border-gray-300 px-3.5 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Email Address *</label>
                  <input
                    type="email"
                    required
                    value={editForm.email}
                    onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                    className="w-full rounded-lg border border-gray-300 px-3.5 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Phone Number</label>
                  <input
                    type="text"
                    value={editForm.phone}
                    onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
                    className="w-full rounded-lg border border-gray-300 px-3.5 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>

                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Institution</label>
                  <input
                    type="text"
                    value={editForm.institution}
                    onChange={(e) => setEditForm({ ...editForm, institution: e.target.value })}
                    className="w-full rounded-lg border border-gray-300 px-3.5 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Category</label>
                  <select
                    value={editForm.category}
                    onChange={(e) => setEditForm({ ...editForm, category: e.target.value })}
                    className="w-full rounded-lg border border-gray-300 px-3.5 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 bg-white"
                  >
                    {CATEGORIES.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>

                {cashfreeEnabled && (
                  <div>
                    <label className="block text-xs font-semibold text-gray-700 mb-1">Payment Status</label>
                    <select
                      value={editForm.payment_status}
                      onChange={(e) => setEditForm({ ...editForm, payment_status: e.target.value })}
                      className="w-full rounded-lg border border-gray-300 px-3.5 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 bg-white"
                    >
                      {PAYMENT_STATUSES.map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              <div className="flex gap-3 justify-end pt-4 border-t border-gray-100">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setEditTarget(null)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={updateMutation.isPending}
                >
                  {updateMutation.isPending ? <Spinner size="sm" /> : <Save className="h-4 w-4 mr-1" />}
                  Save Changes
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6 space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center gap-3">
              <div className="rounded-full bg-red-100 p-3 flex-shrink-0">
                <Trash2 className="h-6 w-6 text-red-600" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-gray-900">Delete Participant</h2>
                <p className="text-xs text-gray-500">This action cannot be undone.</p>
              </div>
            </div>
            <p className="text-sm text-gray-700">
              Are you sure you want to permanently delete <strong>{deleteTarget.name}</strong> ({deleteTarget.email})?
            </p>

            {deleteMutation.isError && (
              <p className="text-xs text-red-600">
                {deleteMutation.error?.response?.data?.detail || 'Delete failed. Only administrators can delete records.'}
              </p>
            )}

            <div className="flex gap-3 justify-end pt-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setDeleteTarget(null)}
                disabled={deleteMutation.isPending}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={() => deleteMutation.mutate(deleteTarget.id)}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? <Spinner size="sm" /> : <Trash2 className="h-4 w-4 mr-1" />}
                Confirm Delete
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
