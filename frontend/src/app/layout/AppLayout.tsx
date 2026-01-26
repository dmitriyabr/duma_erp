import { Box } from '@mui/material'
import { Outlet } from 'react-router-dom'
import { SidebarNav } from './SidebarNav'
import { TopBar } from './TopBar'

export const AppLayout = () => {
  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', backgroundColor: '#f8fafc' }}>
      <SidebarNav />
      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <TopBar />
        <Box
          component="main"
          sx={{
            flexGrow: 1,
            p: 4,
            overflowY: 'auto',
          }}
        >
          <Outlet />
        </Box>
      </Box>
    </Box>
  )
}
