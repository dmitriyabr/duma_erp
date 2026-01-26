import {
  Box,
  Collapse,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
} from '@mui/material'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import SchoolIcon from '@mui/icons-material/School'
import { useMemo, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { navItems } from '../navigation/navItems'
import { useAuth } from '../auth/AuthContext'

const drawerWidth = 280

export const SidebarNav = () => {
  const { user } = useAuth()
  const location = useLocation()
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({})

  const role = user?.role
  const availableItems = useMemo(() => {
    if (!role) {
      return []
    }
    return navItems.filter((item) => item.roles.includes(role))
  }, [role])

  const toggleGroup = (label: string) => {
    setOpenGroups((prev) => ({ ...prev, [label]: !prev[label] }))
  }

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: drawerWidth,
        flexShrink: 0,
        [`& .MuiDrawer-paper`]: {
          width: drawerWidth,
          boxSizing: 'border-box',
          background: 'linear-gradient(180deg, #1e293b 0%, #0f172a 100%)',
          color: '#e2e8f0',
        },
      }}
    >
      {/* Logo Section */}
      <Box
        sx={{
          px: 3,
          py: 3,
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
        }}
      >
        <Box
          sx={{
            width: 40,
            height: 40,
            borderRadius: 2,
            background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <SchoolIcon sx={{ color: 'white', fontSize: 24 }} />
        </Box>
        <Box>
          <Typography
            sx={{
              fontWeight: 700,
              fontSize: '1.125rem',
              color: '#ffffff',
              letterSpacing: '-0.02em',
            }}
          >
            School ERP
          </Typography>
          <Typography
            sx={{
              fontSize: '0.75rem',
              color: '#94a3b8',
            }}
          >
            Management System
          </Typography>
        </Box>
      </Box>

      {/* Navigation */}
      <Box sx={{ px: 1.5, py: 1, flexGrow: 1, overflowY: 'auto' }}>
        <List disablePadding>
          {availableItems.map((item) => {
            const hasChildren = !!item.children?.length
            const isChildActive = item.children?.some(
              (child) => location.pathname === child.path
            )
            const isActive = location.pathname === item.path || isChildActive
            const isGroupOpen = openGroups[item.label] ?? !!isChildActive

            return (
              <Box key={item.label}>
                <ListItemButton
                  component={hasChildren ? 'button' : NavLink}
                  to={hasChildren ? undefined : item.path}
                  onClick={hasChildren ? () => toggleGroup(item.label) : undefined}
                  sx={{
                    borderRadius: 2,
                    mb: 0.5,
                    mx: 0,
                    px: 2,
                    py: 1.25,
                    color: isActive ? '#ffffff' : '#94a3b8',
                    backgroundColor: isActive ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
                    '&:hover': {
                      backgroundColor: isActive
                        ? 'rgba(99, 102, 241, 0.25)'
                        : 'rgba(255, 255, 255, 0.05)',
                      color: '#ffffff',
                    },
                    '& .MuiListItemIcon-root': {
                      color: isActive ? '#818cf8' : '#64748b',
                    },
                    '&:hover .MuiListItemIcon-root': {
                      color: isActive ? '#818cf8' : '#94a3b8',
                    },
                  }}
                >
                  {item.icon && (
                    <ListItemIcon sx={{ minWidth: 36 }}>
                      {item.icon}
                    </ListItemIcon>
                  )}
                  <ListItemText
                    primary={item.label}
                    primaryTypographyProps={{
                      fontSize: '0.875rem',
                      fontWeight: isActive ? 600 : 500,
                    }}
                  />
                  {hasChildren ? (
                    isGroupOpen ? (
                      <ExpandLessIcon sx={{ fontSize: 18, opacity: 0.7 }} />
                    ) : (
                      <ExpandMoreIcon sx={{ fontSize: 18, opacity: 0.7 }} />
                    )
                  ) : null}
                </ListItemButton>
                {hasChildren ? (
                  <Collapse in={isGroupOpen} timeout="auto" unmountOnExit>
                    <List disablePadding sx={{ pl: 2 }}>
                      {item.children?.map((child) => {
                        if (!role || !child.roles.includes(role)) {
                          return null
                        }
                        const isChildItemActive = location.pathname === child.path
                        return (
                          <ListItemButton
                            key={child.label}
                            component={NavLink}
                            to={child.path}
                            sx={{
                              borderRadius: 2,
                              mb: 0.25,
                              px: 2,
                              py: 0.875,
                              color: isChildItemActive ? '#ffffff' : '#94a3b8',
                              backgroundColor: isChildItemActive
                                ? 'rgba(99, 102, 241, 0.15)'
                                : 'transparent',
                              '&:hover': {
                                backgroundColor: isChildItemActive
                                  ? 'rgba(99, 102, 241, 0.2)'
                                  : 'rgba(255, 255, 255, 0.05)',
                                color: '#ffffff',
                              },
                              '&::before': {
                                content: '""',
                                position: 'absolute',
                                left: 0,
                                top: '50%',
                                transform: 'translateY(-50%)',
                                width: 4,
                                height: isChildItemActive ? 20 : 0,
                                borderRadius: 2,
                                backgroundColor: '#6366f1',
                                transition: 'height 0.2s ease',
                              },
                            }}
                          >
                            <ListItemText
                              primary={child.label}
                              primaryTypographyProps={{
                                fontSize: '0.8125rem',
                                fontWeight: isChildItemActive ? 600 : 400,
                              }}
                            />
                          </ListItemButton>
                        )
                      })}
                    </List>
                  </Collapse>
                ) : null}
              </Box>
            )
          })}
        </List>
      </Box>

      {/* Footer */}
      <Box
        sx={{
          px: 3,
          py: 2,
          borderTop: '1px solid rgba(255, 255, 255, 0.1)',
        }}
      >
        <Typography sx={{ fontSize: '0.75rem', color: '#64748b' }}>
          Version 1.0.0
        </Typography>
      </Box>
    </Drawer>
  )
}
