import { useMemo, useState } from 'react'
import { DEFAULT_PAGE_SIZE } from '../../constants/pagination'
import { api } from '../../services/api'
import type { PaginatedResponse } from '../../types/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { formatDateTime } from '../../utils/format'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Table, TableHead, TableBody, TableRow, TableCell, TableHeaderCell, TablePagination } from '../../components/ui/Table'
import { Typography } from '../../components/ui/Typography'
import { Chip } from '../../components/ui/Chip'
import { Alert } from '../../components/ui/Alert'
import { Dialog, DialogTitle, DialogContent, DialogActions, DialogCloseButton } from '../../components/ui/Dialog'
import { Spinner } from '../../components/ui/Spinner'

type UserRole = 'SuperAdmin' | 'Admin' | 'User' | 'Accountant'

interface UserRow {
  id: number
  email: string
  full_name: string
  phone?: string | null
  role: UserRole
  is_active: boolean
  can_login: boolean
  last_login_at?: string | null
}

const roleOptions: UserRole[] = ['SuperAdmin', 'Admin', 'User', 'Accountant']

const emptyForm = {
  email: '',
  full_name: '',
  phone: '',
  role: 'User' as UserRole,
  password: '',
}

export const UsersPage = () => {
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(DEFAULT_PAGE_SIZE)
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebouncedValue(search, 400)
  const [roleFilter, setRoleFilter] = useState<UserRole | 'all'>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all')

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<UserRow | null>(null)
  const [form, setForm] = useState({ ...emptyForm })
  const [confirmState, setConfirmState] = useState<{
    open: boolean
    user?: UserRow
    nextActive?: boolean
  }>({ open: false })

  const url = useMemo(() => {
    const params: Record<string, string | number | boolean> = { page: page + 1, limit }
    if (debouncedSearch.trim()) params.search = debouncedSearch.trim()
    if (roleFilter !== 'all') params.role = roleFilter
    if (statusFilter !== 'all') params.is_active = statusFilter === 'active'

    const sp = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => sp.append(k, String(v)))
    return `/users?${sp.toString()}`
  }, [page, limit, debouncedSearch, roleFilter, statusFilter])

  const { data, loading, error, refetch } = useApi<PaginatedResponse<UserRow>>(url)
  const { execute: saveUser, loading: saving, error: saveError } = useApiMutation()
  const { execute: toggleUser, loading: toggling, error: toggleError } = useApiMutation()
  const busy = saving || toggling

  const rows = data?.items || []
  const total = data?.total || 0

  const openCreate = () => {
    setEditingUser(null)
    setForm({ ...emptyForm })
    setDialogOpen(true)
  }

  const openEdit = (user: UserRow) => {
    setEditingUser(user)
    setForm({
      email: user.email,
      full_name: user.full_name,
      phone: user.phone ?? '',
      role: user.role,
      password: '',
    })
    setDialogOpen(true)
  }

  const submitForm = async () => {
    const result = await saveUser(() =>
      editingUser
        ? api.put(`/users/${editingUser.id}`, {
            email: form.email,
            full_name: form.full_name,
            phone: form.phone || null,
            role: form.role,
          })
        : api.post('/users', {
            email: form.email,
            password: form.password || null,
            full_name: form.full_name,
            phone: form.phone || null,
            role: form.role,
          })
    )

    if (result) {
      setDialogOpen(false)
      refetch()
    }
  }

  const requestToggleActive = (user: UserRow) => {
    setConfirmState({ open: true, user, nextActive: !user.is_active })
  }

  const confirmToggleActive = async () => {
    if (!confirmState.user) return
    const endpoint = confirmState.nextActive ? 'activate' : 'deactivate'
    const userId = confirmState.user.id
    setConfirmState({ open: false })

    const result = await toggleUser(() => api.post(`/users/${userId}/${endpoint}`))
    if (result) {
      refetch()
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <Typography variant="h4">
          Users
        </Typography>
        <Button variant="contained" onClick={openCreate}>
          New user
        </Button>
      </div>

      <div className="flex gap-4 mb-4 flex-wrap">
        <div className="flex-1 min-w-[200px]">
          <Input
            label="Search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search users..."
          />
        </div>
        <div className="min-w-[160px]">
          <Select
            label="Role"
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value as UserRole | 'all')}
          >
            <option value="all">All</option>
            {roleOptions.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </Select>
        </div>
        <div className="min-w-[160px]">
          <Select
            label="Status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as 'all' | 'active' | 'inactive')}
          >
            <option value="all">All</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </Select>
        </div>
      </div>

      {(error || saveError || toggleError) && (
        <Alert severity="error" className="mb-4">
          {error || saveError || toggleError}
        </Alert>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Email</TableHeaderCell>
              <TableHeaderCell>Full name</TableHeaderCell>
              <TableHeaderCell>Role</TableHeaderCell>
              <TableHeaderCell>Can login</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Last login</TableHeaderCell>
              <TableHeaderCell align="right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.email}</TableCell>
                <TableCell>{row.full_name}</TableCell>
                <TableCell>{row.role}</TableCell>
                <TableCell>{row.can_login ? 'Yes' : 'No'}</TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    label={row.is_active ? 'Active' : 'Inactive'}
                    color={row.is_active ? 'success' : 'default'}
                  />
                </TableCell>
                <TableCell>{formatDateTime(row.last_login_at)}</TableCell>
                <TableCell align="right">
                  <div className="flex gap-2 justify-end">
                    <Button size="small" variant="outlined" onClick={() => openEdit(row)}>
                      Edit
                    </Button>
                    <Button size="small" variant="outlined" onClick={() => requestToggleActive(row)}>
                      {row.is_active ? 'Deactivate' : 'Activate'}
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {loading && (
              <TableRow>
                <TableCell colSpan={7} align="center" className="py-8">
                  <Spinner size="medium" />
                </TableCell>
              </TableRow>
            )}
            {!rows.length && !loading && (
              <TableRow>
                <TableCell colSpan={7} align="center" className="py-8">
                  <Typography color="secondary">No users found</Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
        <TablePagination
          page={page}
          rowsPerPage={limit}
          count={total}
          onPageChange={setPage}
          onRowsPerPageChange={(newLimit) => {
            setLimit(newLimit)
            setPage(0)
          }}
        />
      </div>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="md">
        <DialogCloseButton onClose={() => setDialogOpen(false)} />
        <DialogTitle>{editingUser ? 'Edit user' : 'Create user'}</DialogTitle>
        <DialogContent>
          <div className="grid gap-4">
            <Input
              label="Email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
              type="email"
            />
            {!editingUser && (
              <Input
                label="Password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                type="password"
                placeholder="Optional"
                helperText="Leave empty to generate a random password"
              />
            )}
            <Input
              label="Full name"
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              required
            />
            <Input
              label="Phone"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              placeholder="+254..."
            />
            <Select
              label="Role"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value as UserRole })}
            >
              {roleOptions.map((role) => (
                <option key={role} value={role}>
                  {role}
                </option>
              ))}
            </Select>
          </div>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setDialogOpen(false)}>
            Cancel
          </Button>
          <Button variant="contained" onClick={submitForm} disabled={loading || busy}>
            {busy ? <Spinner size="small" /> : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={confirmState.open}
        title={`${confirmState.nextActive ? 'Activate' : 'Deactivate'} user`}
        description={`Are you sure you want to ${confirmState.nextActive ? 'activate' : 'deactivate'} this user?`}
        confirmLabel={confirmState.nextActive ? 'Activate' : 'Deactivate'}
        onCancel={() => setConfirmState({ open: false })}
        onConfirm={confirmToggleActive}
      />
    </div>
  )
}
