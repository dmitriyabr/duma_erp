import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import { useMemo, useState } from 'react'
import { DEFAULT_PAGE_SIZE } from '../../constants/pagination'
import { api } from '../../services/api'
import type { PaginatedResponse } from '../../types/api'
import { useApi, useApiMutation } from '../../hooks/useApi'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { formatDateTime } from '../../utils/format'

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
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Users
        </Typography>
        <Button variant="contained" onClick={openCreate}>
          New user
        </Button>
      </Box>

      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <TextField
          label="Search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          size="small"
        />
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Role</InputLabel>
          <Select
            value={roleFilter}
            label="Role"
            onChange={(event) => setRoleFilter(event.target.value as UserRole | 'all')}
          >
            <MenuItem value="all">All</MenuItem>
            {roleOptions.map((role) => (
              <MenuItem key={role} value={role}>
                {role}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Status</InputLabel>
          <Select
            value={statusFilter}
            label="Status"
            onChange={(event) => setStatusFilter(event.target.value as 'all' | 'active' | 'inactive')}
          >
            <MenuItem value="all">All</MenuItem>
            <MenuItem value="active">Active</MenuItem>
            <MenuItem value="inactive">Inactive</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {error || saveError || toggleError ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error || saveError || toggleError}
        </Alert>
      ) : null}

      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Email</TableCell>
            <TableCell>Full name</TableCell>
            <TableCell>Role</TableCell>
            <TableCell>Can login</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Last login</TableCell>
            <TableCell align="right">Actions</TableCell>
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
                <Button size="small" onClick={() => openEdit(row)}>
                  Edit
                </Button>
                <Button size="small" onClick={() => requestToggleActive(row)}>
                  {row.is_active ? 'Deactivate' : 'Activate'}
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {loading ? (
            <TableRow>
              <TableCell colSpan={7} align="center">
                Loading…
              </TableCell>
            </TableRow>
          ) : null}
          {!rows.length && !loading ? (
            <TableRow>
              <TableCell colSpan={7} align="center">
                No users found
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>
      <TablePagination
        component="div"
        count={total}
        page={page}
        onPageChange={(_, nextPage) => setPage(nextPage)}
        rowsPerPage={limit}
        onRowsPerPageChange={(event) => {
          setLimit(Number(event.target.value))
          setPage(0)
        }}
      />

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{editingUser ? 'Edit user' : 'Create user'}</DialogTitle>
        <DialogContent sx={{ display: 'grid', gap: 2, mt: 1 }}>
          <TextField
            label="Email"
            value={form.email}
            onChange={(event) => setForm({ ...form, email: event.target.value })}
            fullWidth
            required
          />
          {!editingUser ? (
            <TextField
              label="Password"
              value={form.password}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
              fullWidth
              type="password"
              placeholder="Optional"
              InputLabelProps={{ shrink: true }}
            />
          ) : null}
          <TextField
            label="Full name"
            value={form.full_name}
            onChange={(event) => setForm({ ...form, full_name: event.target.value })}
            fullWidth
            required
          />
          <TextField
            label="Phone"
            value={form.phone}
            onChange={(event) => setForm({ ...form, phone: event.target.value })}
            fullWidth
            placeholder="+254..."
            InputLabelProps={{ shrink: true }}
          />
          <FormControl fullWidth>
            <InputLabel>Role</InputLabel>
            <Select
              value={form.role}
              label="Role"
              onChange={(event) => setForm({ ...form, role: event.target.value as UserRole })}
            >
              {roleOptions.map((role) => (
                <MenuItem key={role} value={role}>
                  {role}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={submitForm} disabled={loading || busy}>
            Save
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
    </Box>
  )
}
