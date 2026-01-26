import {
  AppBar,
  Avatar,
  Box,
  IconButton,
  Menu,
  MenuItem,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material'
import LogoutIcon from '@mui/icons-material/Logout'
import PersonIcon from '@mui/icons-material/Person'
import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'

export const TopBar = () => {
  const { user, logout } = useAuth()
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null)

  const handleMenu = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget)
  }

  const handleClose = () => {
    setAnchorEl(null)
  }

  const handleLogout = () => {
    handleClose()
    logout()
  }

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }

  return (
    <AppBar
      position="sticky"
      elevation={0}
      sx={{
        bgcolor: '#ffffff',
        color: '#1e293b',
        borderBottom: '1px solid #e2e8f0',
      }}
    >
      <Toolbar sx={{ display: 'flex', justifyContent: 'space-between', minHeight: 64 }}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 600, color: '#1e293b' }}>
            {user ? `Welcome back, ${user.full_name.split(' ')[0]}` : 'School ERP'}
          </Typography>
          <Typography variant="body2" sx={{ color: '#64748b', fontSize: '0.8125rem' }}>
            {new Date().toLocaleDateString('en-GB', {
              weekday: 'long',
              year: 'numeric',
              month: 'long',
              day: 'numeric',
            })}
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Tooltip title="Account">
            <IconButton
              onClick={handleMenu}
              sx={{
                p: 0.5,
                '&:hover': {
                  backgroundColor: 'rgba(99, 102, 241, 0.08)',
                },
              }}
            >
              <Avatar
                sx={{
                  width: 40,
                  height: 40,
                  background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
                  fontSize: '0.875rem',
                  fontWeight: 600,
                }}
              >
                {user ? getInitials(user.full_name) : <PersonIcon />}
              </Avatar>
            </IconButton>
          </Tooltip>

          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={handleClose}
            transformOrigin={{ horizontal: 'right', vertical: 'top' }}
            anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
            PaperProps={{
              sx: {
                mt: 1,
                minWidth: 200,
                borderRadius: 2,
                boxShadow: '0 10px 40px -10px rgba(0, 0, 0, 0.2)',
              },
            }}
          >
            <Box sx={{ px: 2, py: 1.5, borderBottom: '1px solid #e2e8f0' }}>
              <Typography sx={{ fontWeight: 600, color: '#1e293b' }}>
                {user?.full_name}
              </Typography>
              <Typography variant="body2" sx={{ color: '#64748b' }}>
                {user?.email}
              </Typography>
              <Typography
                variant="caption"
                sx={{
                  display: 'inline-block',
                  mt: 0.5,
                  px: 1,
                  py: 0.25,
                  borderRadius: 1,
                  backgroundColor: 'rgba(99, 102, 241, 0.1)',
                  color: '#6366f1',
                  fontWeight: 500,
                }}
              >
                {user?.role}
              </Typography>
            </Box>
            <MenuItem
              onClick={handleLogout}
              sx={{
                py: 1.5,
                color: '#ef4444',
                '&:hover': {
                  backgroundColor: 'rgba(239, 68, 68, 0.08)',
                },
              }}
            >
              <LogoutIcon sx={{ mr: 1.5, fontSize: 20 }} />
              Sign out
            </MenuItem>
          </Menu>
        </Box>
      </Toolbar>
    </AppBar>
  )
}
