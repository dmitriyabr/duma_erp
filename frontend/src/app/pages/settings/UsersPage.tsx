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
import { useEffect, useMemo, useState } from 'react'
import { api } from '../../services/api'
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

interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
  pages: number
}

interface ApiResponse<T> {
  success: boolean
  data: T
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
  const [rows, setRows] = useState<UserRow[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(20)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState<UserRole | 'all'>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<UserRow | null>(null)
  const [form, setForm] = useState({ ...emptyForm })
  const [confirmState, setConfirmState] = useState<{
    open: boolean
    user?: UserRow
    nextActive?: boolean
  }>({ open: false })

  const requestParams = useMemo(() => {
    const params: Record<string, string | number | boolean> = {
      page: page + 1,
      limit,
    }
    if (search.trim()) {
      params.search = search.trim()
    }
    if (roleFilter !== 'all') {
      params.role = roleFilter
    }
    if (statusFilter !== 'all') {
      params.is_active = statusFilter === 'active'
    }
    return params
  }, [page, limit, search, roleFilter, statusFilter])

  const fetchUsers = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.get<ApiResponse<PaginatedResponse<UserRow>>>('/users', {
        params: requestParams,
      })
      setRows(response.data.data.items)
      setTotal(response.data.data.total)
    } catch (err) {
      setError('Failed to load users.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchUsers()
  }, [requestParams])

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
    setLoading(true)
    setError(null)
    try {
      if (editingUser) {
        await api.put(`/users/${editingUser.id}`, {
          email: form.email,
          full_name: form.full_name,
          phone: form.phone || null,
          role: form.role,
        })
      } else {
        await api.post('/users', {
          email: form.email,
          password: form.password || null,
          full_name: form.full_name,
          phone: form.phone || null,
          role: form.role,
        })
      }
      setDialogOpen(false)
      await fetchUsers()
    } catch (err) {
      setError('Failed to save user.')
    } finally {
      setLoading(false)
    }
  }

  const requestToggleActive = (user: UserRow) => {
    setConfirmState({ open: true, user, nextActive: !user.is_active })
  }

  const confirmToggleActive = async () => {
    if (!confirmState.user) {
      return
    }
    setConfirmState({ open: false })
    setLoading(true)
    try {
      const endpoint = confirmState.nextActive ? 'activate' : 'deactivate'
      await api.post(`/users/${confirmState.user.id}/${endpoint}`)
      await fetchUsers()
    } catch (err) {
      setError('Failed to update user status.')
    } finally {
      setLoading(false)
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

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
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
          <Button variant="contained" onClick={submitForm} disabled={loading}>
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
